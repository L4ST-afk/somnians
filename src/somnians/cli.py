#!/usr/bin/env python3
"""somnians · 蝶花半梦（Viola Somnians）

对已有记忆条目做「存量去重」：扫同义候选 → 由你指定的席位复判 → 单事务软删 → 按批回滚。
判据只有一条：**并的代价 = 丢掉 drop 里 keeper 没有的信息。**

子命令：
  demo        离线复放两席已录判决，立刻出读数（不联网、不需要任何 key）
  scan        扫 records.jsonl 产候选组
  adjudicate  生成 brief，交给你的席位命令，收判决
  apply       单事务软删 + 写审计表
  rollback    按批一行还原
  recover     apply 断在半路时的恢复（按文件真实状态判定）
  selfcheck   15 项离线自检

契约（JSONL，不碰你的库）：
  records.jsonl   {"id":"...","text":"...","is_deleted":false}
  candidates.jsonl{"group":"G01","keeper":"id","drop":"id","jaccard":0.83,...}
  decisions.jsonl {"group":"G01","verdict":"并"|"不并"}

本文件零依赖、只用标准库。⛔ 不写任何外部服务。
"""
import argparse
import concurrent.futures
import difflib
import errno
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import tempfile
import time
from collections import Counter

try:                      # 包内导入（pip 装的那种）
    from .i18n import LANGS, catalog_gaps, resolve_lang, resolve_ok, set_lang, t
except ImportError:       # 直接 python3 src/somnians/cli.py 时
    from i18n import LANGS, catalog_gaps, resolve_lang, resolve_ok, set_lang, t

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.environ.get("SOMNIANS_DATA") or os.path.join(HERE, "data")
# 数据根可显式覆盖（SOMNIANS_DATA）；默认是包内 data，pip 安装后同样成立。
SEATS = {"seat-a": "seat-a.txt", "seat-b": "seat-b.txt"}

# ---------------------------------------------------------------- 判据与解析


