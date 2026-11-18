#!/usr/bin/env python3
"""somnians · 运行时文案层（i18n）

三件事，都在这一层：

1. **三语目录**：`en` / `zh-Hans` / `zh-Hant`。三份键必须一一对齐（`catalog_gaps()` 查）。
2. **判定顺序**：`--lang` > `SOMNIANS_LANG` > `LC_ALL` / `LC_MESSAGES` / `LANGUAGE` / `LANG` > `en`。
   `C` / `POSIX` / 空值一律跳过；认不出的标签落回 `en`，不猜。
3. **什么不翻**：`并` / `不并` / `未判` 是 decisions.jsonl 的**协议值**，`SELFCHECK_PASS` 是
   机器令牌，退出码、ID、路径、JSON 一律不翻。翻协议值＝把别人的库读坏，那不是国际化。

⛔ 繁体是**静态目录**，不是运行时调模型转写：CLI 零依赖、不许联网，而且简繁有一简对多繁
（发→發/髮、干→乾/幹），运行时猜一次，读的人就得猜第二次。
"""

LANGS = ("en", "zh-Hans", "zh-Hant")

_ENV_ORDER = ("SOMNIANS_LANG", "LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG")
_SKIP = {"", "c", "c.utf-8", "posix", "c.utf8"}

_ZH_HANT_REGIONS = ("tw", "hk", "mo", "hant")
_ZH_HANS_REGIONS = ("cn", "sg", "my", "hans")

