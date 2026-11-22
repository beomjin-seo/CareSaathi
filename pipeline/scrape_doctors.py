"""Optional step: read doctors' names, degrees, specialty, years of experience and college from facilities' own websites.

The app cannot fetch other websites when a user clicks (browser security and Databricks Free Edition's outbound
limits), so we fetch once, offline, and store what we find. Scope: every facility in the app that lists a website,
highest-scoring first, so a run stopped early still covers the most relevant places.
Politeness: robots.txt is respected, a generic user agent, at most 5 pages per site (home page plus links whose text
mentions doctors or team), 6-second timeout. Directory sites (Practo, Justdial and similar) are NOT read: their terms
forbid automated collection.

Output: pipeline/external/doctors_web.json
  {facility unique_id: {"url": page, "doctors": [[name, degrees, specialty, years, college], ...], "fetched": date}}
Shown in the app as "read from the hospital's own website, not verified". Never used in a score.
"""
import sys, os, re, json, html, threading, concurrent.futures as cf, urllib.request, urllib.parse, urllib.robotparser
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT

UA = "Mozilla/5.0 (compatible; health-facility-research/0.2)"
OUTF = os.path.join(ROOT, "pipeline", "external", "doctors_web.json")
SKIP = re.compile(r"practo|justdial|lybrate|sulekha|facebook|instagram|google|wikipedia|indiamart|credihealth|medifee|quikr", re.I)
NAME = re.compile(r"\bDr\.?\s+((?:[A-Z][a-zA-Z.']+|[A-Z]\.)(?:\s+(?:[A-Z][a-zA-Z.']+|[A-Z]\.)){0,3})(?=[\s,|(\-–:]|$)")
QUAL = re.compile(r"\b(MBBS|M\.B\.B\.S\.?|MD|M\.D\.|MS|M\.S\.|DM|D\.M\.|M\.?\s?Ch\.?|DNB|FRCS\w*|MRCP\w*|FRCP\w*|DGO|DCH|D\.?\s?Ortho|DA|FNB|FICS|FACS|FACC|FESC|MRCOG|FRCOG|MDS|BDS|DOMS|DLO|DPM|DMRD|DMRT|PhD|FIAGES|FMAS)\b(\s*\([A-Za-z &.,-]{2,30}\))?")
SPEC = re.compile(r"(orthopa?edic\w*|joint replacement|spine|trauma|neuro ?surg\w*|neurolog\w*|nephrolog\w*|urolog\w*|gyn(a)?ecolog\w*|obstetric\w*|"
                  r"p(a)?ediatric\w*|neonatolog\w*|cardiac surg\w*|cardio ?thoracic|ctvs|cardiolog\w*|interventional cardiolog\w*|oncolog\w*|radiation oncolog\w*|"
                  r"radiolog\w*|ophthalmolog\w*|plastic surg\w*|burns?|pulmonolog\w*|chest physician|respiratory|critical care|intensivist|ana?esthe\w*|"
                  r"emergency medicine|general surg\w*|laparoscopic|internal medicine|general physician|physician|patholog\w*|dermatolog\w*|ent|psychiatr\w*|gastro\w*|endocrin\w*|dentist|dental)", re.I)
YEARS = re.compile(r"(\d{1,2})\+?\s*(?:years|yrs)\b", re.I)
COLL = re.compile(r"((?:[A-Z][A-Za-z.&']+\s){0,5}(?:Medical College|University|Institute of Medical Sciences|AIIMS|PGIMER|JIPMER|CMC|KEM|Maulana Azad|Grant Medical)[A-Za-z ,.'&]{0,30})")
LINK = re.compile(r'<a[^>]+href=["\']([^"\'#]+)["\'][^>]*>(.*?)</a>', re.I | re.S)


def get(url, rp):
    if rp is not None and not rp.can_fetch(UA, url): return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=6) as r:
            if "html" not in (r.headers.get("Content-Type") or "html"): return ""
            return r.read(1_500_000).decode("utf-8", "ignore")
    except Exception:
        return ""


def text(h):
    h = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|td|span|a)>", " | ", h)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", h)))


