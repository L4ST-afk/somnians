# Changelog

`[English](CHANGELOG.md) · [中文](CHANGELOG.zh-CN.md)`

## 0.1.6 — 2026-11-19

- **Brief fixes the roles first, with shape examples**: the adjudication brief opens by fixing `keeper` (kept) and `drop` (folded in), and the criterion now carries one positive and one negative shape example, so a seat cannot read "drop has fewer words" backwards as "keep apart".
- **Seat identity check**: `adjudicate` scans the seat's output and stderr for fallback / unavailable traces (model not available, using auto, insufficient quota, 402, insufficient balance). A matching seat's verdicts are discarded and its groups are left missing for retry; the trace is reported in the round output instead of being counted under a model that never answered.
- **Tests**: two new cases in `tests/test_cli.py` (13 total) — a fallback-trace seat drops its verdicts; a normal seat is not flagged.

## 0.1.5 — 2026-11-18

- **Windows keeps CRLF files intact**: `apply` now hashes and backs up the records file as raw bytes. Before, it read and rewrote the file as text, so a CRLF file lost its line endings on the way through and the backup digest never matched the rewritten digest — `selfcheck` failed on files that were fine. The same byte-level rule now covers the staged file and the fingerprint written into the journal, so `recover` compares like with like.
- **Tests**: two new cases in `tests/test_cli.py` (11 total) — a CRLF file recovered before the batch lands, and a CRLF file whose records are backfilled from the written bytes. Both run the same interruption path as the LF cases.

## 0.1.4 — 2026-11-18

- **`recover` decides by file fingerprints**: the journal records the sha256 of the records file before and after the batch. `recover` compares the file against both — equals the "after" hash ⇒ the rename happened and the audit is missing ⇒ backfill; equals the "before" hash ⇒ nothing took effect ⇒ drop the journal; neither ⇒ unknown state, nothing written and nothing deleted, exit code 5. This replaces the old `is_deleted` test, which read a record that was already soft-deleted before the batch as proof the apply had landed.
- **Recovery is idempotent**: when the batch's `audit_change` rows are already committed, `recover` only deletes the journal and writes nothing, so an interrupted recovery can be rerun safely. Journals written before 0.1.4 carry no fingerprints; those fall back to the old check and say in the output that the evidence is weaker.
- **Tests**: four new cases in `tests/test_cli.py` (9 total) — a pre-existing soft delete, backfill on the "after" hash, an idempotent rerun, and a refusal on an unrecognised file.

## 0.1.3 — 2026-11-18

- **`rollback` persistence hardened**: it writes the complete restored JSONL and fsyncs it, atomically replaces the records file, then commits the audit transaction. An ordinary pre-commit error rolls SQLite back and atomically restores the original file; a batch that already carries an `op=rollback` row is a no-op on repeat. `rollback` itself still has no crash-recovery journal, and the README keeps saying so.
- **Cross-platform CI**: the matrix is Ubuntu 24.04 / macOS / Windows × Python 3.9 / 3.11 / 3.13, plus a `quality-gate` job that fails unless every matrix job passes. `demo` and `selfcheck` output no longer breaks on consoles that cannot encode the symbols it prints (cp1252 and friends); the synthetic benchmark and its timings reproduce on Windows.
- **Tests**: `tests/test_cli.py` (standalone unit tests) and `scripts/check_bench.py` (indexed-vs-exact reconciliation).
- **Docs**: both READMEs rewritten so each section opens with the claim it makes; new cover art (L4ST-afk); internal branch names and private paths removed.

## 0.1.2

- **Data files dropped their vendor names**: the recorded verdicts are now `data/recorded/seat-a.txt` / `seat-b.txt` (previously named after the two vendors), and `demo` prints seats as `seat-a` / `seat-b`. Readings unchanged (26/26, 25/26).
- **Cover image** at the top of both READMEs (`docs/cover.jpg`, L4ST-afk).
- No behaviour change.

## 0.1.1 — 2026-11-18

- **Three runtime catalogs**: English / Simplified / Traditional, chosen by `--lang`, then `SOMNIANS_LANG`, then `LC_ALL` / `LC_MESSAGES` / `LANGUAGE` / `LANG`, defaulting to English. `C` and `POSIX` are skipped; unknown tags fall back instead of guessing.
- **Not translated, by contract**: verdict values `并` / `不并` / `未判`, the `SELFCHECK_*` tokens, numbers, IDs, paths, exit codes.
- **`selfcheck` 13 → 15 items**: one asserts the three catalogs are key-for-key aligned and that resolution order holds (flag > env > locale > en); the other asserts an unlisted field (`source`) survives `apply` → `rollback` untouched — the passthrough promise the contracts section now makes.
- Doc pair (README / CONTRIBUTING / CHANGELOG) now carries a Languages section; both language versions must change together (see CONTRIBUTING).

## 0.1.0 — 2026-11-18

First installable version.

- **Seven executable entries**: `demo` (offline replay of two recorded seats), `scan`, `adjudicate`, `apply`, `rollback`, `recover`, `selfcheck`.
- **Atomic order in `apply`**: back up and read back to compare sha256 → write staging file → write journal → `os.replace` → commit transaction → delete journal. Both breakpoints (crash after rename, crash after journal) have a tested recovery path; `recover` decides by the file's actual state, not by whether a journal exists.
- **Two audit tables**: `audit_merge` (who merged whom, which batch, what score) and `audit_change` (undo for every step, including rollback's own record).
- **Inverted index in `scan`**: 3-gram posting lists prune candidates, with the same scoring as full `--exact` (real store of 3,201 records: 174.6 s → 14.5 s; 808 pairs identical pair by pair and score by score).
- **Concurrency and truncation recovery in `adjudicate`**: `--jobs` splits by group and dispatches in parallel; `--retry` resends only missing groups. Missing groups are written as `未判` (undecided) with exit code 2 — never recorded as "keep apart".
- **`selfcheck`, 13 items**: explicit data root, canary on the public gold set, before/after optimization reconciliation, audit schema, apply/rollback round trip, fault injection at both crash points.
- **Public gold set, 26 cases**: five trap families (canary / compression loss / degree difference / object difference / polarity / non-entry). A fabricated seat scores 39.3% on it, which is how the criterion proves it has teeth.
- **CI**: Python 3.9 / 3.11 / 3.13, self-check + readings + inverted-index reconciliation.
