# Changelog

## 0.1.2

- **Data files lost their vendor names**: `data/recorded/perch.txt` → `seat-a.txt`, `qwen.txt` → `seat-b.txt`; `demo` now prints seats as `seat-a` / `seat-b`. Readings unchanged (26/26, 25/26).
- **Cover image** at the top of both READMEs (`docs/cover.jpg`, L4ST-afk).
- No behaviour change.

`[English](CHANGELOG.md) · [中文](CHANGELOG.zh-CN.md)`

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
