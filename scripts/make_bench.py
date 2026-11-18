#!/usr/bin/env python3
"""Generate reproducible stress data (synthetic; contains no real memory).（造可复算压测数据）

Usage: python3 scripts/make_bench.py --n 3120 > /tmp/bench.jsonl
The two timing rows in the README come from this file plus one real store.
（README 那两行耗时＝它＋真库各跑一次。）
"""
import argparse, json, random

VERBS = ["归档", "提交", "部署", "导出", "备份", "巡检", "打包", "回滚", "对账", "同步"]
OBJS = ["AGENTS.md 文件", "数据库快照", "日志目录", "配置档", "审计表", "语料清单", "评审记录", "指标 JSON"]
CONDS = ["之前", "之后", "当天", "每周", "月底", "触发时", "上线前", "收工前"]
EXTRAS = ["并记录背景信息及遇到的问题", "且保留上一版备份", "除纯文档改动外", "只读写面不写", "并写明撤回命令", "遇到冲突先停"]

p = argparse.ArgumentParser()
p.add_argument("--n", type=int, default=3000)
p.add_argument("--dups", type=int, default=120, help="注入的完全重复条数")
p.add_argument("--seed", type=int, default=7)
a = p.parse_args()
random.seed(a.seed)

recs = []
for i in range(a.n):
    t = f"{random.choice(CONDS)}必须{random.choice(VERBS)}{random.choice(OBJS)}"
    if random.random() < 0.45:
        t += "，" + random.choice(EXTRAS)
    if random.random() < 0.18:
        t += f"（第{random.randint(1, 50)}条）"
    recs.append({"id": f"m{i}", "text": t, "is_deleted": False})
for k in range(a.dups):
    recs.append({"id": f"dup{k}", "text": random.choice(recs)["text"], "is_deleted": False})
for r in recs:
    print(json.dumps(r))