def norm(s):
    """归一化：去标点空白，只留汉字字母数字。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s or "")


def parse_verdicts(text, ids):
    """宽松解析席位输出 → {id: '并'|'不并'}"""
    got = {}
    for line in text.splitlines():
        m = re.match(r"\s*[`*>\-]*\s*([RTCG]\d{2,3})", line)
        if not m or m.group(1) not in ids:
            continue
        seg = line[m.end():]
        if re.search(r"不\s*并|不合并|不\s*合|勿并|不应并", seg):
            got[m.group(1)] = "不并"
        elif re.search(r"并|合", seg):
            got[m.group(1)] = "并"
    return got


# ---------------------------------------------------------------- demo


def cmd_demo(args):
    cases = [json.loads(x) for x in open(os.path.join(DATA, "public-cases.jsonl"), encoding="utf-8")]
    ids = {c["id"] for c in cases}
    types = Counter(c["type"] for c in cases)
    print(t("demo.title", data=os.path.abspath(DATA)))
    print(t("demo.cases", n=len(cases),
            types=t("sep.list").join(f"{k}×{v}" for k, v in sorted(types.items()))))
    print(t("demo.note"))

    rows, verdicts = [], {}
    for name, fn in SEATS.items():
        got = parse_verdicts(open(os.path.join(DATA, "recorded", fn), encoding="utf-8").read(), ids)
        verdicts[name] = got
        scored = [c for c in cases if not c["trivial"]]
        right = [c for c in scored if got.get(c["id"]) == c["exp"]]
        merge = [c for c in scored if c["exp"] == "并"]
        wrong_no = [c for c in merge if got.get(c["id"]) == "不并"]
        can = [c for c in cases if c["type"].startswith("CANARY")]
        can_ok = all(got.get(c["id"]) == c["exp"] for c in can)
        acc = 100.0 * len(right) / max(1, len(scored))
        rows.append((name, len(right), len(scored), acc,
                     100.0 * len(wrong_no) / max(1, len(merge)), can_ok))

    print(t("demo.head"))
    for name, r, n, acc, rev, can_ok in rows:
        print(f"{name:<16}{f'{r}/{n}':>10}{f'{rev:.1f}%':>10}"
              f"{(t('demo.canary_ok') if can_ok else t('demo.canary_bad')):>9}   "
              f"{t('demo.usable') if can_ok else t('demo.void')}")

    a, b = list(SEATS)
    diff = [c["id"] for c in cases if verdicts[a].get(c["id"]) != verdicts[b].get(c["id"])]
    print(t("demo.diff", n=len(diff),
            ids=t("sep.list").join(diff) if diff else t("demo.none")))
    for cid in diff:
        c = next(c for c in cases if c["id"] == cid)
        print(t("demo.case", cid=cid, kind=c["type"], exp=c["exp"]))
        print(t("demo.keeper", k=c["K"]))
        print(t("demo.drop", d=c["D"]))
        print(t("demo.verdicts", a=a, va=verdicts[a].get(cid), b=b, vb=verdicts[b].get(cid)))
    print(t("demo.crit1"))
    print(t("demo.crit2"))
    print(t("demo.crit3"))
    return 0


# ---------------------------------------------------------------- scan


def shingles(text, k=3):
    t = norm(text)
    return {t[i:i + k] for i in range(max(0, len(t) - k + 1))} if len(t) >= k else ({t} if t else set())


def jaccard(a, b):
    A, B = shingles(a), shingles(b)
    if not A or not B:
        return 0.0
    return len(A & B) / len(A | B)


def similarity(a, b):
    """取两个尺度的较大值：3-gram Jaccard 与字符序列相似度。
    单用 3-gram 对「只改一两个字」的短条目过于苛刻（实测 0.5 上下），
    序列相似度更贴近人眼「像不像同一条」。"""
    return max(jaccard(a, b), difflib.SequenceMatcher(None, norm(a), norm(b)).ratio())


def _grams(t, n=3):
    """切分只有一处实现（shingles）；这里只是别名，别另起一套。"""
    return shingles(t, n)


def _pairs_exact(live):
    """O(n²) 基线，也作为 --exact 的对照路径。"""
    for i in range(len(live)):
        for j in range(i + 1, len(live)):
            yield i, j


def _pairs_indexed(live, cap=500):
    """3-gram 倒排缩候选：只产生「至少共用一个 3-gram」的配对，判分仍走 similarity()。
    cap 是高频道闸：posting 长度超过 cap 的 gram 不作为配对来源（多条目共有的通用写法）。
    ⛔ cap 被触发就会漏配——所以默认给到 500（真库 3201 条最大 posting 362，实际零跳过），
       并在跳过时打印告警，让人知道该用 --exact 复核。"""
    idx = {}
    for k, r in enumerate(live):
        for g in _grams(norm(r["text"])):
            idx.setdefault(g, []).append(k)
    skipped = [g for g, ks in idx.items() if len(ks) > cap]
    if skipped:
        print(t("scan.cap", n=len(skipped), cap=cap), file=sys.stderr)
    n = len(live)
    seen = set()
    for g, ks in idx.items():
        if len(ks) < 2 or len(ks) > cap:
            continue
        for a in range(len(ks)):
            ia = ks[a]
            for b in range(a + 1, len(ks)):
                ib = ks[b]
                key = ia * n + ib          # 整数键比元组快一截
                if key in seen:
                    continue
                seen.add(key)
                yield ia, ib


def match(a, b, thresh):
    """相似度 ≥ thresh 则回分数，否则回 None。
    分支顺序：先算便宜的 jaccard；再用 difflib 理论上界的长度判据，
    上界都不到阈值就不必跑 O(n²) 的序列比对（只跳过「必然低于阈值」的配对，不改结果）。"""
    na, nb = norm(a), norm(b)
    j = jaccard(a, b)
    bound = 2.0 * min(len(na), len(nb)) / max(1, len(na) + len(nb))
    if j < thresh and bound < thresh:
        return None            # 两个尺度的上界都不到阈值：必然落选，不必比对
    r = difflib.SequenceMatcher(None, na, nb).ratio()
    s = max(j, r)              # 与 similarity() 同口径，分数不变
    return s if s >= thresh else None


def cmd_scan(args):
    recs = [json.loads(x) for x in open(args.inp, encoding="utf-8") if x.strip()]
    live = [r for r in recs if not r.get("is_deleted")]
    print(t("scan.read", n=len(recs), live=len(live), thresh=args.thresh,
            mode=t("scan.mode_exact") if args.exact else t("scan.mode_index")))
    pairs = []
    for i, j in (_pairs_exact(live) if args.exact else _pairs_indexed(live, args.cap)):
        s = match(live[i]["text"], live[j]["text"], args.thresh)
        if s is not None:
            a, b = live[i], live[j]
            keeper, drop = (a, b) if len(norm(a["text"])) >= len(norm(b["text"])) else (b, a)
            pairs.append({"keeper": keeper["id"], "drop": drop["id"], "score": round(s, 4),
                          "keeper_text": keeper["text"], "drop_text": drop["text"]})
    out = []
    for n, p in enumerate(pairs, 1):
        p["group"] = f"G{n:02d}"
        out.append(p)
    with open(args.out, "w", encoding="utf-8") as f:
        for p in out:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    print(t("scan.out", n=len(out), out=args.out))
    return 0


# ---------------------------------------------------------------- adjudicate

BRIEF_HEAD = """你在判「两条记忆条目该不该并成一条」。逐组判决，不要解释。