def doctors(t):
    out, seen = [], set()
    ms = list(NAME.finditer(t))
    for i, m in enumerate(ms):
        toks = re.sub(r"\s+", " ", m.group(1)).strip(" .").split(" ")
        while toks and QUAL.fullmatch(toks[-1].strip(",.")): toks.pop()      # "Dr. Rakesh Sharma MBBS" -> name ends before the degree
        name = " ".join(toks).strip(" .")
        if not name: continue
        if len(name.split()[-1].strip(".")) < 3 or len(name) < 6 or name.lower() in seen: continue
        end = ms[i + 1].start() if i + 1 < len(ms) else len(t)
        w = t[m.start() + 4 + len(name): min(end, m.end() + 320)]
        q = list(dict.fromkeys(re.sub(r"\s+", " ", "".join(x)).strip() for x in QUAL.findall(w)))[:5]
        s = list(dict.fromkeys(x.group(0).lower() for x in SPEC.finditer(w[:200])))[:2]
        if not q and not s: continue
        y = YEARS.search(w); c = COLL.search(w)
        seen.add(name.lower())
        out.append(["Dr. " + name, ", ".join(q)[:60], " / ".join(s)[:40], int(y.group(1)) if y and 1 <= int(y.group(1)) <= 60 else None, c.group(1).strip(" ,.")[:60] if c else ""])
        if len(out) >= 12: break
    return out


def site(uid, raw):
    base = raw if raw.startswith("http") else "https://" + raw.strip("/")
    if SKIP.search(base): return uid, None
    p = urllib.parse.urlparse(base); dom = p.netloc
    rp = urllib.robotparser.RobotFileParser(); rp.set_url(f"{p.scheme}://{dom}/robots.txt")
    try: rp.read()
    except Exception: rp = None
    home = get(base, rp) or (get(base.replace("https://", "http://"), rp) if base.startswith("https://") else "")
    if not home: return uid, None
    pages = [(base, home)]
    for href, lab in LINK.findall(home):
        if re.search(r"doctor|team|consultant|specialist|faculty|our[- ]?experts|physician|surgeon", href + " " + lab, re.I):
            u = urllib.parse.urljoin(base, href)
            if urllib.parse.urlparse(u).netloc.replace("www.", "") == dom.replace("www.", "") and u not in [x[0] for x in pages]:
                h = get(u, rp)
                if h: pages.append((u, h))
        if len(pages) >= 5: break
    docs, src, seen = [], base, set()
    for u, h in pages:
        for d in doctors(text(h)):
            if d[0].lower() in seen: continue
            seen.add(d[0].lower()); docs.append(d)
            if src == base and u != base: src = u
    return uid, {"url": src, "doctors": docs[:12]}


if __name__ == "__main__":
    from common import load_facilities
    D = json.load(open(os.path.join(ROOT, "app", "data.json")))
    F = load_facilities(); ids = dict(zip(F.name.str.slice(0, 70).str.strip(), F.unique_id))
    best = {}
    for s, v in D["claims"].items():
        for k, c in v["c"].items():
            if c[1] >= 1 and not c[8]: best[int(k)] = max(best.get(int(k), 0), c[0])
    jobs = {}
    for i in sorted(best, key=lambda i: -best[i]):
        f = D["fac"][i]; uid = ids.get(re.sub(r"\s+", " ", f[0]).strip())
        if f[9] and uid: jobs[uid] = f[9]
    out = json.load(open(OUTF)) if os.path.exists(OUTF) else {}
    todo = [kv for kv in jobs.items() if kv[0] not in out or (out[kv[0]].get("doctors") and len(out[kv[0]]["doctors"][0]) < 5)]
    print("sites to read:", len(todo), "of", len(jobs), flush=True)
    lock = threading.Lock(); n = 0
    with cf.ThreadPoolExecutor(64) as ex:
        for uid, res in ex.map(lambda kv: site(*kv), todo):
            with lock:
                n += 1
                out[uid] = {**(res or {"url": "", "doctors": []}), "fetched": "2026-11-22"}
                if n % 250 == 0:
                    json.dump(out, open(OUTF, "w"), ensure_ascii=False)
                    print(n, "read |", sum(1 for v in out.values() if v["doctors"]), "sites with doctors", flush=True)
    json.dump(out, open(OUTF, "w"), ensure_ascii=False)
    print("finished | sites", len(out), "| with doctors", sum(1 for v in out.values() if v["doctors"]), "| doctors", sum(len(v["doctors"]) for v in out.values()), flush=True)
