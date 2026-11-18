# 蝶花半梦 · 贡献规范

这个仓库小，规矩也少，但有两条必须先说清：**标识层一律 ASCII，中文只出现在人类可见的文案层**；**每份文档都有中英两版，改一版必须同改另一版**。

## 名字分三层

| 层 | 用哪个 | 允许出现在 |
|---|---|---|
| 中文雅名 | 蝶花半梦 | 标题、文档、口头 |
| 拉丁名 | *Viola Somnians* | 标题、文档 |
| 标识 | `somnians` | 目录、包、命令、变量、URL |

"蝶花半梦"直译是 *butterfly-flower, half-dream*：蝶把花认作所爱，半梦是没醒透的那一段。机制里对应那条判据——两条记录像到可以并、还没到证据确凿，就是半梦；**半梦不并**。名字留在标题里，也让非中文读者看一眼就记住。这层意象的第二层——庄周梦蝶，写入者与被写入者——故意不接：本工具从不读来源，写进文档就等于宣称一个不存在的能力。标识层一个汉字都不能有，不然 shell、CI、URL 三处都会坏。

## 命名表（改名前先查这张）

| 对象 | 规则 | 现值 |
|---|---|---|
| GitHub 仓库 | 全小写；多词用 `-`，不用 `_` | `somnians` |
| PyPI 包 | 全小写、无下划线、无空格 | `somnians` |
| Python 模块 | 小写、单 token、与包名同名 | `somnians`（`src/somnians/`） |
| CLI 命令 | 与包名同名 | `somnians` |
| 子命令 | 动词、小写、无连字符 | `demo` `scan` `adjudicate` `apply` `rollback` `recover` `selfcheck` |
| 长旗标 | 小写 kebab，`--` 前缀 | `--brief-out` `--records` `--decisions` |
| 环境变量 | 大写，`SOMNIANS_` 前缀 | `SOMNIANS_DATA` `SOMNIANS_FAULT` |
| 脚本 | snake_case，`.py` 后缀 | `scripts/make_bench.py` |
| 数据与示例 | 小写 kebab，`.jsonl` 后缀 | `public-cases.jsonl` `sample-records.jsonl` |
| SQL 表与列 | snake_case；落库后**永不改名** | `audit_merge(old_id, keeper_id, batch, jaccard, kind, created_at)` |
| 批号 | 自由字符串标签，由调用方给 | 示例沿用 `dream-YYYYMMDD` |
| 退出码 | 0 成功／2 有缺组／3 前置失败／4 故障注入 | 见 README |

四条硬规矩：

1. **表名与列名落库后不改**。审计链是累积证据，改一次列名，历史批次的回滚就断了。
2. **批号前缀不属于本项目**。上游记库里历史批次都叫 `dream-YYYYMMDD`，这里沿用；你接自己的库时叫什么都行，只要同批内唯一。
3. **中英两版同改**。英文正本是 `README.md` / `CONTRIBUTING.md` / `CHANGELOG.md`，中文原稿是同名的 `.zh-CN.md`。只改一边，另一边就成了过期读数。
4. **运行时文案三份目录同加，协议值永不翻译**。`src/somnians/i18n.py` 里 `en`／`zh-Hans`／`zh-Hant` 三份，加一条文案就在同一次编辑里补齐三份（缺一条 `selfcheck` 就报红）。判决值 `并`／`不并`／`未判`、`SELFCHECK_*` 令牌、数字、ID、路径、退出码在任何语言下都字节一致：翻了就等于把已经写好的库读坏。

## 文档体例（2026-11-18 借太玉洞）

这套体例搬自技能库那边的写作闸，四条：**反例优先、H1 带四字标签、有体量预算、留腐化信号**。

- **H1 形式**：`# <雅名> · <四字标签>`，如 `# 蝶花半梦 · 存量去重` / `# 蝶花半梦 · 贡献规范`。标签只作货架可读，⛔ 不进包名、⛔ 不建索引页。
- **反例优先**：写一条规矩之前，先写它要避免的那次失败（哪一版、缺了什么、重来怎么改）。README 末尾「什么时候回来改这份文件」就是这些反例的存放处。
- **体量预算**：`README.md` ≤ 260 行、单个二级节 ≤ 45 行，`CONTRIBUTING.md` ≤ 120 行。超了先下沉到 `docs/`，再在 README 留一行指针。⛔ 靠删判据句来压行数。
- **腐化信号**：每份主要文档末尾列「出现什么迹象就回来改它」。没有这一节，文档只会越来越像墓志铭。

## 提交前

```bash
./somnians selfcheck          # 期望 SELFCHECK_PASS
python3 scripts/make_bench.py --n 400 > /tmp/b.jsonl && ./somnians scan --in /tmp/b.jsonl --out /tmp/c.jsonl
```

- 判据改动必须连带 `selfcheck` 的用例，否则等于没改（先让用例红，再让它绿）。
- 新增子命令：名字用动词，`--help` 里加一行，README 的七子命令段与文件树同一提交里改。
- 新增依赖：这里默认零依赖，加一个就要说清为什么标准库不够。
- 改文案：英文跑一遍 `fluensand check --doc`（浮沙言），中文稿同步改；⛔ 只改语感、⛔ 顺手改数字与阈值。
