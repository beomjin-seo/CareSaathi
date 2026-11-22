"""Step 5: pack everything the app needs into one JSON file (app/data.json)."""
import sys, os, re, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, OUT, load_facilities
from ontology import SERVICE_ONTOLOGY as ONT
import trust as T
from musthave import MUST, CAP

SERVICES = list(ONT)   # all 19 services
# acute services a single-specialty facility (eye, dental, skin, physio, ayurveda/homeopathy) should not offer
OUT_OF_SCOPE = {"dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab", "burn_care", "icu", "ventilator", "blood_bank", "stroke", "radiotherapy", "snakebite_poison"}
HIGH, LOW = 90.0, 70.0
nz = lambda s: re.sub(r"[^A-Z]", "", str(s).upper().replace("&", "AND"))
t = lambda x, n: (re.sub(r"\s+", " ", x).strip()[:n] if isinstance(x, str) else "")

C = T.features(); S = C[C.y.notna()]; m = T.fit(S)
C["trust"] = 100 * m.predict_proba(C[T.FEATS].values)[:, 1]
C["band"] = np.where(C.trust >= HIGH, 2, np.where(C.trust >= LOW, 1, 0))
# honest validation numbers for the app: everything out-of-fold (each claim scored by a model that never saw its facility)
from sklearn.linear_model import LogisticRegression as _LR
from sklearn.model_selection import GroupKFold as _GK
from sklearn.metrics import roc_auc_score as _auc
_S = S.reset_index(drop=True); _X, _y, _g = _S[T.FEATS].values, _S.y.values, _S.uid.values; _o = np.zeros(len(_S))
for _tr, _te in _GK(5).split(_X, _y, _g): _o[_te] = _LR(max_iter=2000).fit(_X[_tr], _y[_tr]).predict_proba(_X[_te])[:, 1]
_b = np.where(_o >= HIGH / 100, 2, np.where(_o >= LOW / 100, 1, 0))
_svc = {s_: round(float(_auc(_y[(_S.service == s_).values], _o[(_S.service == s_).values])), 2) for s_ in _S.service.unique() if (_S.service == s_).sum() >= 50}
VAL = {"auc": round(float(_auc(_y, _o)), 2), "real": [round(100 * float(_y[_b == k].mean())) for k in (0, 1, 2)], "n": [int((_b == k).sum()) for k in (0, 1, 2)],
       "n_read": int((_S.was_read == 1).sum()) if "was_read" in _S else 0, "n_name": int((_S.was_read != 1).sum()) if "was_read" in _S else len(_S),
       "svc_min": min(_svc, key=_svc.get), "svc_min_auc": min(_svc.values()), "svc_max_auc": max(_svc.values())}
_rng = np.random.default_rng(3); _ug = np.unique(_g); _ix = {u: np.where(_g == u)[0] for u in _ug}; _E = C[C.trust >= LOW][T.FEATS].drop_duplicates().values; _P = []
for _ in range(200):
    _i = np.concatenate([_ix[u] for u in _rng.choice(_ug, len(_ug))])
    if len(set(_y[_i])) == 2: _P.append(100 * _LR(max_iter=2000).fit(_X[_i], _y[_i]).predict_proba(_E)[:, 1])
_sd = np.repeat(np.array(_P).std(0), C[C.trust >= LOW].groupby(T.FEATS, sort=False).size().reindex(pd.MultiIndex.from_arrays(_E.T, names=T.FEATS)).values)
TIE_PTS = round(float(np.median(_sd)), 1)
print("score noise (bootstrap SD of trust over refits, shown claims): median", TIE_PTS, "points -> tie window for planned ranking")
print("out-of-fold validation for the app:", VAL, _svc)
lab = C[C.y.notna()]; print("labelled claims by band (share real):", lab.groupby("band").y.agg(["size", "mean"]).round(2).to_dict("index"))
gp = os.path.join(ROOT, "analysis/labels/labels_general.csv")
if os.path.exists(gp):
    G = pd.read_csv(gp).merge(C[["claim_id", "band"]], on="claim_id"); print("independent reader, general hospitals:"); print(pd.crosstab(G.band, G.verdict).to_string())
