"""Full scan: every NFHS district indicator x every facility-side district measure.
Question: do districts that score higher on an indicator have more capable-looking facilities in the table?"""
import sys, os, re
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, OUT, load_facilities
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 70)
rng = np.random.default_rng(7)
F = load_facilities(); Cl = pd.read_csv(os.path.join(OUT, "claims.csv"))
L = pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False).drop_duplicates("unique_id")[["unique_id", "best_state", "best_district", "loc_class"]]
M = pd.read_csv(os.path.join(ROOT, "research/data_work/record_contamination.csv")).drop_duplicates("unique_id")[["unique_id", "tier"]].rename(columns={"tier": "mix"})
F = F.merge(L, on="unique_id", how="left").merge(M, on="unique_id", how="left")
nz = lambda s: re.sub(r"[^A-Z]", "", str(s).upper().replace("&", "AND"))
F["st"] = F.best_state.map(nz); F["fdi"] = F.best_district.map(nz)
T = Cl.pivot(index="uid", columns="service", values="tier").reindex(F.unique_id).fillna(0); T.index = F.index
SV = list(T.columns)
for s in SV: F["ev_" + s] = (T[s] >= 2).astype(float)
F["n_services"] = (T >= 2).sum(axis=1); F["n_strong"] = (T == 3).sum(axis=1)
F["hosp"] = F.facilityTypeId.eq("hospital"); F["public"] = F.operatorTypeId.isin(["public", "government"]).astype(float)
F["cap_len"] = F.capability_l.map(len); F["has_equip"] = (F.equipment_l.map(len) > 0).astype(float)
F["loc_bad"] = F.loc_class.isin(["B_latlon_outlier", "C_postcode_outlier", "D_city_outlier", "E_all_disagree", "G_ll_pc_disagree_nocity"]).astype(float)
F["mix_high"] = F.mix.eq("HIGH").astype(float)
F["beds"] = F.capacity_n.where(F.capacity_n.between(1, 5000)); F["docs"] = F.numberDoctors_n.where(F.numberDoctors_n.between(1, 5000))

D0 = pd.read_csv(os.path.join(ROOT, "analysis/out_nfhs_district.csv"))[["district_name", "state_ut", "st", "fdi"]]
N = pd.read_csv(os.path.join(ROOT, "nfhs_5_district_health_indicators.csv")).merge(D0, on=["district_name", "state_ut"])
ind = [c for c in N.columns if c not in ("district_name", "state_ut", "st", "fdi", "households_surveyed", "women_15_49_interviewed", "men_15_54_interviewed")]
N[ind] = N[ind].apply(pd.to_numeric, errors="coerce"); ind = [c for c in ind if N[c].notna().mean() >= 0.7]
print("NFHS indicators kept (>=70% filled):", len(ind))

Hh = F[F.hosp]
agg = {"n_fac": ("unique_id", "size")}
A = F.groupby(["st", "fdi"]).agg(n_fac=("unique_id", "size"), n_hosp=("hosp", "sum"), public_share=("public", "mean"), loc_bad=("loc_bad", "mean"), mix_high=("mix_high", "mean"))
B = Hh.groupby(["st", "fdi"]).agg(svc_per_hosp=("n_services", "mean"), strong_per_hosp=("n_strong", "mean"), cap_len=("cap_len", "median"), has_equip=("has_equip", "mean"), beds=("beds", "median"), docs=("docs", "median"), **{"ev_" + s: ("ev_" + s, "mean") for s in SV})
A = A.join(B).reset_index()
X = N.merge(A, on=["st", "fdi"], how="inner"); X = X[X.n_hosp >= 5].reset_index(drop=True)
print("districts with >=5 hospitals in the table and an NFHS match:", len(X), "| hospitals covered:", int(X.n_hosp.sum()))
met = ["svc_per_hosp", "strong_per_hosp", "cap_len", "has_equip", "beds", "docs", "public_share", "loc_bad", "mix_high"] + ["ev_" + s for s in SV]
X["log_n"] = np.log(X.n_fac)
z = X[ind].apply(lambda c: (c - c.mean()) / c.std()).fillna(0); u, sv, vt = np.linalg.svd(z.values, full_matrices=False); X["dev"] = u[:, 0] * sv[0]
load = pd.Series(vt[0], index=ind).sort_values(); 
if X.dev.corr(X["women_age_15_49_with_10_or_more_years_of_schooling_pct"]) < 0: X["dev"] = -X.dev; load = -load
print("development axis (PC1) loads most on:", [c[:45] for c in load.sort_values().index[-4:]], "| least:", [c[:45] for c in load.sort_values().index[:3]])
print("spearman dev vs log(n_fac):", round(stats.spearmanr(X.dev, X.log_n)[0], 2), "| dev vs svc_per_hosp:", round(stats.spearmanr(X.dev, X.svc_per_hosp)[0], 2))

