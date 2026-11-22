"""Estimate formula weights from name-based control groups (silver labels), and measure district size."""
import sys, os, re
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, OUT, load_facilities, haversine
pd.set_option("display.width", 230); pd.set_option("display.max_columns", 40)

# ---- how big is a district? (from post office coordinates in the PIN directory)
P = pd.concat([pd.read_csv(os.path.join(ROOT, f), dtype=str, low_memory=False) for f in ["indiaPincodeDirectory1.csv", "indiaPincodeDirectory2.csv"]])
P["lat"] = pd.to_numeric(P.latitude, errors="coerce"); P["lon"] = pd.to_numeric(P.longitude, errors="coerce")
P = P[P.lat.between(6, 37.5) & P.lon.between(68, 97.5)]
g = P.groupby(["statename", "district"]); c = g[["lat", "lon"]].transform("median")
P["r"] = haversine(P.lat, P.lon, c.lat, c.lon)
dist = g.agg(offices=("pincode", "size"), pins=("pincode", "nunique"), r50=("r", "median"), r90=("r", lambda s: s.quantile(.9)))
dist = dist[dist.offices >= 30]
print("districts in PIN directory (>=30 post offices):", len(dist))
print("distance from district centre to its post offices: median office", round(dist.r50.median(), 1), "km | 90th-percentile office", round(dist.r90.median(), 1), "km  -> typical district is roughly", int(2 * dist.r90.median()), "km across")
print("post offices per district, median:", int(dist.offices.median()), "| PIN codes per district, median:", int(dist.pins.median()))
F = load_facilities()
L = pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False).drop_duplicates("unique_id")
M = pd.read_csv(os.path.join(ROOT, "research/data_work/record_contamination.csv")).drop_duplicates("unique_id")
per = L.groupby(["best_state", "best_district"]).size()
print("table facilities per district (districts that have any):", per.describe()[["count", "25%", "50%", "75%", "max"]].round(0).to_dict())

# ---- silver labels from names
F = F.merge(L[["unique_id", "loc_class"]], on="unique_id", how="left").merge(M[["unique_id", "t_located_elsewhere", "n_std", "n_ov"]], on="unique_id", how="left")
nm = F.name.str.lower()
BROAD = r"multi|general|maternity|nursing home|medical college|trauma|heart|cardiac|kidney|ortho|surgical|children|institute of medical|super ?special|poly ?clinic|hospitals? and|& ?hospital|research cent"
NEG = {"eye": r"\beye\b|netralaya|nethralaya|ophthal|\bvision\b|retina|lasik|drishti|\bnetra\b", "dental": r"dental|dentist|\btooth|teeth|smile|orthodont", "skin_hair": r"\bskin\b|derma|\bhair\b|cosmet|aesthetic", "physio": r"physio", "alt_med": r"ayurved|homoeo|homeo|unani|siddha|naturopath|panchakarma"}
F["neg"] = ""
for k, rx in NEG.items(): F.loc[nm.str.contains(rx, regex=True) & (F.neg == ""), "neg"] = k
F.loc[(F.facilityTypeId == "dentist") & (F.neg == ""), "neg"] = "dental"; F.loc[nm.str.contains(BROAD, regex=True), "neg"] = ""
POS = {"dialysis": r"dialysis|kidney|nephro|\brenal", "emergency_obstetric": r"maternity|matern|women|obstet|gyna?ec|prasuti|zenana", "nicu": r"children|child ?care|pa?ediatric|neonat|newborn|nicu",
       "cardiac_surgery": r"heart|cardiac|cardio", "cath_lab": r"heart|cardiac|cardio", "mri": r"\bmri\b|imaging|\bscan|diagnostic|radiolog", "ct_scan": r"\bct\b|imaging|\bscan|diagnostic|radiolog", "burn_care": r"\bburn",
       "trauma_emergency": r"trauma|accident", "cataract_surgery": NEG["eye"], "chemotherapy": r"cancer|onco", "radiotherapy": r"cancer|onco", "ortho_surgery": r"ortho|\bbone|joint|fracture", "blood_bank": r"blood ?bank|blood cent"}
NEG_SERV = {"dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab", "burn_care", "icu", "ventilator", "blood_bank"}
Cl = pd.read_csv(os.path.join(OUT, "claims.csv")).merge(F[["unique_id", "name", "neg", "loc_class", "t_located_elsewhere", "n_std", "n_ov", "facilityTypeId"]], left_on="uid", right_on="unique_id")
nml = Cl.name.str.lower()
Cl["y"] = np.nan
for s, rx in POS.items():
    m = (Cl.service == s) & nml.str.contains(rx, regex=True) & ((Cl.neg == "") | ((s == "cataract_surgery") & (Cl.neg == "eye")))
    Cl.loc[m, "y"] = 1
