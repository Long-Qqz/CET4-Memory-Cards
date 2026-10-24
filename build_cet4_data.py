# -*- coding: utf-8 -*-
"""
解析 5 个 CET4 词库压缩包 (JSONL 格式), 去重合并成精简词库 bundle.json
字段说明:
  w  词头 (小写)
  p  美音音标 (usphone)
  pk 英音音标 (ukphone)
  au 音频发音标识 (ukspeech, 形如 "abruptly&type=1"; 拼 URL: https://dict.youdao.com/dictvoice?audio=<w>&type=1)
  t  释义列表 [{pos, tran}]
  ex 例句 [{en, cn}]
  xe 真题例句 [{en, paper}]
  q  真题选择题 [{q, choices:[...], answer, explain}] (answer 为正确选项文本)
  ph 短语 [{en, cn}]
  sy 同义词 (去重字符串列表)
  an 反义词 (去重字符串列表)
  rw 同根词 (去重字符串列表)
  rm 助记
  st 星级
"""
import json, zipfile, os, glob

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "bundle.json")

# 基础词过滤表：小学/初中基础词（功能词 + 基础实词），不属于四级核心生词
FILTER_WORDS = set("""a an the i me my mine you your yours he him his she her hers it its we us our ours they them their theirs
be am is are was were been being do does did done doing have has had having can could may might must shall should will would
not no yes and or but so if because when while after before until though although since nor yet as than then
of to for in on at by with from up down out off over under above below about around behind between into onto upon within without
this that these those there here where what when who whom whose why how
one two three four five six seven eight nine ten zero first second third all some any each every both neither either few many much more most
other another such own same only just very too also again almost already even ever never still
apple banana orange pear book pen pencil bag desk chair table door window room house home school class teacher student
boy girl man woman people father mother brother sister family friend name year day today tomorrow yesterday morning afternoon evening night week month
red blue green yellow black white big small tall short long new old good bad hot cold fast slow happy sad
eat drink run walk go come see look hear speak say talk read write listen play sing dance jump sit stand sleep
cat dog bird fish water milk tea rice bread egg meat sun moon star tree flower grass sky cloud rain snow wind
hand foot head eye ear nose mouth face leg arm body hair coat hat shoe shirt dress
""".split())

def load_packs():
    packs = {}
    for z in sorted(glob.glob(os.path.join(ROOT, "*.zip"))):
        with zipfile.ZipFile(z) as f:
            name = [n for n in f.namelist() if n.endswith(".json")][0]
            raw = f.read(name).decode("utf-8", errors="replace")
            objs = [json.loads(l) for l in raw.splitlines() if l.strip()]
            packs[os.path.splitext(os.path.basename(z))[0]] = objs
    return packs

def _content(o):
    try:
        return o["content"]["word"]["content"]
    except (KeyError, TypeError):
        return {}

def _uniq(seq):
    seen, out = set(), []
    for x in seq:
        if x not in seen:
            seen.add(x); out.append(x)
    return out

