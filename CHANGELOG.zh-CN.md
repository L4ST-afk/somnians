# 蝶花半梦 · 变更记录

`[English](CHANGELOG.md) · [中文](CHANGELOG.zh-CN.md)`

## 0.1.2（2026-11-18）

- **数据文件去掉厂商名**：`data/recorded/perch.txt` → `seat-a.txt`，`qwen.txt` → `seat-b.txt`；`demo` 的席位行随之改为 `seat-a`／`seat-b`。读数不变（26/26、25/26）。
- **题图上 README**：两版顶部加 `docs/cover.jpg`（作者自制）。
- 无行为变更。

## 0.1.1 — 2026-11-18

- **运行时三语目录**：英文／简体／繁体，选取顺序 `--lang` > `SOMNIANS_LANG` > `LC_ALL` / `LC_MESSAGES` / `LANGUAGE` / `LANG`，判不出落英文；`C`／`POSIX` 跳过。
- **按契约不翻**：判决值 `并`／`不并`／`未判`、`SELFCHECK_*` 令牌、数字、ID、路径、退出码。
- **selfcheck 13 → 15 项**：一项断言三份目录键对齐、判定顺序成立（flag > env > locale > en）；另一项断言契约节那句「未点名字段原样带过」——带 `source` 的样例过 `apply` → `rollback` 后字段仍在。
- 文档三件套（README／CONTRIBUTING／CHANGELOG）同步加「语言」一节；中英两版必须同改（见 CONTRIBUTING）。

## 0.1.0 — 2026-11-18

首个可安装版本。

- **七个可执行项**：`demo`（离线复放两席已录判决）、`scan`、`adjudicate`、`apply`、`rollback`、`recover`、`selfcheck`。
- **apply 原子序**：备份并读回比 sha256 → 写暂存 → 写日志 → `os.replace` → 提交事务 → 删日志。两个断点（换名后崩、日志后崩）各有实测恢复路径，`recover` 按文件真实状态判定，不按日志存在判定。
- **审计两表**：`audit_merge`（谁并了谁、哪批、多少分）、`audit_change`（每步的 undo，含 rollback 自身留痕）。
- **scan 倒排**：3-gram posting 先在候选上剪枝，判分口径与全量 `--exact` 一致（真库 3201 条 174.6 s → 14.5 s，808 对逐对逐分相同）。
- **adjudicate 并发与截断恢复**：`--jobs` 切块并发、`--retry` 只重发缺组；缺组写「未判」并以退出码 2 报出，不当成「不并」。
- **selfcheck 13 项**：数据根显式、公开金标 canary、优化前后对账、审计 schema、apply/rollback 往返、两个崩溃点故障注入。
- **公开金标 26 组**：五类陷阱（canary／压缩失真／程度差异／对象差异／极性／非条目），伪造席在该集上 39.3%，用于自证判据有牙。
- **CI**：Python 3.9／3.11／3.13 三档，自检 + 读数 + 倒排对账。