m0 = (Cl.neg != "") & Cl.service.isin(NEG_SERV) & ~((Cl.neg == "skin_hair") & (Cl.service == "burn_care"))
Cl.loc[m0, "y"] = 0
# features (no name, no facility type)
Cl["t2"] = (Cl.tier == 2).astype(int); Cl["t3"] = (Cl.tier == 3).astype(int)
Cl["coreq"] = Cl.coreq_found / Cl.coreq_total
Cl["fields2"] = (Cl.n_fields >= 2).astype(int)
Cl["caution"] = Cl.quote_flags.fillna("").ne("").astype(int)
Cl["geo"] = Cl.loc_class.isin(["B_latlon_outlier", "C_postcode_outlier", "D_city_outlier", "E_all_disagree", "G_ll_pc_disagree_nocity"]).astype(int)
Cl["otherplace"] = (Cl.t_located_elsewhere.fillna(0) > 0).astype(int); Cl["phones"] = (Cl.n_std.fillna(0) >= 3).astype(int); Cl["sources"] = (Cl.n_ov.fillna(0) >= 6).astype(int)
Cl["n_signs"] = Cl[["geo", "otherplace", "phones", "sources"]].sum(axis=1)
S = Cl[Cl.y.notna()].copy()
print("\nsilver-labelled claims:", len(S), "| likely real (name states the service):", int(S.y.sum()), "| likely false (single-specialty facility, acute service):", int((S.y == 0).sum()))
print("by service:"); print(S.groupby("service").y.agg(["size", "mean"]).round(2).T.to_string())
print("\nshare likely real, by evidence tier:", S.groupby("tier").y.agg(["size", "mean"]).round(3).to_dict("index"))
print("share likely real, by number of warning signs:", S.groupby("n_signs").y.agg(["size", "mean"]).round(3).to_dict("index"))
print("share likely real, by co-requirements found (thirds):", S.groupby(pd.cut(S.coreq, [-.01, .33, .66, 1])).y.agg(["size", "mean"]).round(3).to_dict("index"))
FEATS = ["t2", "t3", "coreq", "fields2", "caution", "geo", "otherplace", "phones", "sources"]
X, y, grp = S[FEATS].values, S.y.values, S.uid.values
aucs = []
for tr, te in GroupKFold(5).split(X, y, grp):
    mdl = LogisticRegression(C=1.0, max_iter=1000).fit(X[tr], y[tr]); aucs.append(roc_auc_score(y[te], mdl.predict_proba(X[te])[:, 1]))
print("\n5-fold AUC (facilities kept whole across folds):", np.round(aucs, 3), "mean", round(float(np.mean(aucs)), 3))
for name, cols in [("tier only", ["t2", "t3"]), ("tier + corroboration", ["t2", "t3", "coreq", "fields2", "caution"]), ("warning signs only", ["geo", "otherplace", "phones", "sources"])]:
    a = [roc_auc_score(y[te], LogisticRegression(max_iter=1000).fit(S[cols].values[tr], y[tr]).predict_proba(S[cols].values[te])[:, 1]) for tr, te in GroupKFold(5).split(X, y, grp)]
    print(f"   {name:24s} AUC {np.mean(a):.3f}")
# leave-one-service-out: does the formula transfer to a service it never saw?
loso = []
for s in ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab", "blood_bank"]:
    te = (S.service == s).values
    if len(set(y[te])) < 2: continue
    mdl = LogisticRegression(max_iter=1000).fit(X[~te], y[~te]); loso.append((s, int(te.sum()), round(roc_auc_score(y[te], mdl.predict_proba(X[te])[:, 1]), 3)))
print("leave-one-service-out AUC:", loso)
mdl = LogisticRegression(C=1.0, max_iter=1000).fit(X, y)
co = pd.DataFrame({"feature": FEATS, "coef": mdl.coef_[0].round(2), "odds_multiplier": np.exp(mdl.coef_[0]).round(2)})
print("\nfitted weights (log-odds) and what each does to the odds:"); print(co.to_string(index=False)); print("intercept", round(float(mdl.intercept_[0]), 2))
# bootstrap stability
B = []
rng = np.random.default_rng(3); ug = np.unique(grp)
for _ in range(300):
    pick = rng.choice(ug, len(ug)); idx = np.concatenate([np.where(grp == u)[0] for u in pick])
    if len(set(y[idx])) < 2: continue
    B.append(LogisticRegression(max_iter=1000).fit(X[idx], y[idx]).coef_[0])
B = np.array(B); print("bootstrap 90% range of each weight:"); print(pd.DataFrame({"feature": FEATS, "p5": np.percentile(B, 5, 0).round(2), "p95": np.percentile(B, 95, 0).round(2)}).to_string(index=False))
S.to_csv(os.path.join(ROOT, "analysis/out_silver.csv"), index=False)