C["excluded"] = ((C.neg != "") & C.service.isin(OUT_OF_SCOPE) & ~((C.neg == "skin_hair") & (C.service == "burn_care"))).astype(int)
C.loc[(C.service == "cataract_surgery") & ~C.neg.isin(["", "eye"]), "excluded"] = 1
# wider wrong-specialty rule (found by the stress test): the fitted labels use a narrow name rule; for display we also
# leave out dental, eye, skin, physio and ayurveda/homeopathy facilities for every service outside their own field.
_nm = C.name.str.lower().str.split(r" - |,", regex=True).str[0]
_PAT = {"dental": r"dental|dentist|orthodont|\bteeth|\btooth", "alt_med": r"ayurved|homoeo|homeo|unani|\bsiddha\b|naturopath|panchakarma", "eye": r"\beye\b|netralaya|nethralaya|ophthal|retina|lasik", "physio": r"physio", "skin_hair": r"\bskin\b|derma|\bhair\b|cosmet"}
_GEN = r"multi ?special(?!ity dental)|general|super ?special|nursing home|maternity|women|trauma|heart|cardiac|kidney|children|child|institute of medical|poly ?clinic|research cent|medical college"
_COLL = r"(homoeo\w*|homeo\w*|ayurved\w*|unani|dental) (medical )?college"
_ALLOW = {"eye": {"cataract_surgery"}, "skin_hair": {"burn_care"}, "dental": set(), "alt_med": set(), "physio": set()}
_kinds = pd.DataFrame({k: _nm.str.contains(rx, regex=True) for k, rx in _PAT.items()})
_single = _kinds.any(axis=1) & (~_nm.str.contains(_GEN, regex=True) | _nm.str.contains(_COLL, regex=True))
def _out(i):
    ks = [k for k in _PAT if _kinds.at[i, k]]; s_ = C.at[i, "service"]
    return not (any(s_ in _ALLOW[k] for k in ks) or (s_ == "ortho_surgery" and "ortho" in _nm.at[i]))
_new = pd.Series([bool(_single.at[i]) and _out(i) for i in C.index], index=C.index) & (C.excluded == 0)
C.loc[_new, "neg"] = [next(k for k in _PAT if _kinds.at[i, k]) for i in C.index[_new]]; C.loc[_new, "excluded"] = 1
print("wider wrong-specialty rule: extra claims left out", int(_new.sum()), "| of them previously shown (band >= 1)", int((_new & (C.band >= 1)).sum()), "| labelled real among them", int((C.y[_new] == 1).sum()))
C = C[C.service.isin(SERVICES)]
# must-have rule: a claim whose record lacks an indispensable item cannot be "strong"
def missing(r):
    found = set(r.coreq_list.split("|")) if isinstance(r.coreq_list, str) and r.coreq_list else set()
    return [j for j, g in enumerate(MUST.get(r.service, [])) if not (set(g["keys"]) & found)]
C["miss"] = [missing(r) for r in C.itertuples()]; C["raw"] = C.trust
cap = C.miss.map(len).gt(0) & (C.trust > CAP)
print("must-have rule: strong claims before", int((C.band == 2).sum()), "| capped", int(cap.sum()), "| by service:", C[cap].service.value_counts().to_dict())
lab2 = C[C.y.notna() & (C.raw >= HIGH)]; print("  labelled strong claims, share real: must-haves all found", lab2[lab2.miss.map(len) == 0].y.agg(["size", "mean"]).round(3).tolist(), "| a must-have missing", lab2[lab2.miss.map(len) > 0].y.agg(["size", "mean"]).round(3).tolist())
C.loc[cap, "trust"] = CAP; C.loc[cap, "band"] = 1
print("claims exported:", len(C), "| bands:", C.band.value_counts().to_dict(), "| excluded by specialty rule:", int(C.excluded.sum()))

F = load_facilities(); L = pd.read_csv(os.path.join(OUT, "location.csv"))
F = F.merge(L[["uid", "best_lat", "best_lon", "best_state", "best_district", "location_confidence", "loc_class"]], left_on="unique_id", right_on="uid", how="left")
F = F[F.unique_id.isin(C.uid) & F.best_lat.notna()].reset_index(drop=True)
DOC = re.compile(r"\bDr\.?\s+[A-Z][a-zA-Z.]+(?:\s+[A-Z][a-zA-Z.]+){0,3}")
def doctor(r):
    """Up to 4 short sentences on the record that name a doctor (shown as unverified information, never scored)."""
    seen, out = set(), []
    for s in sorted(r.capability_l + r.procedure_l, key=len):
        m = DOC.search(s)
        if m and 25 <= len(s) <= 160 and m.group(0) not in seen:
            seen.add(m.group(0)); out.append(t(s, 160))
        if len(out) == 4: break
    return out