CATALOG = {
    "en": {
        "demo.title": "somnians demo · 蝶花半梦 (Viola Somnians) | data={data}",
        "sep.list": ", ",
        "demo.cases": "Public gold set: {n} cases — {types}",
        "demo.note": "(Cases built from private memory stay out of the public set; "
                     "every case here is a synthetic trap that is safe to publish)\n",
        "demo.head": "seat            acc      reverse     canary   verdict",
        "demo.canary_ok": "all pass",
        "demo.canary_bad": "failed",
        "demo.usable": "usable",
        "demo.void": "void",
        "demo.diff": "\nSeats disagree on {n} case(s): {ids}",
        "demo.none": "none",
        "demo.case": "  {cid} [{kind}] expected {exp}",
        "demo.keeper": "    keeper: {k}",
        "demo.drop": "    drop  : {d}",
        "demo.verdicts": "    {a}={va} / {b}={vb}",
        "demo.crit1": "\nThe criterion (there is only one): the price of a merge is "
                      "whatever the keeper loses from the drop.",
        "demo.crit2": "  drop says more than keeper (qualifier / exception / a second object / "
                      "a different number / reversed polarity) ⇒ keep apart",
        "demo.crit3": "  drop says less than keeper (compression / fragment / dropped modifier / "
                      "reordered words) ⇒ merge\nNo network needed: these are the two recorded "
                      "verdict sets shipped with the repo.",
        "scan.cap": "⚠ {n} 3-gram(s) exceed cap={cap} and were skipped (candidates may be missed); "
                    "use --exact or raise --cap if you need an exact answer",
        "scan.read": "Read {n} record(s), {live} live; threshold {thresh}; {mode}",
        "scan.mode_exact": "full pairwise comparison (--exact)",
        "scan.mode_index": "3-gram inverted index",
        "scan.out": "Candidates: {n} pair(s) → {out}",
        "adj.brief": "Brief written → {out} (no --adapter given; stopping here)",
        "adj.r1": "Round 1: {got}/{ids} group(s) (parallel {jobs})",
        "adj.r1_fail": "; {n} seat(s) failed",
        "adj.retry": "Retry {rd}: only {n} missing group(s) → {ids}",
        "adj.retry_err": "  retry failed: {err}",
        "adj.out": "Verdicts: {got}/{ids} group(s) → {out}",
        "adj.out_miss": "; still missing {ids}",
        "apply.backup_fail": "⛔ Backup self-check failed: {bak} reads back differently from the "
                             "original; nothing was written",
        "apply.backup_ok": "Backup self-check: {bak} sha256={sha}… reads back identical ✓",
        "apply.fault_j": "⚠ Fault injected after_journal: journal written, file untouched, "
                         "database not committed",
        "apply.fault_r": "⚠ Fault injected after_replace: file replaced, database rolled back; "
                         "run `somnians recover` to close the gap",
        "apply.db_fail": "⛔ Database write failed; transaction rolled back, original file untouched "
                         "(staging file removed)",
        "apply.batch": "Batch {batch}: soft-deleted {n}, skipped {skipped} group(s)",
        "apply.batch_list": " ({ids})",
        "apply.audit": "Audit → {db} | original backed up → {bak}",
        "apply.undo": "Undo: somnians rollback --records {records} --db {db} --batch {batch}",
        "rec.none": "No journal at {jpath}: nothing to recover",
        "rec.discard": "Batch {batch}: the file was never renamed, {n} merge(s) never took effect "
                       "⇒ journal discarded, no audit to backfill",
        "rec.backfill": "Batch {batch}: file renamed but the database never committed ⇒ "
                        "backfilled {n} audit row(s); rollback works again",
        "rec.already": "Batch {batch}: audit already committed ({n} row(s)) ⇒ journal dropped, "
                       "nothing rewritten (idempotent)",
        "rec.refuse": "Batch {batch}: the records file matches neither the pre- nor the post-apply "
                      "fingerprint ⇒ state unknown; no audit written, journal kept at {jpath}",
        "rec.legacy": "Batch {batch}: journal has no fingerprints (older format) ⇒ falling back to "
                      "is_deleted, which is weaker evidence",
        "rb.none": "Batch {batch} has no soft-delete rows; nothing changed",
        "rb.already": "Batch {batch} has already been rolled back; nothing changed",
        "rb.fault": "Injected rollback failure; the records file and audit were restored",
        "rb.commit_fault": "Injected interruption after commit; the rollback is durable",
        "rb.done": "Batch {batch}: restored {n} row(s); the audit table stays "
                   "(op=rollback keeps the trace, no rows deleted)",
        "sc.data": "Data root {root} (public gold set {n}/26 cases)",
        "sc.seat": "{name}: canary {p}/{c} pass, recorded verdicts {g}/{ids} lines",
        "sc.index": "Index ≡ exact: {n} candidate pair(s) in the sample, identical pair by pair",
        "sc.merge_cols": "audit_merge columns present "
                         "(old_id/keeper_id/batch/jaccard/kind/created_at)",
        "sc.change_cols": "audit_change columns present (entry_id/op/batch/undo_json/created_at)",
        "sc.apply": "apply: {n} row(s) soft-deleted, exit code {rc}",
        "sc.backup": "Backup decryptable: sha256 read back after writing matches the original",
        "sc.passthrough": "Unknown fields survive apply and rollback unchanged ({n} record(s))",
        "sc.rollback": "rollback: every row back to live, audit_merge left {n} row(s)",
        "sc.rollback_atomic": "Pre-commit failure restored file/audit; post-commit interruption kept "
                              "the committed state; repeating rollback adds no audit rows",
        "sc.crashA": "Crash point A (after rename): {n} row(s) changed on disk, no audit in the "
                     "database (rc={rc})",
        "sc.recover": "recover backfill: {n}/{total} audit row(s)",
        "sc.crashA_end": "Crash point A closed: after rollback every row is live again, "
                         "audit_merge back to zero",
        "sc.crashB": "Crash point B (after journal): file untouched, journal written; "
                     "recover discards the journal and rewrites nothing",
        "sc.missing": "\nSELFCHECK_FAIL (fixtures missing; the remaining items cannot be verified)",
        "sc.i18n": "i18n: three catalogs aligned and resolution order honoured "
                   "(flag > SOMNIANS_LANG > LC_* > LANG > en)",
        "lang.fallback": "⚠ Unknown language tag {tag}; falling back to en "
                         "(use --lang en|zh-Hans|zh-Hant)",
    },
    "zh-Hans": {
        "demo.title": "somnians demo · 蝶花半梦（Viola Somnians）｜data={data}",
        "sep.list": "、",
        "demo.cases": "公开金标 {n} 组：{types}",
        "demo.note": "（含私人记忆的真实组不入公开集；这里全是可公开的合成陷阱）\n",
        "demo.head": "席位            准确率    方向反读   canary   判定",
        "demo.canary_ok": "全过",
        "demo.canary_bad": "未过",
        "demo.usable": "可用",
        "demo.void": "作废",
        "demo.diff": "\n两席分歧 {n} 组：{ids}",
        "demo.none": "无",
        "demo.case": "  {cid} [{kind}] 期望 {exp}",
        "demo.keeper": "    keeper：{k}",
        "demo.drop": "    drop  ：{d}",
        "demo.verdicts": "    {a}={va} / {b}={vb}",
        "demo.crit1": "\n判据（唯一一条）：并的代价 = 丢掉 drop 里 keeper 没有的信息。",
        "demo.crit2": "  drop 比 keeper 多（限定/例外/并列对象/不同数值/相反语气）⇒ 不并",
        "demo.crit3": "  drop 比 keeper 少（压缩/残句/缺修饰/词序）⇒ 并\n"
                      "不用联网，以上是本仓库录好的两席判决。",
        "scan.cap": "⚠ {n} 个高频 3-gram 超过 cap={cap} 已跳过（可能漏配）；"
                    "要完全一致请用 --exact 或调大 --cap",
        "scan.read": "读入 {n} 条，活条目 {live} 条；阈值 {thresh}；{mode}",
        "scan.mode_exact": "全量比对（--exact）",
        "scan.mode_index": "3-gram 倒排缩候选",
        "scan.out": "候选 {n} 对 → {out}",
        "adj.brief": "brief 已写 → {out}（未给 --adapter，到此为止）",
        "adj.r1": "第一轮：{got}/{ids} 组（并发 {jobs}）",
        "adj.r1_fail": "；失败 {n} 席",
        "adj.retry": "重试 {rd}：只补 {n} 组 → {ids}",
        "adj.retry_err": "  重试失败：{err}",
        "adj.out": "判决 {got}/{ids} 组 → {out}",
        "adj.out_miss": "；仍缺 {ids}",
        "apply.backup_fail": "⛔ 备份自检失败：{bak} 读回与原文不一致，未改写入",
        "apply.backup_ok": "备份自检：{bak} sha256={sha}… 读回一致 ✓",
        "apply.fault_j": "⚠ 故障注入 after_journal：日志已写、文件未换、库未提交",
        "apply.fault_r": "⚠ 故障注入 after_replace：文件已换、库回滚；请 somnians recover 补齐",
        "apply.db_fail": "⛔ 写库失败，已回滚事务；原文件未动（暂存件已删）",
        "apply.batch": "批次 {batch}：软删 {n} 条，跳过 {skipped} 组",
        "apply.batch_list": "（{ids}）",
        "apply.audit": "审计 → {db}｜原文件备份 → {bak}",
        "apply.undo": "撤回：somnians rollback --records {records} --db {db} --batch {batch}",
        "rec.none": "无日志 {jpath}：没有待恢复的批次",
        "rec.discard": "批次 {batch}：文件尚未换名，{n} 条未生效 ⇒ 丢弃日志，无需补审计",
        "rec.backfill": "批次 {batch}：文件已换名但库未提交 ⇒ 补回审计 {n} 条，可正常 rollback",
        "rec.already": "批次 {batch}：审计已提交（{n} 条）⇒ 只丢日志，不重复写（幂等）",
        "rec.refuse": "批次 {batch}：文件既不匹配改动前、也不匹配改动后的指纹 ⇒ 状态不明；"
                      "不写审计、不删日志（{jpath}）",
        "rec.legacy": "批次 {batch}：日志无指纹（旧格式）⇒ 退回按 is_deleted 判，证据较弱",
        "rb.none": "批次 {batch} 无软删记录，未改动",
        "rb.already": "批次 {batch} 已回滚，未改动",
        "rb.fault": "注入回滚故障；记录文件与审计均已恢复",
        "rb.commit_fault": "注入提交后中断；回滚已持久提交",
        "rb.done": "批次 {batch} 已还原 {n} 条；审计表保留（op=rollback 留痕，不删记录）",
        "sc.data": "数据根 {root}（公开金标 {n}/26 组）",
        "sc.seat": "{name}：canary {p}/{c} 过，录制判决 {g}/{ids} 行",
        "sc.index": "倒排 ≡ 全量：样本 {n} 对候选，逐对逐分一致",
        "sc.merge_cols": "audit_merge 列齐（old_id/keeper_id/batch/jaccard/kind/created_at）",
        "sc.change_cols": "audit_change 列齐（entry_id/op/batch/undo_json/created_at）",
        "sc.apply": "apply：软删 {n} 条，退出码 {rc}",
        "sc.backup": "备份自证可解：写后读回 sha256 与原文一致",
        "sc.passthrough": "未点名的字段过 apply／rollback 原样不动（{n} 条）",
        "sc.rollback": "rollback：全部回 live，audit_merge 余 {n} 行",
        "sc.rollback_atomic": "提交前故障恢复原文件与审计；提交后中断保留已提交状态；重复回滚不新增审计",
        "sc.crashA": "崩溃点 A（换名后崩）：文件已改 {n} 条、库无审计（rc={rc}）",
        "sc.recover": "recover 补齐：审计 {n}/{total} 条",
        "sc.crashA_end": "崩溃点 A 收尾：回滚后全部回 live，audit_merge 归零",
        "sc.crashB": "崩溃点 B（日志后崩）：文件未动、日志已写；recover 丢弃日志且不改写",
        "sc.missing": "\nSELFCHECK_FAIL（样本缺失，后续项无法验）",
        "sc.i18n": "i18n：三语目录齐、判定顺序正确（--lang > SOMNIANS_LANG > LC_* > LANG > en）",
        "lang.fallback": "⚠ 认不出的语言标签 {tag}，落回 en（可用 --lang en|zh-Hans|zh-Hant）",
    },
    "zh-Hant": {
        "demo.title": "somnians demo · 蝶花半夢（Viola Somnians）｜data={data}",
        "sep.list": "、",
        "demo.cases": "公開金標 {n} 組：{types}",
        "demo.note": "（含私人記憶的真實組不入公開集；這裡全是可公開的合成陷阱）\n",
        "demo.head": "席位            準確率    方向反讀   canary   判定",
        "demo.canary_ok": "全過",
        "demo.canary_bad": "未過",
        "demo.usable": "可用",
        "demo.void": "作廢",
        "demo.diff": "\n兩席分歧 {n} 組：{ids}",
        "demo.none": "無",
        "demo.case": "  {cid} [{kind}] 期望 {exp}",
        "demo.keeper": "    keeper：{k}",
        "demo.drop": "    drop  ：{d}",
        "demo.verdicts": "    {a}={va} / {b}={vb}",
        "demo.crit1": "\n判據（唯一一條）：並的代價＝丟掉 drop 裡 keeper 沒有的資訊。",
        "demo.crit2": "  drop 比 keeper 多（限定／例外／並列對象／不同數值／相反語氣）⇒ 不並",
        "demo.crit3": "  drop 比 keeper 少（壓縮／殘句／缺修飾／詞序）⇒ 並\n"
                      "不用連網，以上是本倉庫錄好的兩席判決。",
        "scan.cap": "⚠ {n} 個高頻 3-gram 超過 cap={cap} 已跳過（可能漏配）；"
                    "要完全一致請用 --exact 或調大 --cap",
        "scan.read": "讀入 {n} 條，活條目 {live} 條；閾值 {thresh}；{mode}",
        "scan.mode_exact": "全量比對（--exact）",
        "scan.mode_index": "3-gram 倒排縮候選",
        "scan.out": "候選 {n} 對 → {out}",
        "adj.brief": "brief 已寫 → {out}（未給 --adapter，到此為止）",
        "adj.r1": "第一輪：{got}/{ids} 組（並發 {jobs}）",
        "adj.r1_fail": "；失敗 {n} 席",
        "adj.retry": "重試 {rd}：只補 {n} 組 → {ids}",
        "adj.retry_err": "  重試失敗：{err}",
        "adj.out": "判決 {got}/{ids} 組 → {out}",
        "adj.out_miss": "；仍缺 {ids}",
        "apply.backup_fail": "⛔ 備份自檢失敗：{bak} 讀回與原文不一致，未改寫入",
        "apply.backup_ok": "備份自檢：{bak} sha256={sha}… 讀回一致 ✓",
        "apply.fault_j": "⚠ 故障注入 after_journal：日誌已寫、檔案未換、庫未提交",
        "apply.fault_r": "⚠ 故障注入 after_replace：檔案已換、庫回滾；請 somnians recover 補齊",
        "apply.db_fail": "⛔ 寫庫失敗，已回滾交易；原檔案未動（暫存件已刪）",
        "apply.batch": "批次 {batch}：軟刪 {n} 條，跳過 {skipped} 組",
        "apply.batch_list": "（{ids}）",
        "apply.audit": "審計 → {db}｜原檔案備份 → {bak}",
        "apply.undo": "撤回：somnians rollback --records {records} --db {db} --batch {batch}",
        "rec.none": "無日誌 {jpath}：沒有待還原的批次",
        "rec.discard": "批次 {batch}：檔案尚未換名，{n} 條未生效 ⇒ 丟棄日誌，無需補審計",
        "rec.backfill": "批次 {batch}：檔案已換名但庫未提交 ⇒ 補回審計 {n} 條，可正常 rollback",
        "rec.already": "批次 {batch}：審計已提交（{n} 條）⇒ 只丟日誌，不重複寫（冪等）",
        "rec.refuse": "批次 {batch}：檔案既不匹配改動前、也不匹配改動後的指紋 ⇒ 狀態不明；"
                      "不寫審計、不刪日誌（{jpath}）",
        "rec.legacy": "批次 {batch}：日誌無指紋（舊格式）⇒ 退回按 is_deleted 判，證據較弱",
        "rb.none": "批次 {batch} 無軟刪記錄，未改動",
        "rb.already": "批次 {batch} 已回滾，未改動",
        "rb.fault": "注入回滾故障；記錄檔與審計均已恢復",
        "rb.commit_fault": "注入提交後中斷；回滾已持久提交",
        "rb.done": "批次 {batch} 已還原 {n} 條；審計表保留（op=rollback 留痕，不刪記錄）",
        "sc.data": "資料根 {root}（公開金標 {n}/26 組）",
        "sc.seat": "{name}：canary {p}/{c} 過，錄製判決 {g}/{ids} 行",
        "sc.index": "倒排 ≡ 全量：樣本 {n} 對候選，逐對逐分一致",
        "sc.merge_cols": "audit_merge 欄位齊（old_id/keeper_id/batch/jaccard/kind/created_at）",
        "sc.change_cols": "audit_change 欄位齊（entry_id/op/batch/undo_json/created_at）",
        "sc.apply": "apply：軟刪 {n} 條，退出碼 {rc}",
        "sc.backup": "備份自證可解：寫後讀回 sha256 與原文一致",
        "sc.passthrough": "未點名的欄位過 apply／rollback 原樣不動（{n} 條）",
        "sc.rollback": "rollback：全部回 live，audit_merge 餘 {n} 行",
        "sc.rollback_atomic": "提交前故障恢復原檔與審計；提交後中斷保留已提交狀態；重複回滾不新增審計",
        "sc.crashA": "崩潰點 A（換名後崩）：檔案已改 {n} 條、庫無審計（rc={rc}）",
        "sc.recover": "recover 補齊：審計 {n}/{total} 條",
        "sc.crashA_end": "崩潰點 A 收尾：回滾後全部回 live，audit_merge 歸零",
        "sc.crashB": "崩潰點 B（日誌後崩）：檔案未動、日誌已寫；recover 丟棄日誌且不改寫",
        "sc.missing": "\nSELFCHECK_FAIL（樣本缺失，後續項無法驗）",
        "sc.i18n": "i18n：三語目錄齊、判定順序正確（--lang > SOMNIANS_LANG > LC_* > LANG > en）",
        "lang.fallback": "⚠ 認不出的語言標籤 {tag}，落回 en（可用 --lang en|zh-Hans|zh-Hant）",
    },
}

