"""NFHS-5 as an outside yardstick: what can the facility table not see?"""
import sys, os, re, difflib
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, load_facilities
pd.set_option("display.width", 220); pd.set_option("display.max_columns", 30)
N = pd.read_csv(os.path.join(ROOT, "nfhs_5_district_health_indicators.csv"))
num = N.drop(columns=["district_name", "state_ut"]).apply(pd.to_numeric, errors="coerce")
print("NFHS", N.shape, "| numeric cols", num.shape[1], "| cols with >10% missing:", int((num.isna().mean() > .1).sum()))

# ---- collinearity inside NFHS
cm = num.corr(method="spearman", min_periods=500).abs()
iu = np.triu_indices_from(cm, 1)
pairs = pd.DataFrame({"a": cm.index[iu[0]], "b": cm.columns[iu[1]], "r": cm.values[iu]}).dropna().sort_values("r", ascending=False)
print("pairs |rho|>=0.9:", int((pairs.r >= .9).sum()), " >=0.8:", int((pairs.r >= .8).sum()), "of", len(pairs))
print(pairs.head(14).assign(a=lambda d: d.a.str[:55], b=lambda d: d.b.str[:55]).to_string(index=False))
z = (num - num.mean()) / num.std(); z = z.fillna(0)
ev = np.linalg.svd(z.values, compute_uv=False) ** 2; ev = ev / ev.sum()
print("PCA variance share, first 5 components:", ev[:5].round(3), "cumulative:", ev[:5].cumsum().round(3))

K = {"inst": "institutional_birth_5y_pct", "pub": "institutional_birth_in_public_facility_5y_pct", "cs": "births_delivered_by_csection_5y_pct",
     "cs_priv": "births_in_a_private_fac_that_were_delivered_by_csection_5y_pct", "cs_pub": "births_in_a_public_fac_that_were_delivered_by_csection_5y_pct",
     "ins": "hh_member_covered_health_insurance_pct", "oop": "average_out_of_pocket_expenditure_per_delivery_in_a_public_fac", "anc4": "mothers_who_had_at_least_4_anc_visits_lb5y_pct"}
D = N[["district_name", "state_ut"]].copy()
for k, c in K.items(): D[k] = pd.to_numeric(N[c], errors="coerce")
D["priv"] = D.inst - D.pub
print("\nNFHS key columns (district medians):"); print(D[list(K) + ["priv"]].describe().loc[["min", "25%", "50%", "75%", "max"]].round(1).to_string())

# ---- combos that should not go together
a = D[(D.inst >= 90) & (D.cs < 5)]
print("\n[combo A] births in a facility >=90% but C-section <5% (reach a facility, almost no surgery):", len(a), "districts")
print(a.state_ut.value_counts().head(6).to_dict()); print(a.sort_values("cs").head(6)[["district_name", "state_ut", "inst", "cs", "cs_pub", "cs_priv"]].to_string(index=False))
b = D[(D.cs_priv >= 60)]
print("\n[combo B] C-section >=60% of private-facility births:", len(b), "districts;", b.state_ut.value_counts().head(6).to_dict())
c = D[(D.cs_pub < 3)]
print("[combo C] C-section <3% of public-facility births:", len(c), "districts;", c.state_ut.value_counts().head(6).to_dict())
print("gap private minus public C-section rate, median:", round((D.cs_priv - D.cs_pub).median(), 1), "points; districts where private rate is 3x+ public:", int((D.cs_priv >= 3 * D.cs_pub).sum()))
print("spearman cs vs inst:", round(D.cs.corr(D.inst, method="spearman"), 2), "| cs vs private birth share:", round(D.cs.corr(D.priv, method="spearman"), 2), "| cs_pub vs cs_priv:", round(D.cs_pub.corr(D.cs_priv, method="spearman"), 2))