# distance noise: for rows whose three location signals agree, how far the map point sits from the postcode centre.
# Two places whose distances differ by less than the 75th percentile of this cannot be ordered by distance with confidence.
_d = L[L.loc_class.astype(str).str.contains("agree")].d_coord_pin_km.dropna(); TIE = round(float(_d.quantile(.75)), 1)
print("location noise (map point vs postcode centre, agreeing rows): median", round(float(_d.median()), 2), "| 75th percentile", TIE, "km -> tie window for emergency ranking")
places, pidx = [], {}
def place(st, di):
    k = (str(st).title() if isinstance(st, str) else "", str(di).title() if isinstance(di, str) else "")
    if k not in pidx: pidx[k] = len(places); places.append(list(k))
    return pidx[k]
fac = []; fid = {}
for i, r in enumerate(F.itertuples()):
    fid[r.unique_id] = i
    fac.append([t(r.name, 70), t(r.address_city, 30), place(r.best_state, r.best_district), round(r.best_lat, 4), round(r.best_lon, 4), round(float(r.location_confidence), 2) if pd.notna(r.location_confidence) else None,
                r.facilityTypeId or "", "public" if r.operatorTypeId in ("public", "government") else (r.operatorTypeId or ""), t(r.officialPhone, 20), t(r.officialWebsite, 60), doctor(r),
                [int(r.capacity_n) if pd.notna(r.capacity_n) and 1 <= r.capacity_n <= 5000 else None, int(r.numberDoctors_n) if pd.notna(r.numberDoctors_n) and 1 <= r.numberDoctors_n <= 5000 else None,
                 int(r.yearEstablished_n) if pd.notna(r.yearEstablished_n) and 1800 <= r.yearEstablished_n <= 2026 else None]])
# ladder: department -> procedure -> equipment, each with the record's own words
H = pd.read_pickle(os.path.join(OUT, "hits.pkl")); H = H[H["flags"].eq("")]
def win(seg, match, n=120):
    """Cut a sentence to n characters around the matched words."""
    seg = re.sub(r"\s+", " ", seg).strip()
    if len(seg) <= n: return seg
    i = seg.lower().find(match.lower()); a = max(0, min(i - 40, len(seg) - n)) if i >= 0 else 0
    if a > 0: a = seg.find(" ", a) + 1
    cut = seg[a:a + n]; cut = cut[:cut.rfind(" ")] if a + n < len(seg) and " " in cut else cut
    return ("… " if a > 0 else "") + cut + (" …" if a + n < len(seg) else "")
def best(cls):
    d = H[H.cls == cls].assign(q=lambda x: ~x.qty, sh=lambda x: x.seglen < 14, l=lambda x: x.seglen.clip(upper=400)).sort_values(["q", "sh", "l"]).drop_duplicates(["uid", "service"])
    return {(r.uid, r.service): [win(r.seg, r.match), r.field] for r in d.itertuples()}
BP, BI = best("proc"), best("infra")
CQ = {s: {k: re.compile(rx, re.I) for k, rx in ONT[s]["coreq"].items()} for s in ONT}
SEGS = {r.unique_id: [(f, x) for f, l in (("equipment", r.equipment_l), ("capability", r.capability_l), ("procedure", r.procedure_l)) for x in l] + [("description", x) for x in re.split(r"(?<=[.!?])\s+", r.description or "")] for r in F.itertuples()}
NOT_EQUIP = re.compile(r"ologist|surgeon|ian$|obstetric|anaesth|intensivist|round_the_clock|volume|count|backup|ambulance", re.I)
OTHER_ICU = re.compile(r"neonat|\bNICU\b|p(a)?ediatric|\bPICU\b|\bSNCU\b", re.I)
def needquote(uid, s, found):
    """When no sentence describes the unit itself: the record's sentence for one needed item (must-haves first)."""
    order = [k for g in MUST.get(s, []) for k in g["keys"]] + list(CQ[s])
    for k in dict.fromkeys(order):
        if k not in found or NOT_EQUIP.search(k): continue      # this step is about rooms and machines, not staff or opening hours
        for f, x in SEGS.get(uid, []):
            m = CQ[s][k].search(x)
            if m and len(x) >= 14 and not (k == "ICU" and OTHER_ICU.search(x)): return [win(x, m.group(0)), f, list(CQ[s]).index(k)]
    return ["", "", -1]
nsp = lambda x: re.sub(r"[^a-z]", "", str(x).lower())
pretty = lambda x: re.sub(r"(?<=[a-z])(?=[A-Z])", " ", str(x)).lower()[:40]
SPEC = dict(zip(F.unique_id, F.specialties_l))
def dept(uid, s):
    """Matching department on the specialties list: 2 = the service's own department, 1 = its parent department."""
    for lvl, key in ((2, "spec_direct"), (1, "spec_related")):
        rx = ONT[s].get(key)
        if not rx: continue
        for x in SPEC.get(uid, []):
            if re.search(rx, nsp(x)): return [pretty(x), lvl]
    return ["", 0]