_current = "en"


def normalize(tag):
    """把 POSIX locale 标签压成三档之一：返回 'en' / 'zh-Hans' / 'zh-Hant' / None（认不出）。"""
    if not tag:
        return None
    tag = str(tag).strip().lower().replace("-", "_")
    if tag in _SKIP:
        return None
    base = tag.split(".")[0].split("@")[0]
    parts = base.split("_")
    if parts[0] == "en":
        return "en"
    if parts[0] == "zh":
        region = parts[1] if len(parts) > 1 else ""
        if region in _ZH_HANT_REGIONS:
            return "zh-Hant"
        if region in _ZH_HANS_REGIONS or region == "":
            return "zh-Hans"
        return None          # zh_XX 认不出地区：不猜，交给下一级
    return None


def resolve_lang(flag=None, env=None):
    """返回 (语言, 警告或 None)。flag 永远赢；其次 SOMNIANS_LANG；再其次按 _ENV_ORDER 往下。"""
    import os
    env = os.environ if env is None else env
    if flag:
        if flag in LANGS:
            return flag, None
        return "en", ("lang.fallback", flag)
    for var in _ENV_ORDER:
        raw = env.get(var)
        if not raw:
            continue
        for part in raw.split(":"):          # LANGUAGE 可以是冒号分隔的列表
            lang = normalize(part)
            if lang:
                return lang, None
    return "en", None