# ---- join facilities to NFHS districts
L = pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False)[["unique_id", "best_state", "best_district", "loc_band"]]
F = load_facilities()[["unique_id", "name", "facilityTypeId", "operatorTypeId"]].merge(L, on="unique_id", how="left")
nz = lambda s: re.sub(r"[^A-Z]", "", str(s).upper().replace("&", "AND"))
SA = {"NCTOFDELHI": "DELHI", "JAMMUANDKASHMIR": "JAMMUANDKASHMIR", "ANDAMANANDNICOBARISLANDS": "ANDAMANANDNICOBARISLANDS", "DADRAANDNAGARHAVELIANDDAMANANDDIU": "THEDADRAANDNAGARHAVELIANDDAMANANDDIU", "MAHARASTRA": "MAHARASHTRA"}
D["st"] = D.state_ut.map(nz).map(lambda s: SA.get(s, s)); D["di"] = D.district_name.map(nz)
F["st"] = F.best_state.map(nz); F["di"] = F.best_district.map(nz)
fs = set(F.st.dropna()); print("\nNFHS states not found in facility states:", sorted(set(D.st) - fs))
keymap = {}
for st, g in D.groupby("st"):
    cand = sorted(set(F[F.st == st].di) - {"NAN", ""})
    for di in g.di:
        if di in cand: keymap[(st, di)] = di
        else:
            m = difflib.get_close_matches(di, cand, n=1, cutoff=0.82)
            if m: keymap[(st, di)] = m[0]
D["fdi"] = [keymap.get(k) for k in zip(D.st, D.di)]
agg = F.groupby(["st", "di"]).agg(n_fac=("unique_id", "size"), n_public=("operatorTypeId", lambda s: (s == "public").sum()), n_private=("operatorTypeId", lambda s: (s == "private").sum()), n_hosp=("facilityTypeId", lambda s: (s == "hospital").sum())).reset_index().rename(columns={"di": "fdi"})
D = D.merge(agg, on=["st", "fdi"], how="left")
for c in ["n_fac", "n_public", "n_private", "n_hosp"]: D[c] = D[c].fillna(0)
print("NFHS districts:", len(D), "| name-matched to a facility district:", int(D.fdi.notna().sum()), "| districts with 0 facilities in the table:", int((D.n_fac == 0).sum()), "| with <=2:", int((D.n_fac <= 2).sum()))
print("facilities assigned to an NFHS district:", int(D.n_fac.sum()), "of", len(F))
z0 = D[D.n_fac == 0]
print("\n[data desert] districts with ZERO facilities in the table:", len(z0), "| their median institutional-birth rate:", z0.inst.median(), "% | lowest:", z0.inst.min())
print("  share of those with institutional births >=80%:", round((z0.inst >= 80).mean(), 2))
print("  by state:", z0.state_ut.value_counts().head(8).to_dict())
D["bucket"] = pd.cut(D.n_fac, [-1, 0, 2, 9, 49, 9999], labels=["0", "1-2", "3-9", "10-49", "50+"])
print(D.groupby("bucket", observed=True).agg(districts=("inst", "size"), inst_birth=("inst", "median"), public_share_of_inst=("pub", "median"), csection=("cs", "median"), insurance=("ins", "median")).round(1).to_string())
print("spearman n_fac vs inst:", round(D.n_fac.corr(D.inst, method="spearman"), 2), "| n_fac vs cs:", round(D.n_fac.corr(D.cs, method="spearman"), 2), "| n_fac vs private birth share:", round(D.n_fac.corr(D.priv, method="spearman"), 2))

# ---- public-sector blindness
op = F.operatorTypeId.replace("", "unknown").value_counts(); print("\nfacility operatorTypeId:", op.to_dict())
known = F[F.operatorTypeId.isin(["public", "private"])]
print("table: public share among rows with a known operator:", round((known.operatorTypeId == "public").mean() * 100, 1), "% | among hospitals only:", round((known[known.facilityTypeId == "hospital"].operatorTypeId == "public").mean() * 100, 1), "%")
print("NFHS : public share of institutional births, district median:", round((D.pub / D.inst * 100).median(), 1), "%")
st = D.groupby("state_ut").agg(nfhs_public_share=("pub", lambda s: np.nan), d=("inst", "size"))
D["pub_share_births"] = D.pub / D.inst * 100
S = D.groupby("state_ut").agg(districts=("inst", "size"), births_public_pct=("pub_share_births", "median"), fac=("n_fac", "sum"), fac_public=("n_public", "sum"), fac_private=("n_private", "sum"))
S["table_public_pct"] = (S.fac_public / (S.fac_public + S.fac_private) * 100).round(1); S["gap"] = (S.births_public_pct - S.table_public_pct).round(1)
print(S[S.fac >= 100].sort_values("gap", ascending=False).round(1).head(12).to_string())
D.to_csv(os.path.join(ROOT, "analysis/out_nfhs_district.csv"), index=False)
