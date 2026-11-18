# 蝶花半梦 · 存量去重（somnians · Viola Somnians）

`[English](README.md) · [中文](README.zh-CN.md)`

**对已有记忆条目做存量去重**：扫同义候选 → 由你指定的席位逐对复判 → 单事务软删 → 按批一行回滚。全程留审计。

mem0 / Zep / Letta 在写入那一刻就决定记不记。这一件处理另一摊：**已经沉淀下来的重复**——一批 3000 条里那些说了两遍、三遍、五遍的规矩。

**形态是一个 CLI。** 库要先有宿主，提示词要先有能跑提示词的入口；CLI 装完敲一行就出读数。七个子命令各自独立，接进谁的库都不用改那个库。

**命名**：中文雅名「蝶花半梦」，拉丁名 *Viola Somnians*（三色堇属 + 梦）；命令与包名统一用 `somnians`——PyPI 上这个名字未被占用，`viola` 已被占。

```
扫描 → 候选组 → 席位判决（并 / 不并）→ apply 软删 → rollback 按批还原
                                        └── audit_merge + audit_change 两表留痕
```

## 装，然后看读数

```bash
pipx install .        # 或 pip install .
somnians demo         # 离线复放两席已录判决：不联网、不需要任何 key

# 不想装也行：仓库内有个零安装入口，同样能跑
./somnians demo
```


```
公开金标 26 组：CANARY×2、COMPRESS×4、LIMIT×4、NONENTRY×5、OBJECT×4、POLARITY×4、VALUE×3

席位              准确率   方向反读   canary   判定
perch(auto)      26/26     0.0%       全过     可用
qwen3.8-flash    25/26     0.0%       全过     可用

两席分歧 1 组：T10 —— perch 判不并（对），qwen 判并（抹平了「消息 vs 邮件」的渠道差异）
```

**口径**：准确率＝与金标标签的一致率，分母 26（含 2 组 canary）；canary 任一不过则整份读数作废。它只是这两席在**这一套判据**上的可复现读数，跟「模型能力强弱」无关。

这两行是**自检**：换席位、改判据，先把这两行跑出来，再看剩下的话值不值得信。

## 判据只有一条

> **并的代价 = 丢掉 drop 里 keeper 没有的信息。**

- drop 比 keeper **多**东西（一条限定、一处例外、一个并列对象、一个不同的数值、相反语气）⇒ **不并**
- drop 比 keeper **少**东西（压缩写法、残句、缺修饰、词序不同、多一个介词）⇒ **并**
- 否定极性相反（一禁一许）⇒ **不并**

外加一层**前置过滤**（看结构，不看语义）：批注/状态词、8 字以下无谓语、纯标点数字表情、回执语 ⇒ 非条目，直接判「不并」并**列名回报**。这一层不能省——`全批。` 这类东西按判据反而"该并"，因为它没有信息可丢，并进 keeper 只会污染正文。

## 三个契约，不碰你的库

```jsonl
// records.jsonl —— 你把自己的记忆库导出成这个
{"id":"a1","text":"归档时必须包含 AGENTS.md 文件，并记录背景信息及遇到的问题","is_deleted":false}

// candidates.jsonl —— scan 产出，一对一行
{"group":"G01","keeper":"a1","drop":"a2","score":0.8421,"keeper_text":"…","drop_text":"…"}

// decisions.jsonl —— 席位判决
{"group":"G01","verdict":"并", ...}
```

不要求数据库、不要求 ORM、不要求 MCP host。导出 20 行代码就够。

这三个契约没点名的字段一律原样带过：`apply`／`rollback` 整行回写，只改 `is_deleted`（drop 另有 `merged_into`）。所以上游的 `source`／`source_client` 列可以搭车过来，本工具并不知道它是什么意思——这是透传，不是判据。这条由 `selfcheck` 盯着。

## 七个子命令

```bash
# 1. 扫候选（默认阈值 0.62，故意偏低：扫描管召回，判决管精确）
./somnians scan --in records.jsonl --out candidates.jsonl

# 2. 交给你的席位。适配器契约：命令收到 brief 路径作为 argv[1]，stdout 回 ID｜并/不并
./somnians adjudicate --in candidates.jsonl --out decisions.jsonl \
    --adapter ./my-seat.sh --brief-out brief.md \
    --jobs 3         # 三席并发，切块派发
    --retry 2        # 截断恢复：只把缺失的组重发，最多两轮

# 3. 落库（软删 + 写审计；原文件自动 .bak-<批号>）
./somnians apply --records records.jsonl --decisions decisions.jsonl --batch dream-20261118

# 4. 按批还原（一行，审计表保留 op=rollback 留痕）
./somnians rollback --records records.jsonl --batch dream-20261118

# 5. 崩溃恢复（只在 apply 半途断掉时才用得到；没日志就什么都不做）
./somnians recover --records records.jsonl --db somnians-audit.db --batch dream-20261118

# 6. 自检（离线、不联网）：数据根 / canary / 优化对账 / 审计 schema / apply-rollback 往返
./somnians selfcheck        # 期望 SELFCHECK_PASS，退出码 0

# 7. 离线复放两席已录判决（同「装，然后看读数」那一节）
./somnians demo
```