def extract(o):
    c = _content(o)
    w = o.get("headWord", "").strip().lower()
    rec = {"w": w, "p": "", "pk": "", "au": "", "t": [], "ex": [], "xe": [], "q": [],
           "ph": [], "sy": [], "an": [], "rw": [], "rm": "", "st": 0}
    if not w:
        return None
    rec["p"] = c.get("usphone", "") or ""
    rec["pk"] = c.get("ukphone", "") or ""
    rec["au"] = c.get("ukspeech", "") or ""
    rec["st"] = c.get("star", 0) or 0
    # 释义
    for tr in c.get("trans", []) or []:
        pos = tr.get("pos", ""); tran = tr.get("tran", "") or tr.get("tranCn", "")
        if pos or tran:
            rec["t"].append({"pos": pos, "tran": tran})
    # 例句
    for s in (c.get("sentence", {}) or {}).get("sentences", []) or []:
        en = s.get("sContent", "") or ""
        cn = s.get("sCn", "") or ""
        if en and cn and (en, cn) not in rec["ex"]:
            rec["ex"].append({"en": en, "cn": cn})
    # 真题例句
    for s in (c.get("realExamSentence", {}) or {}).get("sentences", []) or []:
        en = s.get("sContent", "") or ""
        src = (s.get("sourceInfo", {}) or {})
        paper = (src.get("year", "") + " " + src.get("paper", "") + " " + src.get("type", "")).strip()
        if en and (en, paper) not in rec["xe"]:
            rec["xe"].append({"en": en, "paper": paper})
    # 真题选择题
    for q in c.get("exam", []) or []:
        question = q.get("question", "")
        choices = [ch.get("choice", "") for ch in q.get("choices", []) or []]
        ans = q.get("answer", {}) or {}
        right = ans.get("rightIndex", 0) or 0
        explain = ans.get("explain", "") or ""
        choice_ok = ""
        for ch in q.get("choices", []) or []:
            if ch.get("choiceIndex") == right:
                choice_ok = ch.get("choice", "")
        if question and choices and len(rec["q"]) < 2:
            rec["q"].append({"q": question, "choices": choices, "answer": choice_ok, "explain": explain})
    # 短语
    for ph in (c.get("phrase", {}) or {}).get("phrases", []) or []:
        en = ph.get("pContent", ""); cn = ph.get("pCn", "")
        if en and (en, cn) not in rec["ph"]:
            rec["ph"].append({"en": en, "cn": cn})
    # 同/反/同根词
    for key, out in (("syno", "sy"), ("antos", "an"), ("relWord", "rw")):
        node = c.get(key, {}) or {}
        lst = []
        if key == "syno":
            for g in node.get("synos", []) or []:
                for h in g.get("hwds", []) or []:
                    lst.append(h.get("w", ""))
        elif key == "antos":
            for h in node.get("anto", []) or []:
                lst.append(h.get("hwd", ""))
        elif key == "relWord":
            for h in node.get("relWords", []) or []:
                lst.append(h.get("headWord", "") or h.get("hwd", ""))
        rec[out] = _uniq([x.strip() for x in lst if x and x.strip()])
    # 助记
    rm = c.get("remMethod", {}) or {}
    if isinstance(rm, dict):
        rm = rm.get("val", "") or ""
    rec["rm"] = rm or ""
    return rec

def merge(base, add):
    """合并两条同词记录, 保留更丰富的信息"""
    if not base:
        return add
    for k in ("p", "pk", "au"):
        if not base[k] and add[k]:
            base[k] = add[k]
    for k in ("t", "ex", "xe", "q", "ph"):
        seen = set()
        merged = []
        for item in list(base[k]) + list(add[k]):
            key = json.dumps(item, ensure_ascii=False)
            if key not in seen:
                seen.add(key); merged.append(item)
        base[k] = merged
    for k in ("sy", "an", "rw"):
        base[k] = _uniq(base[k] + add[k])
    if not base["rm"] and add["rm"]:
        base["rm"] = add["rm"]
    base["st"] = max(base["st"], add["st"])
    return base

def main():
    packs = load_packs()
    print("pack counts:", {k: len(v) for k, v in packs.items()})
    merged = {}
    src_counts = {}
    for name, objs in packs.items():
        for o in objs:
            rec = extract(o)
            if not rec:
                continue
            src_counts.setdefault(name, 0)
            src_counts[name] += 1
            key = rec["w"]
            merged[key] = merge(merged.get(key), rec)
    print("per-pack valid words:", src_counts)
    print("union unique words:", len(merged))
    words = sorted(merged.values(), key=lambda r: r["w"])
    # 过滤基础词
    removed = [r for r in words if r["w"] in FILTER_WORDS]
    words = [r for r in words if r["w"] not in FILTER_WORDS]
    print("removed basic words:", len(removed), "->", sorted(r["w"] for r in removed))
    print("kept words:", len(words))
    # 大小统计
    raw_size = sum(len(json.dumps(r, ensure_ascii=False)) for r in words)
    print("bundle raw size: %.2f MB" % (raw_size / 1024 / 1024))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, separators=(",", ":"))
    print("written:", OUT)
    # 覆盖统计
    with_f = lambda k: sum(1 for r in words if r[k])
    for k in ("p", "pk", "au", "t", "ex", "xe", "q", "ph", "sy", "an", "rw", "rm"):
        print("  %s: %d/%d" % (k, with_f(k), len(words)))

if __name__ == "__main__":
    main()
