"""Optional step: read doctor names and qualifications from facilities' own websites, ahead of time.

The app cannot fetch other websites when a user clicks (browser security and Databricks Free Edition's outbound
limits), so we fetch once, offline, and store what we find. Scope: facilities near the city shortcuts on the start
screen (the demo set), not all 6,535. Politeness: robots.txt is respected, one site at a time per domain, a generic
user agent, at most 4 pages per site (home page plus links whose text mentions doctors or team).

Output: pipeline/external/doctors_web.json  {facility unique_id: {"url": page, "doctors": [[name, qualifications], ...], "fetched": date}}
Shown in the app as "from the hospital's own website, read on <date>, not verified".
"""
import sys, os, re, json, math, html, concurrent.futures as cf, urllib.request, urllib.parse, urllib.robotparser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

CITIES = ["Delhi", "Mumbai", "Kolkata", "Chennai", "Bengaluru", "Hyderabad", "Patna", "Lucknow", "Jaipur", "Bhopal", "Ranchi", "Guwahati"]
PER_CITY, RADIUS_KM, UA = 45, 30, "Mozilla/5.0 (compatible; health-facility-research/0.1)"
OUTF = os.path.join(ROOT, "pipeline", "external", "doctors_web.json")
QUAL = r"(?:MBBS|M\.?B\.?B\.?S|MD|M\.D\.|MS|M\.S\.|DM|D\.M\.|M\.?Ch|DNB|FRCS|MRCP|FRCP|DGO|DCH|DA|FNB|FICS|FACS|MDS|BDS|DO|DOMS|DLO|DPM|PhD|Fellowship)"
DOC = re.compile(r"\b(Dr\.?\s+[A-Z][a-zA-Z.]+(?:\s+[A-Z][a-zA-Z.]+){0,3})\s*[,\-–(|:]?\s*((?:" + QUAL + r"[\s,.()/&A-Za-z-]{0,40}?){1,5})(?=[\s<|;]|$)")
LINK = re.compile(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def hav(a, b, c, d):
    r = math.pi / 180; x = math.sin((c - a) * r / 2) ** 2 + math.cos(a * r) * math.cos(c * r) * math.sin((d - b) * r / 2) ** 2
    return 12742 * math.asin(math.sqrt(x))


def get(url, rp):
    if rp is not None and not rp.can_fetch(UA, url): return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=8) as r:
            if "html" not in (r.headers.get("Content-Type") or "html"): return ""
            return r.read(1_500_000).decode("utf-8", "ignore")
    except Exception:
        return ""


def text(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|td|span)>", " | ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


def site(uid, raw):
    base = raw if raw.startswith("http") else "https://" + raw.strip("/")
    dom = urllib.parse.urlparse(base).netloc
    rp = urllib.robotparser.RobotFileParser(); rp.set_url(f"{urllib.parse.urlparse(base).scheme}://{dom}/robots.txt")
    try: rp.read()
    except Exception: rp = None
    home = get(base, rp) or (get(base.replace("https://", "http://"), rp) if base.startswith("https://") else "")
    if not home: return uid, None
    pages = [(base, home)]
    for href, lab in LINK.findall(home):
        if re.search(r"doctor|team|consultant|specialist|faculty|our[- ]?experts|physician", href + " " + lab, re.I):
            u = urllib.parse.urljoin(base, href)
            if urllib.parse.urlparse(u).netloc.endswith(dom.replace("www.", "")) and u not in [p[0] for p in pages]:
                h = get(u, rp)
                if h: pages.append((u, h))
        if len(pages) >= 4: break
    seen, docs, src = set(), [], base
    for u, h in pages:
        for m in DOC.finditer(text(h)):
            n = re.sub(r"\s+", " ", m.group(1)).strip(" .")
            q = re.sub(r"\s+", " ", m.group(2)).strip(" ,.-(|")
            if n.lower() in seen or len(n) < 7: continue
            seen.add(n.lower()); docs.append([n, q[:60]]); src = u if src == base else src
            if len(docs) >= 10: break
    return uid, {"url": src, "doctors": docs} if docs else {"url": base, "doctors": []}


if __name__ == "__main__":
    D = json.load(open(os.path.join(ROOT, "app", "data.json")))
    import pandas as pd
    from common import load_facilities
    F = load_facilities(); ids = dict(zip(F.name.str.slice(0, 70).str.strip(), F.unique_id))
    best = {}
    for s, v in D["claims"].items():
        for k, c in v["c"].items():
            if c[1] >= 1 and not c[8]: best[int(k)] = max(best.get(int(k), 0), c[0])
    pick = {}
    for city in CITIES:
        if city not in D["cities"]: continue
        la, lo = D["cities"][city][:2]
        near = sorted([(-best[i], i) for i in best if D["fac"][i][9] and hav(la, lo, D["fac"][i][3], D["fac"][i][4]) <= RADIUS_KM])[:PER_CITY]
        for _, i in near: pick[i] = D["fac"][i][9]
    jobs = {}
    for i, w in pick.items():
        uid = ids.get(re.sub(r"\s+", " ", D["fac"][i][0]).strip())
        if uid: jobs[uid] = w
    print("sites to read:", len(jobs), flush=True)
    out = json.load(open(OUTF)) if os.path.exists(OUTF) else {}
    with cf.ThreadPoolExecutor(24) as ex:
        for n, (uid, res) in enumerate(ex.map(lambda kv: site(*kv), [kv for kv in jobs.items() if kv[0] not in out])):
            if res is not None: out[uid] = {**res, "fetched": "2026-11-22"}
            if n % 25 == 0: print(n, "done |", sum(1 for v in out.values() if v["doctors"]), "sites with doctors", flush=True)
    json.dump(out, open(OUTF, "w"), ensure_ascii=False)
    print("finished | sites read", len(out), "| with doctors", sum(1 for v in out.values() if v["doctors"]), "| doctors", sum(len(v["doctors"]) for v in out.values()))