`apply` 写盘前会先做一次**备份自证**：把 `.bak-<批号>` 读回来算 sha256 与原文比对，不一致就在改写入前中止（退出码 3）。备份不是"文件还在就算数"。

## 语言（三语运行时）

运行时文案有三份目录：**英文／简体／繁体**。选取顺序是 `--lang` > `SOMNIANS_LANG` > `LC_ALL` / `LC_MESSAGES` / `LANGUAGE` / `LANG` > 英文。`C`、`POSIX`、空值跳过；认不出的标签落回英文，不猜。

```bash
./somnians demo                    # 跟着系统 locale 走
SOMNIANS_LANG=zh-Hant ./somnians demo
./somnians --lang en selfcheck
```

三样东西永不翻译：判决值 `并` / `不并` / `未判`（那是 decisions.jsonl 的契约，翻了会把别人的库读坏）、`SELFCHECK_PASS` / `SELFCHECK_FAIL` 两个令牌、以及所有数字、ID、路径与退出码。繁体是**静态目录**，不是运行时转写：CLI 零依赖、不联网，而简繁有一简对多繁（发→發/髮、干→乾/幹），运行时猜一次，读的人就得猜第二次。用词差异（數據／資料）留给评审，不做静默替换。

有两处**故意不跟着语言走**：`adjudicate --brief-out` 写出的席位 brief 是被测刺激物本身——翻它，就等于换掉录制判决所量的东西，所以一字不动留在中文；`--help` 是固定的双语表（英文词＋中文注），而不是按语言重排：一个你半猜着敲的旗标，在哪都该读出同一个意思。

## apply 的顺序，以及断在半路会发生什么

「库改了、文件没改」这类撕裂比崩溃本身更难受，所以顺序是固定的：

```
① 备份 + 读回比 hash   ② 写暂存文件（不碰原文件）
③ 写日志 <records>.journal-<batch>   ④ 原子换名（os.replace）
⑤ 提交事务   ⑥ 删日志
```

两个断点都有实测的恢复路径（`selfcheck` 会跑出来）：

| 断在哪 | 现场 | 怎么办 |
|---|---|---|
| ④ 之后、⑤ 之前 | 文件已并、库无审计 | `somnians recover` 按日志补审计，然后 `rollback` 正常可用 |
| ③ 之后、④ 之前 | 文件没动、日志在 | `somnians recover` 判定「未生效」，丢弃日志、不改任何数据 |

`recover` 看的是**文件到底换没换名**：日志在、文件没动，就不补审计。

### 适配器只要一个 shell 脚本

```bash
#!/usr/bin/env bash
# my-seat.sh —— 任何能读 brief、回判决的东西都行：curl、本地模型、另一个 agent
BRIEF="$1"
curl -s https://your-endpoint/v1/chat/completions \
  -H "Authorization: Bearer $YOUR_KEY" -H 'Content-Type: application/json' \
  -d "$(python3 -c 'import json,sys;print(json.dumps({"model":"your-model","messages":[{"role":"user","content":open(sys.argv[1]).read()}]}))' "$BRIEF")" \
| python3 -c 'import json,sys;print(json.load(sys.stdin)["choices"][0]["message"]["content"])'
```

**模型由你自己填**——这正是它跟厂商解耦的地方：协议是「一份 brief 进，n 行 `ID｜并` 出」，谁接不写死。

## 为什么阈值默认 0.62 而不是 0.75

条目大多很短，只改一两个字的近重复在 3-gram Jaccard 下会掉到 0.5 上下。所以这里取 `max(3-gram Jaccard, 字符序列相似度)`，再用低阈值多收。**扫描宁可多收（召回），判决负责拦（精确）**——两段式的分工不能被一个阈值替代。

## 大库怎么办：倒排 + 一把可复核的尺

`scan` 默认用 3-gram 倒排缩候选，**判分与分数完全不变**（还是 `max(3-gram Jaccard, 序列相似度)`）：

| 数据 | 全量两两 `--exact` | 倒排（默认） | 候选对数 | 是否一致 |
|---|---|---|---|---|
| 真实库 3201 条 | **174.6 s** | **14.5 s** | 808 | 逐对逐分一致 |
| 合成 3120 条（大量同构短句） | 82.4 s | 7.0 s | 80114 | 触发 cap，读数不可直接用 |

复算方式（数在 2026-11-18 本机测得，跑法见括号）：

