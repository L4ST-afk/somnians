import contextlib
import io
import json
import os
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from somnians import cli


class CliBehaviorTests(unittest.TestCase):
    def test_selfcheck_marker_is_safe_for_cp1252_stdout(self):
        output = io.BytesIO()
        stdout = io.TextIOWrapper(output, encoding="cp1252")
        with contextlib.redirect_stdout(stdout):
            cli._selfcheck_line(True, "probe")
            cli._selfcheck_line(False, "probe")
            stdout.flush()
        self.assertEqual(output.getvalue(), b"[OK] probe\n[FAIL] probe\n")

    def test_normalization_and_verdict_parser(self):
        self.assertEqual(cli.norm("记忆- a! 12"), "记忆a12")
        self.assertEqual(
            cli.parse_verdicts("G01｜不并\nG02｜并\nG03｜不合并", {"G01", "G02", "G03"}),
            {"G01": "不并", "G02": "并", "G03": "不并"},
        )

    def test_indexed_pairs_match_exact_pairs(self):
        records = [
            {"id": "a", "text": "归档之前必须保留数据库快照"},
            {"id": "b", "text": "归档之前必须保留数据库快照，并记录背景"},
            {"id": "c", "text": "上线后检查审计表和日志目录"},
            {"id": "deleted", "text": "归档之前必须保留数据库快照", "is_deleted": True},
        ]
        live = [record for record in records if not record.get("is_deleted")]

        def accepted_pairs(pair_generator):
            return {
                (i, j): round(score, 4)
                for i, j in pair_generator
                if (score := cli.match(live[i]["text"], live[j]["text"], 0.62)) is not None
            }

        self.assertEqual(
            accepted_pairs(cli._pairs_indexed(live, cap=1000)),
            accepted_pairs(cli._pairs_exact(live)),
        )

    def seed_rollback_batch(self, root):
        records = root / "records.jsonl"
        merged_record = {
            "id": "drop",
            "text": "A record to restore",
            "is_deleted": True,
            "merged_into": "keeper",
            "source": "test",
        }
        records.write_text(
            json.dumps({"id": "keeper", "text": "Keeper", "is_deleted": False}) + "\n"
            + json.dumps(merged_record) + "\n",
            encoding="utf-8",
        )
        db = root / "audit.db"
        con = cli._db(str(db))
        undo = {"id": "drop", "text": "A record to restore", "is_deleted": False}
        con.execute(
            "INSERT INTO audit_merge VALUES(?,?,?,?,?,?)",
            ("drop", "keeper", "batch-1", 0.9, "batch", "now"),
        )
        con.execute(
            "INSERT INTO audit_change(entry_id,op,batch,undo_json,created_at) "
            "VALUES(?,?,?,?,?)",
            ("drop", "soft_delete", "batch-1", json.dumps(undo), "now"),
        )
        con.commit()
        con.close()
        return records, db

    def audit_counts(self, db):
        con = cli._db(str(db))
        counts = (
            con.execute(
                "SELECT COUNT(*) FROM audit_change WHERE op='rollback' AND batch='batch-1'"
            ).fetchone()[0],
            con.execute(
                "SELECT COUNT(*) FROM audit_merge WHERE batch='batch-1'"
            ).fetchone()[0],
        )
        con.close()
        return counts

    def run_rollback(self, records, db):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return cli.cmd_rollback(Namespace(
                records=str(records), db=str(db), batch="batch-1",
            ))

    def test_rollback_precommit_failure_restores_original_file_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            records, db = self.seed_rollback_batch(Path(directory))
            original = records.read_bytes()

            with patch.dict(os.environ, {"SOMNIANS_FAULT": "rollback_before_commit"}):
                result = self.run_rollback(records, db)

            self.assertEqual(result, 4)
            self.assertEqual(records.read_bytes(), original)
            self.assertEqual(self.audit_counts(db), (0, 1))
            self.assertEqual(sorted(path.name for path in Path(directory).iterdir()),
                             ["audit.db", "records.jsonl"])

    def test_rollback_postcommit_failure_keeps_committed_restore_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            records, db = self.seed_rollback_batch(Path(directory))

            with patch.dict(os.environ, {"SOMNIANS_FAULT": "rollback_after_commit"}):
                result = self.run_rollback(records, db)

            restored = [json.loads(line) for line in records.read_text(encoding="utf-8").splitlines()]
            restored_drop = next(record for record in restored if record["id"] == "drop")
            self.assertEqual(result, 4)
            self.assertFalse(restored_drop["is_deleted"])
            self.assertNotIn("merged_into", restored_drop)
            self.assertEqual(restored_drop["source"], "test")
            self.assertEqual(self.audit_counts(db), (1, 0))

            committed_file = records.read_bytes()
            self.assertEqual(self.run_rollback(records, db), 0)
            self.assertEqual(records.read_bytes(), committed_file)
            self.assertEqual(self.audit_counts(db), (1, 0))


if __name__ == "__main__":
    unittest.main()