## 第一步：先过滤「根本不是条目」的东西
批注/状态词（全批、同意、收到、OK、负一：…）、归一化后不足 8 字且无谓语、
纯标点/数字/表情、回执语（已处理） ⇒ 一律判「不并」。这类不是同一类问题：
它没有内容可丢，并进 keeper 只会污染正文。

## 第二步：判据（过滤之后才用）
并的代价 = **丢掉 drop 里 keeper 没有的信息**。
- drop 比 keeper 多东西（一条限定/例外/并列对象/不同数值/相反语气）⇒ 不并
- drop 比 keeper 少东西（压缩写法/残句/缺修饰/词序不同/多一个介词）⇒ 并

⛔ 别按「两条像不像」判。⛔ 别把「drop 缺词」当成「不并」的理由——那是方向读反。

## 输出（只允许这个）
每组一行：`G01｜并` 或 `G01｜不并`。末行 `【并】n/【不并】m`。
"""


def _brief_for(cands):
    body = [BRIEF_HEAD, f"## 待判 {len(cands)} 组\n"]
    for c in cands:
        body += [f"### {c['group']}", f"- keeper：{c['keeper_text']}", f"- drop：{c['drop_text']}", ""]
    return "\n".join(body)


def _decode(b):
    """席位回执可能是 utf-8，也可能是本机 locale（GBK）；都认，解不出就替换。"""
    if isinstance(b, str):
        return b
    for enc in ("utf-8", "gb18030"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", "replace")


def _call_adapter(adapter, brief, timeout, ids):
    """调一次席位；失败/超时回空字典（调用方据此走重试）。"""
    fd, path = tempfile.mkstemp(suffix=".md", prefix="somnians-brief-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(brief)
        r = subprocess.run(adapter + [path], capture_output=True, timeout=timeout)
        out, err = _decode(r.stdout), _decode(r.stderr)
        if r.returncode != 0:
            return {}, (err or "")[-300:]
        return parse_verdicts(out, ids), ""
    except subprocess.TimeoutExpired:
        return {}, "超时"
    finally:
        os.unlink(path)


def cmd_adjudicate(args):
    cands = [json.loads(x) for x in open(args.inp, encoding="utf-8") if x.strip()]
    ids = {c["group"] for c in cands}
    brief = _brief_for(cands)
    if args.brief_out:
        open(args.brief_out, "w", encoding="utf-8").write(brief)
    if not args.adapter:
        print(t("adj.brief", out=args.brief_out))
        return 0

    jobs = max(1, min(args.jobs, len(cands) or 1))
    chunks = [cands[i::jobs] for i in range(jobs)] if jobs > 1 else [cands]
    got, notes = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_call_adapter, args.adapter, _brief_for(ch),
                          args.timeout, {c["group"] for c in ch}) for ch in chunks if ch]
        for f in concurrent.futures.as_completed(futs):
            v, err = f.result()
            got.update(v)
            if err:
                notes.append(err)
    print(t("adj.r1", got=len(got), ids=len(ids), jobs=jobs)
          + (t("adj.r1_fail", n=len(notes)) if notes else ""))

    # 截断恢复：只把缺的组重发，最多 retry 轮
    for rd in range(1, args.retry + 1):
        miss = [c for c in cands if c["group"] not in got]
        if not miss:
            break
        print(t("adj.retry", rd=rd, n=len(miss),
                ids=", ".join(c["group"] for c in miss[:8])) + ("…" if len(miss) > 8 else ""))
        v, err = _call_adapter(args.adapter, _brief_for(miss), args.timeout,
                               {c["group"] for c in miss})
        got.update(v)
        if err:
            print(t("adj.retry_err", err=err))
    miss = sorted(ids - set(got))
    with open(args.out, "w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps({**c, "verdict": got.get(c["group"], "未判")}, ensure_ascii=False) + "\n")
    print(t("adj.out", got=len(got), ids=len(ids), out=args.out)
          + (t("adj.out_miss", ids=", ".join(miss)) if miss else ""))
    return 0 if not miss else 2


# ---------------------------------------------------------------- apply / rollback

DDL = """
CREATE TABLE IF NOT EXISTS audit_merge(
  old_id TEXT, keeper_id TEXT, batch TEXT, jaccard REAL, kind TEXT, created_at TEXT,
  PRIMARY KEY(old_id, batch));
CREATE TABLE IF NOT EXISTS audit_change(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, entry_id TEXT, op TEXT, batch TEXT,
  undo_json TEXT, created_at TEXT);
