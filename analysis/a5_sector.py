"""Sharper tests of the 'district indicator -> facility capability' idea, plus claimed-vs-delivered mismatches."""
import sys, os, re
import numpy as np, pandas as pd
from scipy import stats
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT
pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_colwidth", 60)
rng = np.random.default_rng(11)
R = pd.read_csv(os.path.join(ROOT, "analysis/out_scan.csv")); X = pd.read_csv(os.path.join(ROOT, "analysis/out_district_merged.csv"))
Ff = pd.read_pickle(os.path.join(ROOT, "analysis/out_fac_features.pkl"))
N = pd.read_csv(os.path.join(ROOT, "nfhs_5_district_health_indicators.csv")).merge(pd.read_csv(os.path.join(ROOT, "analysis/out_nfhs_district.csv"))[["district_name", "state_ut", "st", "fdi"]], on=["district_name", "state_ut"])
for c in N.columns[2:-2]: N[c] = pd.to_numeric(N[c], errors="coerce")
CS, CSV_, CSU, INST = "births_delivered_by_csection_5y_pct", "births_in_a_private_fac_that_were_delivered_by_csection_5y_pct", "births_in_a_public_fac_that_were_delivered_by_csection_5y_pct", "institutional_birth_5y_pct"

print("PAIRS you would expect to be linked (district level, 202 districts with >=5 hospitals):")
want = [(CS, "ev_emergency_obstetric"), (CSV_, "ev_emergency_obstetric"), (INST, "ev_emergency_obstetric"), (CS, "ev_nicu"),
        ("women_age_30_49_years_ever_undergone_a_breast_exam_pct", "ev_chemotherapy"), ("women_age_30_49_years_ever_undergone_a_cervical_screen_pct", "ev_radiotherapy"),
        ("m15_plus_with_high_or_very_high_gt_140_mg_dl_blood_sugar_or_pct", "ev_dialysis"), ("m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "ev_dialysis"),
        ("m15_plus_with_high_bp_sys_gte_140_mmhg_and_or_dia_gte_90_mm_pct", "ev_cath_lab"), ("all_w15_49_who_are_anaemic_pct", "ev_blood_bank"),
        ("m15_plus_who_use_any_kind_of_tobacco_pct", "ev_chemotherapy"), ("hh_member_covered_health_insurance_pct", "svc_per_hosp"), ("hh_member_covered_health_insurance_pct", "public_share"),
        ("institutional_birth_in_public_facility_5y_pct", "public_share")]
for i, m in want:
    r = R[(R.indicator == i) & (R.facility_measure == m)]
    if len(r): r = r.iloc[0]; print(f"  {i[:58]:58s} x {m:22s} rho {r.rho:+.2f}  after controls {r.partial:+.2f}  q {r.q_partial:.2f}")

# ---- facility-level, sector-specific: does a hospital's own text line up with what its sector does in its district?
G = Ff.merge(N[["st", "fdi", CS, CSV_, CSU, INST]], on=["st", "fdi"], how="inner"); G = G[G.hosp]
def tercile_test(sub, col, y, label):
    d = sub.dropna(subset=[col]); dist = d.groupby(["st", "fdi"]).agg(v=(col, "first"), n=(y, "size"), k=(y, "sum")).reset_index()
    dist["t"] = pd.qcut(dist.v.rank(method="first"), 3, labels=["low", "mid", "high"])
    tab = dist.groupby("t", observed=True).agg(districts=("v", "size"), indicator_median=("v", "median"), hospitals=("n", "sum"), with_evidence=("k", "sum")); tab["share_%"] = (tab.with_evidence / tab.hospitals * 100).round(1)
    obs = tab["share_%"]["high"] - tab["share_%"]["low"]
    perm = []
    for _ in range(2000):
        t = rng.permutation(dist.t.values); a = dist[t == "high"]; b = dist[t == "low"]; perm.append(a.k.sum() / a.n.sum() * 100 - b.k.sum() / b.n.sum() * 100)
    p = (np.abs(perm) >= abs(obs)).mean()
    print(f"\n{label}\n{tab.round(1).to_string()}\n  high minus low = {obs:+.1f} points, permutation p = {p:.3f} (districts shuffled, not hospitals)")
tercile_test(G[G.public == 0], CSV_, "ev_emergency_obstetric", "PRIVATE hospitals: obstetric evidence (tier>=2) by the district's private-facility C-section rate")
tercile_test(G[G.public == 1], CSU, "ev_emergency_obstetric", "PUBLIC hospitals: obstetric evidence (tier>=2) by the district's public-facility C-section rate")
tercile_test(G, CS, "ev_emergency_obstetric", "ALL hospitals: obstetric evidence by the district's overall C-section rate")
tercile_test(G, INST, "ev_emergency_obstetric", "ALL hospitals: obstetric evidence by the district's facility-birth rate")
G["many"] = (G.n_services >= 4).astype(float)
tercile_test(G, "women_age_15_49_with_10_or_more_years_of_schooling_pct" if False else CS, "many", "ALL hospitals: 4+ services with evidence, by overall C-section rate")

# ---- claimed vs delivered, per district
X["claimed"] = X["ev_emergency_obstetric"]; d = X.dropna(subset=[CS, "claimed"]).copy()
d["cl_r"] = d.claimed.rank(pct=True); d["cs_r"] = d[CS].rank(pct=True)
a = d[(d.cl_r >= .67) & (d.cs_r <= .33)].sort_values("claimed", ascending=False); b = d[(d.cl_r <= .33) & (d.cs_r >= .67)].sort_values(CS, ascending=False)
cols = ["district_name", "state_ut", "n_hosp", "claimed", CS, CSU, CSV_, INST]
ren = {"claimed": "hosp_with_obstetric_evidence", CS: "csection_all", CSU: "cs_public", CSV_: "cs_private", INST: "facility_births"}
print("\nMISMATCH A: many hospitals claim obstetric surgery, but few C-sections happen in the district:", len(a)); print(a[cols].rename(columns=ren).head(8).round(2).to_string(index=False))
print("\nMISMATCH B: few hospitals in the table show obstetric evidence, but many C-sections happen:", len(b)); print(b[cols].rename(columns=ren).head(8).round(2).to_string(index=False))

# ---- where is the table least reliable?
Fa = pd.read_csv(os.path.join(ROOT, "research/data_work/record_contamination.csv")).drop_duplicates("unique_id")[["unique_id", "tier"]].merge(
     pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False).drop_duplicates("unique_id")[["unique_id", "best_state", "loc_class"]], on="unique_id")
Fa["mix_high"] = Fa.tier.eq("HIGH"); Fa["loc_bad"] = Fa.loc_class.isin(["B_latlon_outlier", "C_postcode_outlier", "D_city_outlier", "E_all_disagree", "G_ll_pc_disagree_nocity"])
S = Fa.groupby("best_state").agg(rows=("unique_id", "size"), mix_high_pct=("mix_high", lambda s: s.mean() * 100), loc_bad_pct=("loc_bad", lambda s: s.mean() * 100)); S = S[S.rows >= 100].round(1)
print("\nROW RELIABILITY BY STATE (states with >=100 rows). India overall: mix HIGH", round(Fa.mix_high.mean() * 100, 1), "% | location cells disagree", round(Fa.loc_bad.mean() * 100, 1), "%")
print("worst:"); print(S.sort_values("mix_high_pct", ascending=False).head(6).to_string()); print("best:"); print(S.sort_values("mix_high_pct").head(6).to_string())
