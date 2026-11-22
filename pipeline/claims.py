"""Step 2: find every sentence that mentions a service, and grade each (facility, service) claim.

Output
  pipeline/out/hits.pkl    one row per (facility, service, sentence) match
  pipeline/out/claims.csv  one row per (facility, service): tier 3 strong / 2 medium / 1 weak
Tier rule (no weights):
  strong  = an infrastructure/equipment sentence with no caution flag, AND (a quantity in it OR support in 2+ fields)
  medium  = a named procedure or an infrastructure sentence with no caution flag
  weak    = only loose topical words, or every matching sentence carries a caution flag
Caution flags: negation, referral elsewhere, future plan, doctor biography, directory listing, news, "not listed" meta text.
"""
import re, sys, os
import pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_facilities, OUT
from ontology import SERVICE_ONTOLOGY as ONT, CONTEXT, QUANTITY

I = re.I
CX = {k: re.compile(v, I) for k, v in CONTEXT.items()}
QTY = re.compile(QUANTITY, I)
SPLIT = re.compile(r";\s+|\s\|\s|\n+|(?<![A-Z]r)(?<!No)(?<!Mr)(?<!Mrs)(?<!St)(?<!vs)(?<!Prof)(?<!\b[A-Z])(?<=[a-z0-9\)\]])\.\s+(?=[A-Z0-9])")
comp = lambda lst: re.compile("|".join(f"(?:{p})" for p in lst), I) if lst else None
# False friends found by two independent readers of 227 suspect claims (2026-11-21): words that match a service but mean something else.
EXTRA_EXCLUDE = {
    "emergency_obstetric": [r"delivery (unit|arm|tray|cart|hose|tubing)", r"dental (chair )?(with |and )?(attached )?delivery", r"(timely|prompt|quick|fast|speedy|same[- ]day|on[- ]time|doorstep|free|express) delivery",
                            r"(denture|spectacle|eyewear|lens|crown|aligner|order|product|parcel|kit|report|result|sample|medicine|drug|oxygen|care|service|healthcare|treatment) delivery",
                            r"delivery of (dentures?|spectacles|eyewear|lenses|crowns?|aligners?|orders?|products?|reports?|results?|medicines?|care|services?|treatment|healthcare|quality)"],
    "cath_lab": [r"(retinal?|fundus|fluorescein|ophthalmic|ocular|eye|OCT|ICG|indocyanine|FFA|digital fundus)[ -]*(fluorescein )?angiograph\w*", r"angiograph\w* (of the )?(retina|eye|fundus)", r"(surgical|implant|dental|orthodontic|occlusal|radiographic) stents?"],
    "nicu": [r"(dry|co2|ivf|embryo|lab(oratory)?) incubators?", r"phototherapy (for|in) (skin|psoriasis|vitiligo|eczema)", r"(skin|derma\w*|psoriasis|vitiligo)[^.;]{0,40}phototherapy"],
    "cardiac_surgery": [r"\bEECP\b[^.;]*", r"(alternative|without|avoid\w*|non[- ]surgical)[^.;]{0,40}(bypass|heart surgery|cardiac surgery|open[- ]heart)"],
}
for _s, _extra in EXTRA_EXCLUDE.items():
    ONT[_s]["exclude"] = list(ONT[_s].get("exclude", [])) + _extra
C = {s: {k: comp(o.get(k, [])) for k in ["infra", "proc", "generic", "exclude"]} for s, o in ONT.items()}
ANY = {s: comp(o.get("infra", []) + o.get("proc", []) + o.get("generic", [])) for s, o in ONT.items()}
CQ = {s: {k: re.compile(v, I) for k, v in o["coreq"].items()} for s, o in ONT.items()}