def resid(v, C):
    m = v.notna(); r = stats.rankdata(v[m]); Cm = np.column_stack([np.ones(m.sum())] + [stats.rankdata(c[m]) for c in C])
    out = pd.Series(np.nan, index=v.index); out[m] = r - Cm @ np.linalg.lstsq(Cm, r, rcond=None)[0]; return out
rows = []
for i in ind:
    for m_ in met:
        ok = X[i].notna() & X[m_].notna()
        if ok.sum() < 60: continue
        r, p = stats.spearmanr(X.loc[ok, i], X.loc[ok, m_])
        a = resid(X.loc[ok, i], [X.loc[ok, "log_n"], X.loc[ok, "dev"]]); b = resid(X.loc[ok, m_], [X.loc[ok, "log_n"], X.loc[ok, "dev"]])
        pr, pp = stats.pearsonr(a, b)
        rows.append((i, m_, int(ok.sum()), r, p, pr, pp))
R = pd.DataFrame(rows, columns=["indicator", "facility_measure", "n", "rho", "p", "partial", "p_partial"])
def bh(p):
    p = np.asarray(p); o = np.argsort(p); q = np.empty_like(p); q[o] = np.minimum.accumulate((p[o] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]; return q
R["q"] = bh(R.p); R["q_partial"] = bh(R.p_partial)
print("\ntests run:", len(R), "| raw: significant at FDR 5%:", int((R.q < .05).sum()), "| after removing district size + development axis:", int((R.q_partial < .05).sum()))
sh = lambda d: d.assign(indicator=d.indicator.str[:62]).round(3).to_string(index=False)
print("\nTOP raw correlations:"); print(sh(R.reindex(R.rho.abs().sort_values(ascending=False).index).head(14)[["indicator", "facility_measure", "n", "rho", "q"]]))
print("\nTOP after controlling for district size and development (the non-obvious ones):"); print(sh(R.reindex(R.partial.abs().sort_values(ascending=False).index).head(22)[["indicator", "facility_measure", "n", "rho", "partial", "q_partial"]]))
R.to_csv(os.path.join(ROOT, "analysis/out_scan.csv"), index=False)

# ---- the hypothesis stated directly: above-median districts have more capable-looking hospitals?
print("\nHYPOTHESIS: split districts at the median of each indicator; compare 'services with evidence per hospital'")
res = []
for i in ind:
    ok = X[i].notna(); v = X.loc[ok, i]; y = X.loc[ok, "svc_per_hosp"]; hi = v >= v.median()
    d = y[hi].mean() - y[~hi].mean()
    perm = np.array([(lambda h: y[h].mean() - y[~h].mean())(rng.permutation(hi.values)) for _ in range(1000)])
    res.append((i, round(y[hi].mean(), 2), round(y[~hi].mean(), 2), round(d, 2), (np.abs(perm) >= abs(d)).mean()))
Hy = pd.DataFrame(res, columns=["indicator", "above_median", "below_median", "diff", "p_perm"]).sort_values("diff")
print("indicators where ABOVE-median districts have MORE services per hospital (top 8):"); print(sh(Hy.tail(8).iloc[::-1]))
print("indicators where ABOVE-median districts have FEWER (top 8):"); print(sh(Hy.head(8)))
print("share of indicators with p<0.05:", round((Hy.p_perm < .05).mean(), 2), "| overall mean services per hospital:", round(X.svc_per_hosp.mean(), 2))
X.to_csv(os.path.join(ROOT, "analysis/out_district_merged.csv"), index=False)
F[["unique_id", "st", "fdi", "hosp", "public", "n_services", "n_strong"] + ["ev_" + s for s in SV]].to_pickle(os.path.join(ROOT, "analysis/out_fac_features.pkl"))
