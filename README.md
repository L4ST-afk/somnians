# somnians · 蝶花半梦（Viola Somnians）

[![selfcheck](https://github.com/L4ST-afk/somnians/actions/workflows/selfcheck.yml/badge.svg)](https://github.com/L4ST-afk/somnians/actions/workflows/selfcheck.yml)
[![PyPI](https://img.shields.io/pypi/v/somnians)](https://pypi.org/project/somnians/)
[![Python](https://img.shields.io/pypi/pyversions/somnians)](https://pypi.org/project/somnians/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)


`[English](README.md) · [中文](README.zh-CN.md)`

<img src="docs/cover.jpg" alt="蝶花半梦 · Viola Somnians — a pansy with butterflies, watercolour on torn paper" width="720">


**This tool handles one thing only: duplicates that have already settled in.** The rule you wrote twice, three times, five times across 3,000 records — that pile. mem0 / Zep / Letta decide at write time whether something gets stored. This never touches the write path; it looks at what is already in the store, and at how many times the same sentence sits there.

Four steps, and none of them can be skipped: scan for near-duplicates → your own seat adjudicates each pair → soft-delete in one transaction → roll back one batch at a time. Every step leaves an audit trail.

**The artifact is a CLI, not a library.** A library would need a host first; a prompt would need something that can run prompts. A CLI needs one line after install, and it prints numbers you can check. The seven subcommands are independent, so you can wire it into any store without changing yours.

**Naming**: Chinese name 蝶花半梦, Latin name *Viola Somnians* (pansy + dream). Commands and package name are `somnians` — it is now on PyPI; `viola` was taken.

```
scan → candidate groups → seat verdicts (merge / keep apart) → apply (soft delete) → rollback (by batch)
                                      └── audit_merge + audit_change: two tables, every step
```

## Install, then read the numbers

Read those two rows first. They are a self-test: change the seat or the criterion, print them again, and only then decide whether to trust the rest.

```bash
pipx install .        # or pip install .
somnians demo         # replays two seats' recorded verdicts offline: no network, no key

# or skip installing: the repo ships a zero-install entry
./somnians demo
```

```
Public gold set, 26 cases: CANARY×2, COMPRESS×4, LIMIT×4, NONENTRY×5, OBJECT×4, POLARITY×4, VALUE×3

seat             accuracy  reversed   canary   verdict
seat-a           26/26     0.0%       all pass usable
seat-b           25/26     0.0%       all pass usable

1 disagreement: T10 — seat-a keeps it apart (correct); seat-b merges it (flattens the channel difference between a message and an email). The two seats are unnamed on purpose: the rows only claim what these verdict sets score, not which vendor is better.
```

**How to read it**: accuracy = agreement with the gold labels, denominator 26 (canaries included); if any canary fails, the whole reading is void. Change the seats or the corpus and these numbers move; the row only claims what these two seats score on **this criterion set**, reproducibly — nothing about which model is stronger.

That single T10 disagreement is worth a second look: the seat that merged it treated "message" and "email" as the same channel. That is exactly the class of thing the criterion below is built to stop.

## One criterion

**In every pair, `keeper` (the longer / fuller entry) is kept; `drop` folds into `keeper`.**

**The cost of a merge = the information in `drop` that `keeper` does not have.**

- `drop` has **more** than `keeper` (a qualifier, an exception, a second object, a different value, an opposite tone) ⇒ **keep apart**
- `drop` has **less** than `keeper` (abbreviated form, fragment, dropped modifier, different word order, one extra preposition) ⇒ **merge**
- Opposite polarity (one forbids, one permits) ⇒ **keep apart**

On top of that sits a **pre-filter** (structural, not semantic): annotations and status words, fragments under 8 characters with no predicate, pure punctuation/numbers/emoji, receipt chatter ⇒ not an entry at all; verdict "keep apart" and **list them by name**.

This layer cannot be skipped. Something like `全批。` ("approve the whole batch") would read as "merge" under the criterion above, because it has no information to lose — and merging it into a keeper only pollutes the text.

## Three contracts, and nothing else

```jsonl
// records.jsonl — export your own store into this
{"id":"a1","text":"归档时必须包含 AGENTS.md 文件，并记录背景信息及遇到的问题","is_deleted":false}

// candidates.jsonl — produced by scan, one line per pair
{"group":"G01","keeper":"a1","drop":"a2","score":0.8421,"keeper_text":"…","drop_text":"…"}

// decisions.jsonl — seat verdicts
{"group":"G01","verdict":"并", ...}
```

No database, no ORM, no MCP host. Exporting is about 20 lines of code.

Any field these three contracts do not name is carried through untouched: `apply` and `rollback` rewrite the whole line and only change `is_deleted` (plus `merged_into` on the drop). An upstream `source` or `source_client` column can therefore ride along even though this tool has no idea what it means — passthrough, not a criterion. `selfcheck` holds that to a test.

## Seven subcommands

```bash
# 1. scan candidates (default threshold 0.62, deliberately low: scan handles recall, the seat handles precision)
./somnians scan --in records.jsonl --out candidates.jsonl

# 2. hand them to your seat. Adapter contract: the command receives a brief path as argv[1],
#    prints ID｜并 (merge) or ID｜不并 (keep apart), one per line
./somnians adjudicate --in candidates.jsonl --out decisions.jsonl \
    --adapter ./my-seat.sh --brief-out brief.md \
    --jobs 3         # three seats in parallel, candidates split by group
    --retry 2        # truncation recovery: resend only the missing groups, at most twice

# 3. commit (soft delete + audit; the original file is backed up as .bak-<batch>)
./somnians apply --records records.jsonl --decisions decisions.jsonl --batch dream-20261118

# 4. restore one batch (a single line; the audit table keeps an op=rollback record)
./somnians rollback --records records.jsonl --batch dream-20261118

# 5. crash recovery (only needed when apply was cut off midway; with no journal it does nothing)
./somnians recover --records records.jsonl --db somnians-audit.db --batch dream-20261118

# 6. self-check (offline, no network): data root / canary / optimization reconciliation / audit schema / apply-rollback round trip
./somnians selfcheck        # expect SELFCHECK_PASS, exit code 0

# 7. demo — offline replay of two recorded seats (see "Install" above)
./somnians demo
```

Before writing anything, `apply` **proves its own backup**: it reads `.bak-<batch>` back, computes sha256 and compares it with the original, and aborts before touching the target if they differ (exit code 3). "The file is still there" is not proof.

## Languages

Runtime copy ships in three catalogs: **English / 简体 / 繁體**. Order of choice: `--lang` > `SOMNIANS_LANG` > `LANGUAGE` > `LC_ALL` / `LC_MESSAGES` > `LANG` > English. `C`, `POSIX` and empty values are skipped; an unrecognised tag falls back to English instead of guessing.

```bash
./somnians demo                    # follows your locale
SOMNIANS_LANG=zh-Hant ./somnians demo
./somnians --lang en selfcheck
```

Three things are never translated: the verdict values `并` / `不并` / `未判` (they are the JSONL contract, so a translated run still writes the same bytes), the `SELFCHECK_PASS` / `SELFCHECK_FAIL` tokens, and every number, ID, path and exit code. Traditional Chinese is a **static catalog, not a runtime conversion**: the CLI is zero-dependency and offline, and 一简对多繁 (发→發/髮, 干→乾/幹) means a runtime guess makes the reader guess again. Vocabulary differences (數據 vs 資料) belong to a review pass, not to a silent substitution.

Two surfaces stay out of scope on purpose: the seat brief written by `adjudicate --brief-out` is the experimental stimulus — translating it would change what the recorded verdicts measure, so it stays Chinese byte for byte. And `--help` is a fixed bilingual table (English term plus Chinese gloss) rather than a per-language render: a flag you half-guessed should read the same either way.

## The order inside `apply`, and what a half-way break leaves behind

A torn state — store updated, file not updated — hurts more than a crash. So the order is fixed, and it is not negotiable:

```
① back up + read back + compare hash   ② write a staging file (original untouched)
③ write the journal <records>.journal-<batch>   ④ atomic rename (os.replace)
⑤ commit the transaction   ⑥ delete the journal
```

Both breakpoints have a recovery path that `selfcheck` exercises:

| Breakpoint | What you find | What to do |
|---|---|---|
| after ④, before ⑤ | file merged, store has no audit row | `somnians recover` writes the audit from the journal; `rollback` then works normally |
| after ③, before ④ | file untouched, journal present | `somnians recover` decides "never took effect", drops the journal, changes nothing |

`recover` trusts fingerprints, not `is_deleted`: the journal records the sha256 of the file before and after the batch. Equals the "after" hash ⇒ the file was renamed and the audit is missing ⇒ backfill. Equals the "before" hash ⇒ nothing took effect ⇒ drop the journal. Neither ⇒ unknown state: write nothing, delete nothing, exit code 5. If the batch's audit rows are already committed, it only drops the journal — running it again is a no-op.

`rollback` uses the same staging discipline: it fsyncs the complete restored JSONL before atomically replacing the records file, then commits the audit transaction. If an ordinary pre-commit error occurs, it rolls back SQLite and atomically restores the original file. A batch that already has an `op=rollback` audit row is a no-op on repeat. This protects handled errors; it is not a crash-recovery journal for rollback.

## Guards and exit codes

Before touching the store, several inputs are rejected up front:

- **Batch reuse**: a batch that already has a `soft_delete` or `rollback` audit row cannot be applied again.
- **Batch name**: only `[A-Za-z0-9][A-Za-z0-9._-]{0,127}`; `..`, `/`, `\` and newlines are rejected, so a name cannot escape the records directory.
- **Input JSONL**: a malformed line, a non-object line or a missing required field is reported with file and line number; no backup or staging file is written.
- **Adapter failure**: a seat command that cannot start (missing file, permission error) leaves its group undecided for retry instead of crashing the round.
- **Missing record on rollback**: an audit row pointing at an ID no longer in the file refuses the rollback and writes no rollback row.

Exit codes: `0` success · `1` nothing to restore · `2` invalid input or batch, reused batch, missing record, or groups left undecided after retry · `3` backup self-check failed · `4` injected fault (self-check only) · `5` recover cannot tell the file's state.

### An adapter can be one shell script

```bash
#!/usr/bin/env bash
# my-seat.sh — anything that can read a brief and answer verdicts: curl, a local model, another agent
BRIEF="$1"
curl -s https://your-endpoint/v1/chat/completions \
  -H "Authorization: Bearer $YOUR_KEY" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"model":"your-model","messages":[{"role":"user","content":open(sys.argv[1]).read()}]}))' "$BRIEF")" \
| python3 -c 'import json,sys;print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

**You fill in the model yourself.** That is where vendor decoupling lives: one brief goes in, n lines of `ID｜并`/`ID｜不并` come out, and who answers it is not baked into the repo.

## Why the default threshold is 0.62, not 0.75

Records are short. A near-duplicate that differs by one character or two drops to around 0.5 under 3-gram Jaccard. So the score is `max(3-gram Jaccard, character-sequence similarity)` and the threshold stays low to collect more candidates.

**Scan over-collects; the seat rejects.** A two-stage split that one threshold cannot replace.

## Large stores: inverted index, plus a ruler you can re-run

`scan` prunes candidates with a 3-gram inverted index by default. **Scoring is unchanged** (still `max(3-gram Jaccard, sequence similarity)`):

| Data | Full pairwise `--exact` | Inverted (default) | Candidate pairs | Identical? |
|---|---|---|---|---|
| Real store, 3,201 records | **174.6 s** | **14.5 s** | 808 | pair by pair, score by score |
| Synthetic 3,120 (many isomorphic short lines) | 82.4 s | 7.0 s | 80,114 | hits the cap; the number is not usable as-is |

How to reproduce (measured on one Mac, 2026-11-18):

```bash
python3 scripts/make_bench.py --n 3120 > /tmp/bench.jsonl    # the synthetic row
./somnians scan --in /tmp/bench.jsonl --out /tmp/a.jsonl --exact     # slow ruler
./somnians scan --in /tmp/bench.jsonl --out /tmp/b.jsonl             # inverted
```

`--exact` is the ruler: re-check any speed-up against it. A speed-up without that row is not a result.

`--cap` (default 500) is the high-frequency gate — a 3-gram whose posting list is longer than that stops contributing pairs, and **the moment it triggers, a warning is printed**: the real store's largest posting list is 362, so nothing was skipped; the synthetic distribution does skip, and there `--exact` or a bigger `--cap` is the only honest answer.

## What this does not do

- ⛔ Does not touch your storage: reads JSONL, writes JSONL plus one audit table
- ⛔ Does not commit on its own: `apply` is run by a human; `adjudicate` only produces verdicts
- ⛔ Does not deduplicate at write time: that is mem0 / LangMem's job; this handles the existing pile
- ⛔ Does not lock you to a vendor: the adapter is your script; the repo ships no vendor client
- ⛔ Ships no private memory: `data/public-cases.jsonl` is entirely synthetic traps

## Concurrency and truncation

Free and small-model seats often cut off mid-stream. `adjudicate` **fills gaps only** instead of rerunning the batch:

```
round 1: 1/2 groups (concurrency 1)
retry 1: resend the 1 missing group → G02
verdicts 2/2 groups → decisions.jsonl
```

When retries run out and groups are still missing: **exit code 2**, and those groups are written as `未判` (undecided) in decisions — never silently recorded as "keep apart".

`--jobs 3` splits candidates by group and dispatches concurrently; the seats do not affect each other. A single seat's timeout is handled by `--timeout`.

## Seat identity

A seat command can silently fall back to a default model (quota exhausted, endpoint unavailable, "using auto"). `adjudicate` scans the seat's output and stderr for those traces; if one matches, the seat's verdicts are **not counted** and the group is left missing for a retry, rather than recorded under a model that never actually answered. The trace is reported in the round output.

## Files

CI runs the standard-library unit suite, `selfcheck`, the offline demo, and indexed-vs-exact reconciliation on Ubuntu, macOS, and Windows with Python 3.9, 3.11, and 3.13. The `quality-gate` check is the single aggregate status for the full matrix.

```
somnians                    # zero-install entry (run straight from the repo)
.github/workflows/selfcheck.yml  # CI: 3 OSes × Python 3.9/3.11/3.13; quality-gate aggregates the matrix
tests/test_cli.py            # stdlib unittest coverage for core behavior and rollback atomicity
scripts/check_bench.py       # portable synthetic indexed-vs-exact CI check
scripts/make_bench.py       # synthetic stress data (reproduces the timings above)
examples/seat.py            # seat adapter example (returns fixed verdicts without an endpoint; pipeline only)
src/somnians/cli.py         # implementation: one file, no dependencies (stdlib + sqlite3)
src/somnians/data/
  public-cases.jsonl        # public gold set, 26 cases (traps + canary, no private content)
  recorded/                 # two seats' recorded verdicts (IDs and verdicts only, no record text)
  sample-records.jsonl      # 8 runnable samples
pyproject.toml              # for pipx / pip install; data installs with the package
LICENSE                     # MIT
README.zh-CN.md             # Chinese original of this file
CONTRIBUTING.zh-CN.md       # Chinese original of CONTRIBUTING
CHANGELOG.zh-CN.md          # Chinese original of CHANGELOG
```

## Name

Chinese name **蝶花半梦**, Latin *Viola Somnians*, identifier `somnians` everywhere.

Read literally, 蝶花半梦 is *butterfly-flower, half-dream*: the butterfly takes the flower for the thing it loves; the half-dream is the stretch before waking. The mechanism answers to the same image — **two records close enough to merge, but not yet beyond doubt, are a half-dream; a half-dream is not merged**. The name stays in the title; readers of other languages can treat it as flavour.

`Viola` is the violet genus; read the Latin as *the dreaming violet*. The Chinese text never names the plant — one image, not a botanical footnote.

The image has a second layer this tool does **not** wire: 庄周梦蝶 — writer and written, or whether a record came from the agent's own sleep or from input that actually happened. There is no criterion for that here, because the tool never looks at provenance: it compares text. The blank is deliberate, not a to-do.

Every identifier stays ASCII — see the naming table in [CONTRIBUTING.md](CONTRIBUTING.md#the-name-has-three-layers).

## Where the criterion came from

The criterion and the pre-filter both come from one real incident on 2026-11-17: two of four seats read "drop is missing a word" as "keep apart" (direction reversed), and chatter like `全批。` got merged into body text. Both became canaries. **The failing cases in the gold set are pitfalls already stepped in, not invented exercises.**

The seat-identity check comes from a second incident: a seat labeled a named model silently fell back to the default model (quota exhausted, endpoint unavailable), and its verdicts were counted under the label that never actually answered.

## When to come back and edit this file

- A second seat reverses direction on a criterion that was "obvious" → add the case to the gold set first, then fix the wording here.
- Someone reads the CLI as "a library with a thin wrapper" → the "The artifact is a CLI" paragraph failed; rewrite it with the actual install line.
- `--exact` and the inverted index disagree on one pair → stop publishing timings until they agree again.
- Someone proposes a second criterion, or one more metaphor layer, for this tool → answer two questions first: does that information change a merge/keep decision, and can it be read from the input JSONL without a guess? Two "no"s mean it does not belong here.
- A new subcommand lands → update "Seven subcommands", the file tree, and CONTRIBUTING's subcommand row in the same commit.

---

© 2026 L4ST-afk · MIT License