def flags_for(seg, ms, me, own):
    f = []
    pre, post = seg[max(0, ms - 70):ms], seg[me:me + 70]
    m = CX["neg_pre"].search(pre)
    if m and not CX["neg_ignore"].search(pre[m.start():] + seg[ms:me]): f.append("neg")
    elif CX["neg_post"].search(post): f.append("neg")
    if CX["meta_absent"].search(seg): f.append("meta")
    loc = seg[max(0, ms - 80):me + 60]
    if CX["referral"].search(loc) and not CX["referral_ignore"].search(loc): f.append("referral")
    if CX["future"].search(seg[max(0, ms - 45):me + 30]): f.append("future")
    if CX["bio"].search(own.sub(" ", seg) if own else seg): f.append("bio")
    if CX["directory"].search(seg): f.append("directory")
    if CX["news"].search(seg): f.append("news")
    return f


def build_hits(df):
    rows = []
    for r in df.itertuples():
        nm = r.name.strip()
        own = re.compile(re.escape(nm), I) if len(nm) >= 4 else None
        units = []
        for fld in ["procedure", "equipment", "capability"]:
            seen = set()
            for t in getattr(r, fld + "_l"):
                t = t.strip(); k = re.sub(r"\W+", " ", t.lower()).strip()
                if t and k not in seen:
                    seen.add(k); units.append((fld, t))
        units.append(("description", r.description))
        for fld, t in units:
            cand = [s for s in ONT if ANY[s].search(t)]
            if not cand: continue
            for seg in SPLIT.split(t):
                if not seg or len(seg) < 3: continue
                for s in cand:
                    c = C[s]
                    mseg = c["exclude"].sub(lambda m: " " * len(m.group(0)), seg) if c["exclude"] else seg
                    if own: mseg = own.sub(lambda m: " " * len(m.group(0)), mseg)   # a service word inside the facility's own name is not evidence
                    hit = None
                    for cls in ("infra", "proc", "generic"):
                        if c[cls] is None: continue
                        m = c[cls].search(mseg)
                        if m: hit = (cls, m); break
                    if not hit: continue
                    cls, m = hit
                    fl = flags_for(seg, m.start(), m.end(), own)
                    qty = bool(QTY.search(seg[max(0, m.start() - 45):m.end() + 45]))
                    rows.append((r.unique_id, s, fld, cls, m.group(0), qty, "|".join(fl), len(seg), seg))
    return pd.DataFrame(rows, columns=["uid", "service", "field", "cls", "match", "qty", "flags", "seglen", "seg"])


def build_claims(H, df):
    H = H.assign(valid=H["flags"].eq(""))
    alltext = (df.description + " || " + df.procedure_l.map(" || ".join) + " || " + df.equipment_l.map(" || ".join) + " || " + df.capability_l.map(" || ".join))
    alltext = dict(zip(df.unique_id, alltext))
    rank = {"infra": 0, "proc": 1, "generic": 2}
    out = []
    for (uid, s), h in H.groupby(["uid", "service"]):
        v = h[h.valid]; vi = v[v.cls == "infra"]; vp = v[v.cls == "proc"]
        nf = v[v.cls.isin(["infra", "proc"])].field.nunique()
        tier = 3 if (len(vi) and (nf >= 2 or vi.qty.any())) else 2 if (len(vi) or len(vp)) else 1
        b = h.assign(o=(~h.valid) * 10 + h.cls.map(rank) - h.qty * 0.5, l=h.seglen.clip(upper=400)).sort_values(["o", "l"]).iloc[0]
        txt = alltext.get(uid, "")
        co = [k for k, rx in CQ[s].items() if rx.search(txt)]
        out.append((uid, s, tier, nf, len(h), int(h.valid.sum()), b.field, b.seg[:300], b["flags"], len(co), len(CQ[s]), "|".join(co)))
    return pd.DataFrame(out, columns=["uid", "service", "tier", "n_fields", "n_hits", "n_valid", "quote_field", "quote", "quote_flags", "coreq_found", "coreq_total", "coreq_list"])


if __name__ == "__main__":
    df = load_facilities()
    H = build_hits(df); H.to_pickle(os.path.join(OUT, "hits.pkl"))
    Cl = build_claims(H, df); Cl.to_csv(os.path.join(OUT, "claims.csv"), index=False)
    print("facilities", len(df), "| hits", len(H), "| claims", len(Cl))
    print(Cl.groupby("service").tier.value_counts().unstack(fill_value=0).to_string())
