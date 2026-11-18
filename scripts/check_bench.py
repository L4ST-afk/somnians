#!/usr/bin/env python3
"""Reconcile indexed and exact scans on reproducible synthetic records."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def scan(records, output, exact):
    command = [
        sys.executable, "-m", "somnians.cli", "scan",
        "--in", str(records), "--out", str(output),
    ]
    if exact:
        command.append("--exact")
    subprocess.run(command, cwd=ROOT, check=True)


def pairs(path):
    with path.open(encoding="utf-8") as stream:
        return {
            (row["keeper"], row["drop"])
            for line in stream
            if line.strip()
            for row in [json.loads(line)]
        }


def main():
    with tempfile.TemporaryDirectory(prefix="somnians-bench-") as directory:
        temp = Path(directory)
        records = temp / "bench.jsonl"
        with records.open("w", encoding="utf-8") as output:
            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "make_bench.py"), "--n", "400"],
                cwd=ROOT, check=True, stdout=output,
            )
        exact_output = temp / "exact.jsonl"
        indexed_output = temp / "indexed.jsonl"
        scan(records, exact_output, exact=True)
        scan(records, indexed_output, exact=False)
        exact_pairs = pairs(exact_output)
        indexed_pairs = pairs(indexed_output)
        if exact_pairs != indexed_pairs:
            missing = exact_pairs - indexed_pairs
            extra = indexed_pairs - exact_pairs
            raise AssertionError(f"Mismatch: {len(missing)} missing, {len(extra)} extra")
        print(f"Consistent: {len(exact_pairs)} pairs")


if __name__ == "__main__":
    main()