```bash
python3 scripts/make_bench.py --n 3120 > /tmp/bench.jsonl    # 合成那行的数据
./somnians scan --in /tmp/bench.jsonl --out /tmp/a.jsonl --exact     # 慢尺
./somnians scan --in /tmp/bench.jsonl --out /tmp/b.jsonl             # 倒排
```

`--exact` 是那把尺：**任何一次提速都用它复核**，不看这行就别信提速。`--cap`（默认 500）是高频道闸——posting 超过它的 3-gram 不作为配对来源，**一被触发就打印告警**：真库最大 posting 362，实际零跳过；同构短句那种极端分布会跳过，那时只能 `--exact` 或调大 `--cap`。

## 不做什么

- ⛔ 不碰你的存储：只吃 JSONL、只吐 JSONL + 一张审计表
- ⛔ 不自动落库：`apply` 必须人执行，`adjudicate` 只产判决不写入
- ⛔ 不做写入时去重：那是 mem0 / LangMem 的活；这里只管存量
- ⛔ 不绑厂商：适配器是你自己的脚本，仓库不带任何厂商客户端
- ⛔ 不含任何私人记忆：`data/public-cases.jsonl` 全部是合成陷阱

## 并发与截断

免费/小模型席位常在中途断流。`adjudicate` 的处理是**只补缺的**，不重跑整份：

```
第一轮：1/2 组（并发 1）
重试 1：只补 1 组 → G02
判决 2/2 组 → decisions.jsonl
```

重试用尽仍缺时，**退出码 2**、缺组在 decisions 里写 `未判`——不会静默当成「不并」。
`--jobs 3` 会把候选按组切开并发派，三席互不影响；同一席超时由 `--timeout` 收。

## 文件

```
somnians                    # 零安装入口（仓库内直接跑）
.github/workflows/selfcheck.yml  # CI：3.9/3.11/3.13 跑自检、读数、倒排对账
scripts/make_bench.py       # 造压测数据（合成，可复算 README 的耗时）
examples/seat.py            # 席位适配器示例（不配端点就回固定判决，只验管路）
src/somnians/cli.py     # 实现，单文件、零依赖（标准库 + sqlite3）
src/somnians/data/
  public-cases.jsonl        # 公开金标 26 组（陷阱 + canary，无私人内容）
  recorded/                 # 两席已录判决（只有 ID 与判决，无记忆正文）
  sample-records.jsonl      # 8 条可试跑样本
pyproject.toml              # pipx / pip install 用，数据随包安装
LICENSE                     # MIT
README.zh-CN.md             # 本文件（英文正本在 README.md）
CONTRIBUTING.zh-CN.md       # CONTRIBUTING 的中文原稿
CHANGELOG.zh-CN.md          # CHANGELOG 的中文原稿
```

## 名字

中文雅名**蝶花半梦**，拉丁名 *Viola Somnians*，标识统一 `somnians`。

"蝶花半梦"直译是 *butterfly-flower, half-dream*：蝶把花认作所爱，半梦是没醒透的那一段。对应到机制就是那条判据——**两条记录像到可以并、但还没到证据确凿，就是半梦；半梦不并**。名字留在标题里，非中文读者可以当异国感看。

`Viola` 是堇菜（三色堇）属，拉丁名读作「做梦的三色堇」；中文正文不点植物名——留一个意象，不背一条植物注。

这层意象还有第二层，本工具**不接**：庄周梦蝶——写入者与被写入者，或者「这条记忆是它睡着时自己写的，还是外面真进来的」。这里没有它的判据，因为本工具从不看来源，只比正文。这块空白是刻意的，不是待办。

标识层一律 ASCII，规矩见 [CONTRIBUTING.zh-CN.md](CONTRIBUTING.zh-CN.md#名字分三层)。

## 出处

判据与「前置过滤」这两条，来自 2026-11-17 一次真实事故：四席里两席把「drop 缺词」读成「不并」（方向反读），另有 `全批。` 这种批注被并进正文。这两处都写进了 canary——**金标里那些不合格的组，每一组都是踩过的坑；没有一组是编出来的题**。

## 什么时候回来改这份文件

- 第二席在「想当然」的判据上又反读了 → 先把那组进金标，再回来改这里的措辞。
- 有人把 CLI 读成「加了壳的库」→ 上面「形态是一个 CLI」那一段没站住，拿真实安装行重写。
- `--exact` 与倒排在某一对上不一致 → 先停发所有耗时读数，等两边重新对齐。
- 有人要给本工具加第二条判据、或再配一层意象 → 先答两问：这条信息会不会改变并／不并的判决？它能不能从输入 JSONL 里确定拿到、不靠猜？两问都否 ⇒ 不属于这里。
- 新子命令落地 → 「七个子命令」、文件树、CONTRIBUTING 的子命令行同一提交里一起改。

---

© 2026 L4ST-afk · [@L4ST-afk](https://github.com/L4ST-afk) · MIT License