# doctors read ahead of time from facilities' own websites (pipeline/scrape_doctors.py); demo cities only
_dw = os.path.join(ROOT, "pipeline", "external", "doctors_web.json"); DW = json.load(open(_dw)) if os.path.exists(_dw) else {}
for i, r in enumerate(F.itertuples()):
    w = DW.get(r.unique_id)
    # drop names cut by the reader (a short last word glued to a degree, e.g. "Dr. Shamsul Ho" + "DA" from "HODA"); fix ALL-CAPS
    ds = [[re.sub(r"\b([A-Z])([A-Z]+)\b", lambda m_: m_.group(1) + m_.group(2).lower(), n_), q_] for n_, q_ in (w or {}).get("doctors", []) if len(n_.split()[-1].strip(".")) >= 3]
    fac[i].append([w["url"], ds[:8], w["fetched"]] if ds else None)
print("doctors from websites: facilities", sum(1 for f in fac if f[12]), "| doctors", sum(len(f[12][1]) for f in fac if f[12]))
claims = {}
for s in SERVICES:
    keys = list(ONT[s]["coreq"].keys()); d = {}
    for r in C[C.service == s].itertuples():
        if r.uid not in fid: continue
        found = set(r.coreq_list.split("|")) if isinstance(r.coreq_list, str) and r.coreq_list else set()
        signs = int(r.all_differ) | (int(r.far2) << 1) | (int(r.other_sites_2plus) << 2)
        row = [round(r.trust, 1), int(r.band), int(r.tier), [keys.index(k) for k in keys if k in found], t(r.quote, 190), r.quote_field, signs, int(r.ownurl), int(r.excluded), r.neg or ""]
        if r.band >= 1 and not r.excluded:   # shown on a card: add the ladder, the missing must-haves and the uncapped score
            row += [dept(r.uid, s) + BP.get((r.uid, s), ["", ""]) + (BI[(r.uid, s)] + [-1] if (r.uid, s) in BI else needquote(r.uid, s, found)), r.miss, round(r.raw, 1)]
        d[fid[r.uid]] = row
    claims[s] = {"coreq": [k.replace("_", " ") for k in keys], "c": d,
                 "must": [{"k": [keys.index(k) for k in g["keys"]], "why": g["why"], "src": g["src"]} for g in MUST.get(s, [])]}
P = pd.read_csv(os.path.join(OUT, "pin_lookup.csv"), dtype={"pincode": str}); P = P[P.lat.notna()]
pins = {r.pincode: [round(r.lat, 3), round(r.lon, 3), place(r.state, r.district)] for r in P.itertuples()}
cities = {}
for (c, st, di), g in F.groupby([F.address_city.str.strip().str.title(), "best_state", "best_district"]):
    if c and len(c) >= 3 and (c not in cities or len(g) > cities[c][3]): cities[c] = [round(g.best_lat.median(), 3), round(g.best_lon.median(), 3), place(st, di), len(g)]
for (st, di), g in P.groupby(["state", "district"]):
    c = str(di).title()
    if c not in cities and len(g) >= 3: cities[c] = [round(g.lat.median(), 3), round(g.lon.median(), 3), place(st, di), 0]
cities = {k: v[:3] for k, v in cities.items()}
N = pd.read_csv(os.path.join(ROOT, "nfhs_5_district_health_indicators.csv")); D = pd.read_csv(os.path.join(ROOT, "analysis/out_nfhs_district.csv"))
N = N.merge(D[["district_name", "state_ut", "st", "di", "fdi"]], on=["district_name", "state_ut"])
_acc = ["institutional_birth_5y_pct", "mothers_who_had_at_least_4_anc_visits_lb5y_pct", "births_attended_by_skilled_hp_5y_10_pct", "child_12_23m_fully_vaccinated_based_on_information_from_eit_pct"]
_idx = N[_acc].apply(pd.to_numeric, errors="coerce").rank(pct=True).mean(axis=1)      # how much basic care actually reaches people here
N["access_group"] = pd.qcut(_idx.rank(method="first"), 3, labels=[0, 1, 2]).astype(int)   # 0 = least reached third of districts
print("access groups (districts):", N.access_group.value_counts().sort_index().to_dict(), "| median facility births by group:", N.assign(v=pd.to_numeric(N.institutional_birth_5y_pct, errors="coerce")).groupby("access_group").v.median().to_dict())
g_ = lambda r, c: (None if pd.isna(pd.to_numeric(r[c], errors="coerce")) else round(float(pd.to_numeric(r[c], errors="coerce")), 1))
nfhs = {}
for _, r in N.iterrows():
    v = [g_(r, "institutional_birth_5y_pct"), g_(r, "institutional_birth_in_public_facility_5y_pct"), g_(r, "births_in_a_public_fac_that_were_delivered_by_csection_5y_pct"), g_(r, "births_in_a_private_fac_that_were_delivered_by_csection_5y_pct"),
         g_(r, "hh_member_covered_health_insurance_pct"), g_(r, "women_age_15_49_who_are_literate_pct"), g_(r, "all_w15_49_who_are_anaemic_pct"), r.district_name.strip(), int(r.access_group),
         g_(r, "w15_19_who_were_already_mothers_or_pregnant_at_the_time_of_pct"), g_(r, "average_out_of_pocket_expenditure_per_delivery_in_a_public_fac"), g_(r, "w20_24_married_before_age_18_years_pct")]
    for k in {r.st + "|" + (r.fdi if isinstance(r.fdi, str) else r.di), r.st + "|" + r.di}: nfhs[k] = v