def set_lang(lang):
    global _current
    _current = lang if lang in LANGS else "en"
    return _current


def get_lang():
    return _current


def t(key, **kw):
    """取一条文案。缺键先落 en，再不行就把键本身吐出来——⛔ 不静默吞掉。"""
    for lang in (_current, "en"):
        tpl = CATALOG.get(lang, {}).get(key)
        if tpl is not None:
            try:
                return tpl.format(**kw) if kw else tpl
            except (KeyError, IndexError):
                return tpl
    return key


def catalog_gaps():
    """三份目录的键差；空列表＝对齐。自检与 CI 都吃它。"""
    keys = {k: set(v) for k, v in CATALOG.items()}
    union = set().union(*keys.values())
    return sorted("%s:%s" % (lang, key) for lang, ks in keys.items() for key in union - ks)


# 判定顺序的自测用例（自检直接调 resolve_lang，不依赖真实环境变量）
_RESOLVE_CASES = (
    (None, {"LANG": "zh_CN.UTF-8"}, "zh-Hans"),
    (None, {"LANG": "zh_TW.UTF-8"}, "zh-Hant"),
    (None, {"LANG": "zh_HK.UTF-8"}, "zh-Hant"),
    (None, {"LANG": "en_US.UTF-8"}, "en"),
    (None, {"LANG": "C"}, "en"),
    (None, {"LC_ALL": "zh_Hant", "LANG": "en_US"}, "zh-Hant"),
    (None, {"SOMNIANS_LANG": "en", "LANG": "zh_CN.UTF-8"}, "en"),
    ("zh-Hant", {"LANG": "zh_CN.UTF-8"}, "zh-Hant"),
)


def resolve_ok():
    """所有用例都按预期落位才算过；空环境也必须是 en（⛔ 不许「碰巧」）。"""
    for flag, env, want in _RESOLVE_CASES:
        if resolve_lang(flag, env)[0] != want:
            return False
    return resolve_lang(None, {})[0] == "en"
