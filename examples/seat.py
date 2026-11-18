#!/usr/bin/env python3
"""Minimal seat adapter example: reads a brief, answers "merge" per group, offline.（最小席位适配器）

Contract: argv[1] is the brief path; stdout is one line per group, `<ID>｜并` or `<ID>｜不并`.
Swap in a real model by turning this into one HTTP call; model name and key are yours.
（契约：argv[1]＝brief 路径；stdout 每行 `<ID>｜并`／`<ID>｜不并`。）
"""
import json
import os
import re
import sys
import urllib.request

BRIEF = sys.argv[1]
IDS = re.findall(r"^### ([RTCGUM]\d{2,3})", open(BRIEF, encoding="utf-8").read(), re.M)

ENDPOINT = os.environ.get("SEAT_ENDPOINT")      # 例：https://your-endpoint/v1/chat/completions
MODEL = os.environ.get("SEAT_MODEL")            # 例：your-model
KEY = os.environ.get("SEAT_KEY")

if ENDPOINT and MODEL and KEY:
    body = json.dumps({"model": MODEL, "messages": [
        {"role": "user", "content": open(BRIEF, encoding="utf-8").read()}]}).encode()
    req = urllib.request.Request(ENDPOINT, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {KEY}"})
    print(urllib.request.urlopen(req, timeout=600).read().decode("utf-8", "replace"))
else:
    # 没配端点就回一份固定判决，用来验证管路（不是判据，别拿它下结论）
    for gid in IDS:
        print(f"{gid}｜并")