# renamed districts: facility-side name -> name used by the 2019-21 survey (found by the data check: 11.6% of facilities had no district context)
ALIAS = {"KARNATAKA|BENGALURUURBAN": "KARNATAKA|BANGALORE", "HARYANA|GURUGRAM": "HARYANA|GURGAON", "UTTARPRADESH|PRAYAGRAJ": "UTTARPRADESH|ALLAHABAD", "KARNATAKA|BELAGAVI": "KARNATAKA|BELGAUM",
         "KARNATAKA|MYSURU": "KARNATAKA|MYSORE", "KARNATAKA|KALABURAGI": "KARNATAKA|GULBARGA", "KARNATAKA|BALLARI": "KARNATAKA|BELLARY", "ASSAM|KAMRUPMETRO": "ASSAM|KAMRUPMETROPOLITAN",
         "WESTBENGAL|PARAGANASNORTH": "WESTBENGAL|NORTHTWENTYFOURPARGANA", "WESTBENGAL|PARAGANASSOUTH": "WESTBENGAL|SOUTHTWENTYFOURPARGANA", "MAHARASHTRA|RAIGAD": "MAHARASHTRA|RAIGARH",
         "UTTARPRADESH|AYODHYA": "UTTARPRADESH|FAIZABAD", "HARYANA|NUH": "HARYANA|MEWAT", "KARNATAKA|SHIVAMOGGA": "KARNATAKA|SHIMOGA", "KARNATAKA|TUMAKURU": "KARNATAKA|TUMKUR"}
_n0 = len(nfhs)
for k, v in ALIAS.items():
    if v in nfhs and k not in nfhs: nfhs[k] = nfhs[v]
_fk = pd.Series([nz(places[f[2]][0]) + "|" + nz(places[f[2]][1]) for f in fac])
print("district context: aliases added", len(nfhs) - _n0, "| facilities with survey context", int(_fk.isin(set(nfhs)).sum()), "of", len(fac))
pm = pd.read_csv(os.path.join(ROOT, "pipeline/external/pmndp_centres.csv")); pmndp = {}
for r in pm.itertuples(): pmndp.setdefault(nz(r.state) + "|" + nz(r.district), []).append(t(r.facility, 60))
w = dict(zip(T.FEATS, np.exp(m.coef_[0]).round(2).tolist()))
out = {"fac": fac, "places": places, "claims": claims, "pins": pins, "cities": cities, "nfhs": nfhs, "pmndp": pmndp,
       "meta": {"tie_pts": TIE_PTS, "tie_km": TIE, "val": VAL, "cap": CAP, "weights": w, "base": round(float(np.exp(m.intercept_[0])), 2), "high": HIGH, "low": LOW, "n_fac_table": 9989, "public_share_table": 5.0, "n_labelled": int(len(S))}}
js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(os.path.join(ROOT, "app", "data.json"), "w").write(js)
print("facilities:", len(fac), "| pins:", len(pins), "| cities:", len(cities), "| nfhs keys:", len(nfhs), "| pmndp districts:", len(pmndp), "| bytes:", len(js.encode()))
for q in ["Araria", "Patna", "Nashik", "Gadchiroli", "Jaipur"]: print(q, cities.get(q), places[cities[q][2]] if q in cities else None, nfhs.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1]))[:5] if q in cities and nfhs.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1])) else None, len(pmndp.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1]), [])) if q in cities else None)
