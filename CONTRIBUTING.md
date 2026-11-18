# somnians · 蝶花半梦

Contributing rules. The repo is small, so there are only a few — but two come before everything else: **identifiers stay ASCII, Chinese lives only in human-facing copy**, and **every document exists in two languages; change one, change the other in the same commit**.

`[English](CONTRIBUTING.md) · [中文](CONTRIBUTING.zh-CN.md)`

## The name has three layers

| Layer | What to use | Where it may appear |
|---|---|---|
| Chinese name | 蝶花半梦 | titles, docs, conversation |
| Latin name | *Viola Somnians* | titles, docs |
| Identifier | `somnians` | directories, package, commands, variables, URLs |

Read literally, 蝶花半梦 is *butterfly-flower, half-dream*: the butterfly takes the flower for the thing it loves; the half-dream is the stretch before waking. The criterion answers to the same image — two records close enough to merge, not yet beyond doubt, are a half-dream, and **a half-dream is not merged**. The name stays in the title so readers of other languages remember it. The image's second layer — 庄周梦蝶, writer versus written — stays deliberately unwired: the tool never reads provenance, so naming it would claim a capability that does not exist. The identifier layer carries no CJK at all: shell, CI and URLs break otherwise.

## Naming table (check it before renaming anything)

| Object | Rule | Current value |
|---|---|---|
| GitHub repo | lowercase; `-` between words, never `_` | `somnians` |
| PyPI package | lowercase, no underscores, no spaces | `somnians` |
| Python module | lowercase, single token, same as package | `somnians` (`src/somnians/`) |
| CLI command | same as package | `somnians` |
| Subcommands | verbs, lowercase, no hyphens | `demo` `scan` `adjudicate` `apply` `rollback` `recover` `selfcheck` |
| Long flags | lowercase kebab, `--` prefix | `--brief-out` `--records` `--decisions` |
| Env vars | uppercase, `SOMNIANS_` prefix | `SOMNIANS_DATA` `SOMNIANS_FAULT` |
| Scripts | snake_case, `.py` suffix | `scripts/make_bench.py` |
| Data and examples | lowercase kebab, `.jsonl` suffix | `public-cases.jsonl` `sample-records.jsonl` |
| SQL tables and columns | snake_case; **never renamed once shipped** | `audit_merge(old_id, keeper_id, batch, jaccard, kind, created_at)` |
| Batch id | free-form string label, supplied by the caller | examples keep `dream-YYYYMMDD` |
| Exit codes | 0 ok / 2 missing groups / 3 precondition failed / 4 injected fault | see README |

Four hard rules:

1. **Table and column names never change after shipping.** The audit chain is accumulated evidence; renaming a column cuts rollback for every historical batch.
2. **The batch-id prefix is not ours.** Upstream batches are labelled `dream-YYYYMMDD`, so examples keep that shape; when you point it at your own store, any label works as long as it is unique within the batch.
3. **Keep the two languages in step.** English is canonical (`README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`); the Chinese originals are the same names with `.zh-CN.md`. Change one side only and the other becomes a stale reading.
4. **Runtime copy lives in three catalogs, and protocol values are never translated.** `src/somnians/i18n.py` carries `en` / `zh-Hans` / `zh-Hant`; add a key to all three in the same edit (`selfcheck` fails on any gap). Verdict values `并` / `不并` / `未判`, the `SELFCHECK_*` tokens, numbers, IDs, paths and exit codes stay byte-identical in every language: translating them breaks every store already written.

## Document conventions

Four habits: **failure first, a four-character H1 label, a size budget, and decay signals**.

- **H1 form**: `# <name> · <four-character label>`, e.g. `# 蝶花半梦 · 存量去重` / `# 蝶花半梦 · 贡献规范`. The label is shelf-readable only — not part of the package name, not indexed.
- **Failure first**: before writing a rule, write the failure it exists to prevent — which version, what context was missing, what a redo would change. The README's closing section is where those failures live.
- **Size budget**: `README.md` ≤ 260 lines, one `##` section ≤ 45 lines, `CONTRIBUTING.md` ≤ 120 lines. Over budget → push detail into `docs/` and leave one pointer line. ⛔ Never buy lines by deleting criterion sentences.
- **Decay signals**: every major document ends with "when to come back and edit this". Without that section a document only becomes a tombstone.

## Before you commit

```bash
./somnians selfcheck          # expect SELFCHECK_PASS
python3 scripts/make_bench.py --n 400 > /tmp/b.jsonl && ./somnians scan --in /tmp/b.jsonl --out /tmp/c.jsonl
```

- A criterion change must come with its `selfcheck` case, or it did not happen (let the case go red first, then green).
- New subcommand: verb name, one line in `--help`, and the README's seven-subcommand section plus the file tree in the same commit.
- New dependency: this repo is zero-dependency by default; adding one means explaining why the standard library is not enough.
- Copy changes: change the tone only, never numbers or thresholds, and update the Chinese side in the same commit.