"""


def _db(path):
    con = sqlite3.connect(path)
    con.executescript(DDL)
    return con


def _fault():
    """故障注入：只在自检里用，模拟两个崩溃点。"""
    return os.environ.get("SOMNIANS_FAULT", "")


def _journal_path(records, batch):
    return f"{records}.journal-{batch}"


def cmd_apply(args):
    recs = [json.loads(x) for x in open(args.records, encoding="utf-8") if x.strip()]
    decs = [json.loads(x) for x in open(args.decisions, encoding="utf-8") if x.strip()]
    by_id = {r["id"]: r for r in recs}
    batch = args.batch or time.strftime("dream-%Y%m%d")
    merged, skipped = [], []
    for d in decs:
        if d.get("verdict") != "并":
            skipped.append(d["group"])
            continue
        if d["drop"] not in by_id or d["keeper"] not in by_id:
            skipped.append(d["group"] + "(缺条目)")
            continue
        drop = by_id[d["drop"]]
        if drop.get("is_deleted") and drop.get("merged_into") == d["keeper"]:
            skipped.append(d["group"] + "(已并过)")
            continue
        undo = {"id": drop["id"], "text": drop["text"], "is_deleted": drop.get("is_deleted", False)}
        drop["is_deleted"] = True
        drop["merged_into"] = d["keeper"]
        merged.append((d["drop"], d["keeper"], d.get("score"), batch, json.dumps(undo, ensure_ascii=False)))

    # ① 备份 + 自证可解（读回比 hash）：备份不是「文件还在」，是「能解回原物」
    bak = args.records + f".bak-{batch}"
    original = open(args.records, encoding="utf-8").read()
    with open(bak, "w", encoding="utf-8") as f:
        f.write(original)
    digest = hashlib.sha256(original.encode("utf-8")).hexdigest()
    if hashlib.sha256(open(bak, encoding="utf-8").read().encode("utf-8")).hexdigest() != digest:
        print(t("apply.backup_fail", bak=bak), file=sys.stderr)
        return 3
    print(t("apply.backup_ok", bak=bak, sha=digest[:12]))

    # ② 先落暂存文件（不碰原文件）
    staged = f"{args.records}.tmp-{batch}"
    with open(staged, "w", encoding="utf-8") as f:
        for r in recs:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())

    # ③ 写日志（崩溃恢复的唯一依据）：文件换了/库没提，靠它补齐
    jpath = _journal_path(args.records, batch)
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump({"batch": batch, "db": os.path.abspath(args.db),
                   "merges": [{"old": m[0], "keeper": m[1], "score": m[2],
                               "undo": json.loads(m[4])} for m in merged]},
                  f, ensure_ascii=False)
    if _fault() == "after_journal":
        print(t("apply.fault_j"), file=sys.stderr)
        return 4

    con = _db(args.db)
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        con.execute("BEGIN")
        for old, keeper, jac, b, undo in merged:
            con.execute("INSERT OR REPLACE INTO audit_merge VALUES(?,?,?,?,?,?)",
                        (old, keeper, b, jac, "batch", now))
            con.execute("INSERT INTO audit_change(entry_id,op,batch,undo_json,created_at) VALUES(?,?,?,?,?)",
                        (old, "soft_delete", b, undo, now))

        # ④ 原子换名（同一目录内 rename 是原子的），⑤ 再提交事务
        os.replace(staged, args.records)
        if _fault() == "after_replace":
            con.rollback()
            con.close()
            print(t("apply.fault_r"), file=sys.stderr)
            return 4
        con.commit()
    except Exception:
        con.rollback()
        con.close()
        os.unlink(staged) if os.path.exists(staged) else None
        print(t("apply.db_fail"), file=sys.stderr)
        raise
    con.close()
    os.unlink(jpath)

    print(t("apply.batch", batch=batch, n=len(merged), skipped=len(skipped))
          + (t("apply.batch_list", ids=", ".join(skipped[:6])) if skipped else ""))
    print(t("apply.audit", db=args.db, bak=bak))
    print(t("apply.undo", records=args.records, db=args.db, batch=batch))
    return 0


def cmd_recover(args):
    """崩溃恢复：日志在、库没提 ⇒ 按文件真实状态补审计或丢弃日志。"""
    jpath = args.journal or _journal_path(args.records, args.batch)
    if not os.path.exists(jpath):
        print(t("rec.none", jpath=jpath))
        return 0
    j = json.load(open(jpath, encoding="utf-8"))
    recs = [json.loads(x) for x in open(args.records, encoding="utf-8") if x.strip()]
    state = {r["id"]: bool(r.get("is_deleted")) for r in recs}
    touched = [m for m in j["merges"] if state.get(m["old"])]
    con = _db(args.db)
    if not touched:
        con.close()
        os.unlink(jpath)
        print(t("rec.discard", batch=j["batch"], n=len(j["merges"])))
        return 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    with con:
        for m in touched:
            con.execute("INSERT OR REPLACE INTO audit_merge VALUES(?,?,?,?,?,?)",
                        (m["old"], m["keeper"], j["batch"], m["score"], "recovered", now))
            con.execute("INSERT INTO audit_change(entry_id,op,batch,undo_json,created_at) VALUES(?,?,?,?,?)",
                        (m["old"], "soft_delete", j["batch"],
                         json.dumps(m["undo"], ensure_ascii=False), now))
    con.close()
    os.unlink(jpath)
    print(t("rec.backfill", batch=j["batch"], n=len(touched)))
    return 0


def cmd_rollback(args):
    con = _db(args.db)
    staged = original_stage = None
    directory = os.path.dirname(os.path.abspath(args.records))
    replaced = committed = fault_injected = post_commit_fault = False

    def stage(content, mode):
        fd, path = tempfile.mkstemp(prefix=".somnians-rollback-", dir=directory)
        try:
            os.chmod(path, mode)
            with os.fdopen(fd, "wb") as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())
        except BaseException:
            try:
                os.close(fd)
            except OSError:
                pass
            if os.path.exists(path):
                os.unlink(path)
            raise
        return path

    def sync_directory():
        if os.name == "nt":
            return
        unsupported = {
            errno.EINVAL,
            getattr(errno, "ENOTSUP", None),
            getattr(errno, "EOPNOTSUPP", None),
        }
        try:
            fd = os.open(directory, os.O_RDONLY)
        except OSError as error:
            if error.errno in unsupported:
                return
            raise
        try:
            try:
                os.fsync(fd)
            except OSError as error:
                if error.errno not in unsupported:
                    raise
        finally:
            os.close(fd)

    try:
        con.execute("BEGIN")
        rows = con.execute(
            "SELECT entry_id, undo_json, batch FROM audit_change "
            "WHERE op='soft_delete' AND batch=?",
            (args.batch,)).fetchall()
        if not rows:
            con.rollback()
            con.close()
            print(t("rb.none", batch=args.batch))
            return 1
        if con.execute(
                "SELECT 1 FROM audit_change WHERE op='rollback' AND batch=? LIMIT 1",
                (args.batch,)).fetchone():
            con.rollback()
            con.close()
            print(t("rb.already", batch=args.batch))
            return 0

        with open(args.records, "rb") as f:
            original_bytes = f.read()
        recs = [json.loads(line) for line in original_bytes.decode("utf-8").splitlines()
                if line.strip()]
        by_id = {r["id"]: r for r in recs}
        n = 0
        for old, undo_json, b in rows:
            undo = json.loads(undo_json)
            if old in by_id:
                by_id[old]["is_deleted"] = undo.get("is_deleted", False)
                by_id[old].pop("merged_into", None)
                n += 1

        mode = stat.S_IMODE(os.stat(args.records).st_mode)
        restored_bytes = "".join(
            json.dumps(r, ensure_ascii=False) + "\n" for r in recs
        ).encode("utf-8")
        original_stage = stage(original_bytes, mode)
        staged = stage(restored_bytes, mode)

        con.execute("DELETE FROM audit_merge WHERE batch=?", (args.batch,))
        for old, undo_json, b in rows:
            con.execute(
                "INSERT INTO audit_change(entry_id,op,batch,undo_json,created_at) "
                "VALUES(?,?,?,?,?)",
                (old, "rollback", b, undo_json, time.strftime("%Y-%m-%dT%H:%M:%S")))

        os.replace(staged, args.records)
        staged = None
        replaced = True
        sync_directory()
        if _fault() == "rollback_before_commit":
            fault_injected = True
            raise RuntimeError("injected rollback failure before commit")
        con.commit()
        if _fault() == "rollback_after_commit":
            post_commit_fault = True
            raise RuntimeError("injected interruption after rollback commit")
        committed = True
        con.close()
    except BaseException:
        rollback_error = None
        if not committed:
            if replaced and not con.in_transaction:
                try:
                    rollback_rows = con.execute(
                        "SELECT COUNT(*) FROM audit_change "
                        "WHERE op='rollback' AND batch=?",
                        (args.batch,)).fetchone()[0]
                    remaining_merges = con.execute(
                        "SELECT COUNT(*) FROM audit_merge WHERE batch=?",
                        (args.batch,)).fetchone()[0]
                    committed = rollback_rows == len(rows) and remaining_merges == 0
                except BaseException as error:
                    backup_path = original_stage
                    original_stage = None
                    con.close()
                    raise RuntimeError(
                        "rollback commit outcome is ambiguous; original records are preserved at "
                        f"{backup_path}") from error
            if not committed:
                try:
                    con.rollback()
                except BaseException as error:
                    rollback_error = error
            if replaced:
                if not committed:
                    try:
                        os.replace(original_stage, args.records)
                        original_stage = None
                        sync_directory()
                        replaced = False
                    except BaseException as restore_error:
                        con.close()
                        raise RuntimeError(
                            "rollback failed and the original records file could not be restored: "
                            f"{restore_error}") from restore_error
        con.close()
        if rollback_error:
            raise RuntimeError(
                f"rollback file restored, but the SQLite transaction could not be rolled back: "
                f"{rollback_error}") from rollback_error
        if post_commit_fault and committed:
            print(t("rb.commit_fault"), file=sys.stderr)
            return 4
        if fault_injected:
            print(t("rb.fault"), file=sys.stderr)
            return 4
        raise
    finally:
        for path in (staged, original_stage):
            if path and os.path.exists(path):
                os.unlink(path)

    print(t("rb.done", batch=args.batch, n=n))
    return 0



# ---------------------------------------------------------------- selfcheck


def _selfcheck_line(cond, msg):
    line = ("[OK] " if cond else "[FAIL] ") + msg
    encoding = getattr(sys.stdout, "encoding", None)
    if encoding:
        line = line.encode(encoding, errors="backslashreplace").decode(encoding)
    print(line)


def cmd_selfcheck(args):
    import contextlib
    import io
    import tempfile

    ok = True

    def line(cond, msg):
        nonlocal ok
        _selfcheck_line(cond, msg)
        ok = ok and bool(cond)

    cases_path = os.path.join(DATA, "public-cases.jsonl")
    sample_path = os.path.join(DATA, "sample-records.jsonl")
    cases = [json.loads(x) for x in open(cases_path, encoding="utf-8")] if os.path.exists(cases_path) else []
    ids = {c["id"] for c in cases}
    line(len(cases) == 26, t("sc.data", root=os.path.abspath(DATA), n=len(cases)))

    for name, fn in SEATS.items():
        fp = os.path.join(DATA, "recorded", fn)
        got = parse_verdicts(open(fp, encoding="utf-8").read(), ids) if os.path.exists(fp) else {}
        can = [c for c in cases if c["type"].startswith("CANARY")]
        passed = [c for c in can if got.get(c["id"]) == c["exp"]]
        line(len(can) > 0 and len(passed) == len(can),
             t("sc.seat", name=name, p=len(passed), c=len(can), g=len(got), ids=len(ids)))

    sample = ([json.loads(x) for x in open(sample_path, encoding="utf-8")]
              if os.path.exists(sample_path) else [])
    live = [r for r in sample if not r.get("is_deleted")]

    def _set(gen, thresh=0.62):
        out = {}
        for i, j in gen:
            sc = match(live[i]["text"], live[j]["text"], thresh)
            if sc is not None:
                a, b = sorted([live[i]["id"], live[j]["id"]])
                out[(a, b)] = round(sc, 4)
        return out

    idx = _set(_pairs_indexed(live, 10**6))
    exc = _set(_pairs_exact(live))
    line(bool(live) and idx == exc, t("sc.index", n=len(exc)))

    if not live:
        print(t("sc.missing"))
        return 1

    with tempfile.TemporaryDirectory() as d:
        db = os.path.join(d, "a.db")
        con = _db(db)
        cols = lambda t: {r[1] for r in con.execute(f"PRAGMA table_info({t})")}
        m, c = cols("audit_merge"), cols("audit_change")
        con.close()
        line({"old_id", "keeper_id", "batch", "jaccard", "kind", "created_at"} <= m,
             t("sc.merge_cols"))
        line({"entry_id", "op", "batch", "undo_json", "created_at"} <= c,
             t("sc.change_cols"))

        recs = os.path.join(d, "recs.jsonl")
        open(recs, "w", encoding="utf-8").write(
            "\n".join(json.dumps({**r, "source": "export-a"}, ensure_ascii=False)
                      for r in sample))
        dec = os.path.join(d, "dec.jsonl")
        kt = {r["id"]: r["text"] for r in live}
        with open(dec, "w", encoding="utf-8") as f:
            for n, (a, b) in enumerate(sorted(exc), 1):
                keeper = a if len(norm(kt[a])) >= len(norm(kt[b])) else b
                drop = b if keeper == a else a
                f.write(json.dumps({"group": f"G{n:02d}", "keeper": keeper, "drop": drop,
                                    "score": exc[(a, b)], "verdict": "并",
                                    "keeper_text": kt[keeper], "drop_text": kt[drop]},
                                   ensure_ascii=False) + "\n")

        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            rc_apply = cmd_apply(argparse.Namespace(records=recs, decisions=dec,
                                                    db=db, batch="selfcheck"))
        state = {json.loads(x)["id"]: json.loads(x).get("is_deleted", False)
                 for x in open(recs, encoding="utf-8")}
        line(rc_apply == 0 and any(state.values()),
             t("sc.apply", n=sum(bool(v) for v in state.values()), rc=rc_apply))
        # 文案三语不同，断言只认 ASCII 令牌（sha256= 在三种语言里都在）
        line("sha256=" in log.getvalue(), t("sc.backup"))

        with contextlib.redirect_stdout(log):
            rc_rb = cmd_rollback(argparse.Namespace(records=recs, db=db, batch="selfcheck"))
        state = {json.loads(x)["id"]: json.loads(x).get("is_deleted", False)
                 for x in open(recs, encoding="utf-8")}
        con = _db(db)
        left = con.execute("SELECT COUNT(*) FROM audit_merge").fetchone()[0]
        con.close()
        line(rc_rb == 0 and not any(state.values()) and left == 0,
             t("sc.rollback", n=left))
        # 契约节承诺「未点名字段整行原样带过」，这条把它钉成可跑断言（A＋ 那一半）
        kept = all(json.loads(x).get("source") == "export-a"
                   for x in open(recs, encoding="utf-8"))
        line(kept, t("sc.passthrough", n=len(sample)))

        # 6 崩溃点 A：文件已换名、库刚回滚（最常见的撕裂）
        crash = os.path.join(d, "crash.jsonl")
        open(crash, "w", encoding="utf-8").write(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in sample))
        db2 = os.path.join(d, "c.db")
        os.environ["SOMNIANS_FAULT"] = "after_replace"
        try:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc_a = cmd_apply(argparse.Namespace(records=crash, decisions=dec,
                                                    db=db2, batch="crashA"))
        finally:
            os.environ.pop("SOMNIANS_FAULT", None)
        con = _db(db2)
        rows = con.execute("SELECT COUNT(*) FROM audit_merge").fetchone()[0]
        con.close()
        st = {json.loads(x)["id"]: bool(json.loads(x).get("is_deleted"))
              for x in open(crash, encoding="utf-8")}
        line(rc_a == 4 and rows == 0 and any(st.values()),
             t("sc.crashA", n=sum(st.values()), rc=rc_a))
        with contextlib.redirect_stdout(log):
            cmd_recover(argparse.Namespace(records=crash, db=db2, batch="crashA", journal=None))
        con = _db(db2)
        rows = con.execute("SELECT COUNT(*) FROM audit_merge").fetchone()[0]
        con.close()
        line(rows == len(exc), t("sc.recover", n=rows, total=len(exc)))
        before_fault = open(crash, "rb").read()
        os.environ["SOMNIANS_FAULT"] = "rollback_before_commit"
        try:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc_rb_fault = cmd_rollback(
                    argparse.Namespace(records=crash, db=db2, batch="crashA"))
        finally:
            os.environ.pop("SOMNIANS_FAULT", None)
        fault_file_unchanged = open(crash, "rb").read() == before_fault
        con = _db(db2)
        fault_merges = con.execute(
            "SELECT COUNT(*) FROM audit_merge WHERE batch='crashA'").fetchone()[0]
        fault_rollbacks = con.execute(
            "SELECT COUNT(*) FROM audit_change WHERE op='rollback' AND batch='crashA'"
        ).fetchone()[0]
        con.close()
        fault_ok = (rc_rb_fault == 4 and fault_file_unchanged
                    and fault_merges == len(exc) and fault_rollbacks == 0)
        os.environ["SOMNIANS_FAULT"] = "rollback_after_commit"
        try:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc_rb2 = cmd_rollback(
                    argparse.Namespace(records=crash, db=db2, batch="crashA"))
        finally:
            os.environ.pop("SOMNIANS_FAULT", None)
        st = {json.loads(x)["id"]: bool(json.loads(x).get("is_deleted"))
              for x in open(crash, encoding="utf-8")}
        con = _db(db2)
        left2 = con.execute("SELECT COUNT(*) FROM audit_merge").fetchone()[0]
        rollback_rows = con.execute(
            "SELECT COUNT(*) FROM audit_change WHERE op='rollback' AND batch='crashA'"
        ).fetchone()[0]
        con.close()
        line(rc_rb2 == 4 and not any(st.values()) and left2 == 0,
             t("sc.crashA_end"))
        after_rollback = open(crash, "rb").read()
        with contextlib.redirect_stdout(log):
            rc_rb_repeat = cmd_rollback(
                argparse.Namespace(records=crash, db=db2, batch="crashA"))
        con = _db(db2)
        repeated_rows = con.execute(
            "SELECT COUNT(*) FROM audit_change WHERE op='rollback' AND batch='crashA'"
        ).fetchone()[0]
        con.close()
        line(fault_ok and rc_rb2 == 4 and rc_rb_repeat == 0
             and open(crash, "rb").read() == after_rollback
             and rollback_rows == len(exc) and repeated_rows == rollback_rows,
             t("sc.rollback_atomic"))

        # 7 崩溃点 B：日志写了、文件没换、库没提 ⇒ 恢复应丢弃日志，不做任何改写
        crash2 = os.path.join(d, "crash2.jsonl")
        open(crash2, "w", encoding="utf-8").write(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in sample))
        os.environ["SOMNIANS_FAULT"] = "after_journal"
        try:
            with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
                rc_b = cmd_apply(argparse.Namespace(records=crash2, decisions=dec,
                                                    db=db2, batch="crashB"))
        finally:
            os.environ.pop("SOMNIANS_FAULT", None)
        st2 = {json.loads(x)["id"]: bool(json.loads(x).get("is_deleted"))
               for x in open(crash2, encoding="utf-8")}
        jleft = os.path.exists(_journal_path(crash2, "crashB"))
        with contextlib.redirect_stdout(log):
            cmd_recover(argparse.Namespace(records=crash2, db=db2, batch="crashB", journal=None))
        line(rc_b == 4 and not any(st2.values()) and jleft
             and not os.path.exists(_journal_path(crash2, "crashB")),
             t("sc.crashB"))

    line(not catalog_gaps() and resolve_ok(), t("sc.i18n"))

    print("\nSELFCHECK_" + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


# ---------------------------------------------------------------- main


def main():
    p = argparse.ArgumentParser(prog="somnians", description="蝶花半梦 · in-place deduplication for stored memory (rollback by batch, always audited)")
    p.add_argument("--lang", choices=list(LANGS), metavar="LANG",
                   help="output language: en | zh-Hans | zh-Hant "
                        "(default: detected from SOMNIANS_LANG / LC_ALL / LC_MESSAGES / LANGUAGE / LANG)（输出语言；判不出落 en）")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("demo", help="replay two recorded seats offline and print the numbers（离线复放两席判决）")

    s = sub.add_parser("scan", help="scan for near-duplicate candidates（扫同义候选）")
    s.add_argument("--in", dest="inp", required=True, help="input records, JSONL")
    s.add_argument("--out", required=True, help="output candidates, JSONL")
    s.add_argument("--thresh", type=float, default=0.62)
    s.add_argument("--exact", action="store_true", help="full pairwise comparison, slow; use it to reconcile（全量对账用）")
    s.add_argument("--cap", type=int, default=500, help="cap on posting length per 3-gram; longer lists stop contributing pairs（高频道闸）")

    a = sub.add_parser("adjudicate", help="build the brief and call your seat command（生成 brief 并调席位）")
    a.add_argument("--in", dest="inp", required=True, help="output candidates, JSONL")
    a.add_argument("--out", required=True, help="output decisions, JSONL")
    a.add_argument("--adapter", nargs="+", help="seat command; receives the brief path as argv[1], prints verdict lines on stdout（席位命令）")
    a.add_argument("--brief-out", help="also keep a copy of the brief（brief 落盘）")
    a.add_argument("--jobs", type=int, default=1, help="number of seats to run in parallel, default 1（并发席位数）")
    a.add_argument("--retry", type=int, default=1, help="truncation recovery rounds; only missing groups are resent（截断恢复轮数）")
    a.add_argument("--timeout", type=int, default=900, help="wall-clock limit per seat, in seconds（单席上限）")

    ap = sub.add_parser("apply", help="soft-delete in one transaction, write the audit（单事务软删＋审计）")
    ap.add_argument("--records", required=True)
    ap.add_argument("--decisions", required=True)
    ap.add_argument("--db", default="somnians-audit.db")
    ap.add_argument("--batch")

    rec = sub.add_parser("recover", help="crash recovery: backfill audit from the journal, or discard a journal that never took effect（崩溃恢复）")
    rec.add_argument("--records", required=True)
    rec.add_argument("--db", default="somnians-audit.db")
    rec.add_argument("--batch", required=True)
    rec.add_argument("--journal", help="journal path, default <records>.journal-<batch>（日志路径）")
    sub.add_parser("selfcheck", help="offline self-check: data root, canary, optimization reconciliation, audit schema, apply/rollback round trip（离线自检）")
    rb = sub.add_parser("rollback", help="restore one batch（按批还原）")
    rb.add_argument("--records", required=True)
    rb.add_argument("--db", default="somnians-audit.db")
    rb.add_argument("--batch", required=True)

    args = p.parse_args()
    lang, warn = resolve_lang(args.lang)
    set_lang(lang)
    if warn:
        print(t(warn[0], tag=warn[1]), file=sys.stderr)
    return {"demo": cmd_demo, "scan": cmd_scan, "adjudicate": cmd_adjudicate,
            "apply": cmd_apply, "rollback": cmd_rollback,
            "recover": cmd_recover, "selfcheck": cmd_selfcheck}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
