"""Step 5: pack everything the app needs into one JSON file (app/data.json)."""
import sys, os, re, json
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, OUT, load_facilities
from ontology import SERVICE_ONTOLOGY as ONT
import trust as T

SERVICES = list(ONT)   # all 19 services
# acute services a single-specialty facility (eye, dental, skin, physio, ayurveda/homeopathy) should not offer
OUT_OF_SCOPE = {"dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab", "burn_care", "icu", "ventilator", "blood_bank", "stroke", "radiotherapy", "snakebite_poison"}
HIGH, LOW = 90.0, 70.0
nz = lambda s: re.sub(r"[^A-Z]", "", str(s).upper().replace("&", "AND"))
t = lambda x, n: (re.sub(r"\s+", " ", x).strip()[:n] if isinstance(x, str) else "")

C = T.features(); S = C[C.y.notna()]; m = T.fit(S)
C["trust"] = 100 * m.predict_proba(C[T.FEATS].values)[:, 1]
C["band"] = np.where(C.trust >= HIGH, 2, np.where(C.trust >= LOW, 1, 0))
lab = C[C.y.notna()]; print("labelled claims by band (share real):", lab.groupby("band").y.agg(["size", "mean"]).round(2).to_dict("index"))
gp = os.path.join(ROOT, "analysis/labels/labels_general.csv")
if os.path.exists(gp):
    G = pd.read_csv(gp).merge(C[["claim_id", "band"]], on="claim_id"); print("independent reader, general hospitals:"); print(pd.crosstab(G.band, G.verdict).to_string())
C["excluded"] = ((C.neg != "") & C.service.isin(OUT_OF_SCOPE) & ~((C.neg == "skin_hair") & (C.service == "burn_care"))).astype(int)
C.loc[(C.service == "cataract_surgery") & ~C.neg.isin(["", "eye"]), "excluded"] = 1
C = C[C.service.isin(SERVICES)]
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
claims = {}
for s in SERVICES:
    keys = list(ONT[s]["coreq"].keys()); d = {}
    for r in C[C.service == s].itertuples():
        if r.uid not in fid: continue
        found = set(r.coreq_list.split("|")) if isinstance(r.coreq_list, str) and r.coreq_list else set()
        signs = int(r.all_differ) | (int(r.far2) << 1) | (int(r.other_sites_2plus) << 2)
        d[fid[r.uid]] = [round(r.trust, 1), int(r.band), int(r.tier), [keys.index(k) for k in keys if k in found], t(r.quote, 190), r.quote_field, signs, int(r.ownurl), int(r.excluded), r.neg or ""]
    claims[s] = {"coreq": [k.replace("_", " ") for k in keys], "c": d}
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
pm = pd.read_csv(os.path.join(ROOT, "pipeline/external/pmndp_centres.csv")); pmndp = {}
for r in pm.itertuples(): pmndp.setdefault(nz(r.state) + "|" + nz(r.district), []).append(t(r.facility, 60))
w = dict(zip(T.FEATS, np.exp(m.coef_[0]).round(2).tolist()))
out = {"fac": fac, "places": places, "claims": claims, "pins": pins, "cities": cities, "nfhs": nfhs, "pmndp": pmndp,
       "meta": {"weights": w, "base": round(float(np.exp(m.intercept_[0])), 2), "high": HIGH, "low": LOW, "n_fac_table": 9989, "public_share_table": 5.0, "n_labelled": int(len(S))}}
js = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(os.path.join(ROOT, "app", "data.json"), "w").write(js)
print("facilities:", len(fac), "| pins:", len(pins), "| cities:", len(cities), "| nfhs keys:", len(nfhs), "| pmndp districts:", len(pmndp), "| bytes:", len(js.encode()))
for q in ["Araria", "Patna", "Nashik", "Gadchiroli", "Jaipur"]: print(q, cities.get(q), places[cities[q][2]] if q in cities else None, nfhs.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1]))[:5] if q in cities and nfhs.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1])) else None, len(pmndp.get(nz(places[cities[q][2]][0]) + "|" + nz(places[cities[q][2]][1]), [])) if q in cities else None)
