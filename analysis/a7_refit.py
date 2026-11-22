"""Refit the trust formula with the rebuilt signs and the reader-cleaned labels; compare variants."""
import sys, os, re
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, OUT, load_facilities
import trust as T0
pd.set_option("display.width", 230)
o = lambda f: pd.read_csv(os.path.join(OUT, f))
F = load_facilities()
nm = F.name.str.lower(); F["neg"] = ""
for k, rx in T0.NEG.items(): F.loc[nm.str.contains(rx, regex=True) & (F.neg == ""), "neg"] = k
F.loc[(F.facilityTypeId == "dentist") & (F.neg == ""), "neg"] = "dental"; F.loc[nm.str.contains(T0.BROAD, regex=True), "neg"] = ""
C = o("claims.csv").merge(F[["unique_id", "name", "address_city", "facilityTypeId", "neg"]], left_on="uid", right_on="unique_id")
C = C.merge(o("location.csv")[["uid", "all_differ", "one_differs"]], on="uid", how="left")
C = C.merge(o("feat_attribution_row.csv")[["uid", "n_other_places_city", "phone_areas_3plus"]], on="uid", how="left")
C = C.merge(o("feat_sources_row.csv")[["uid", "other_sites_2plus"]], on="uid", how="left")
C = C.merge(o("feat_bundles_claim.csv")[["uid", "service", "two_facts", "fit_text_pos_min5"]], on=["uid", "service"], how="left")
C = C.merge(o("feat_sources_claim.csv")[["uid", "service", "svc_in_own_url"]], on=["uid", "service"], how="left")
C["t2"] = (C.tier == 2).astype(int); C["t3"] = (C.tier == 3).astype(int); C["coreq"] = C.coreq_found / C.coreq_total
C["far1"] = (C.n_other_places_city == 1).astype(int); C["far2"] = (C.n_other_places_city >= 2).astype(int)
C["twofacts"] = (C.two_facts.fillna(0) >= 1).astype(int); C["fit"] = C.fit_text_pos_min5.fillna(C.fit_text_pos_min5.median()); C["ownurl"] = C.svc_in_own_url.fillna(0)
for c in ["all_differ", "one_differs", "phone_areas_3plus", "other_sites_2plus"]: C[c] = C[c].fillna(0)
# labels: name-based silver, then corrected by the readers
nml = C.name.str.lower(); C["y"] = np.nan
for s, rx in T0.POS.items(): C.loc[(C.service == s) & nml.str.contains(rx, regex=True) & (C.neg == ""), "y"] = 1
C.loc[(C.neg != "") & C.service.isin(T0.FIT_SERVICES) & ~((C.neg == "skin_hair") & (C.service == "burn_care")), "y"] = 0
C["y_silver"] = C.y; C["claim_id"] = C.uid.str[:8] + ":" + C.service
L = os.path.join(ROOT, "analysis/labels/")
a = pd.read_csv(L + "labels_likely_false_A.csv").merge(pd.read_csv(L + "labels_likely_false_B.csv"), on="claim_id", suffixes=("_a", "_b"))
a["v"] = np.where((a.verdict_a == "false") & (a.verdict_b == "false"), 0.0, np.where((a.verdict_a == "real") & (a.verdict_b == "real"), 1.0, np.nan))
p = pd.read_csv(L + "labels_likely_real.csv"); p["v"] = p.verdict.map({"real": 1.0, "false": 0.0})
g = pd.read_csv(L + "labels_general.csv"); g["v"] = g.verdict.map({"real": 1.0, "false": 0.0})
rd = pd.concat([a[["claim_id", "v"]].assign(src="likely_false"), p[["claim_id", "v"]].assign(src="likely_real"), g[["claim_id", "v"]].assign(src="general")])
C = C.merge(rd.rename(columns={"v": "y_read", "src": "read_src"}), on="claim_id", how="left")
read = C.read_src.notna() & (C.read_src != "general")
C.loc[read, "y"] = C.loc[read, "y_read"]
S = C[C.y.notna()].reset_index(drop=True); hosp = (S.facilityTypeId == "hospital").values
print("claims now:", len(C), "| labelled for fitting:", len(S), "| real", int(S.y.sum()), "| false", int((S.y == 0).sum()), "| at hospitals:", int(hosp.sum()))
def cv(cols, d=S):
    X, y, gp = d[cols].values, d.y.values, d.uid.values; oof = np.zeros(len(d))
    for tr, te in GroupKFold(5).split(X, y, gp): oof[te] = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    return oof
EV = ["t2", "t3", "coreq"]; SIGN = ["all_differ", "one_differs", "far1", "far2", "phone_areas_3plus", "other_sites_2plus", "twofacts"]
variants = {"evidence only": EV, "evidence + row signs": EV + SIGN, "+ own-site page": EV + SIGN + ["ownurl"], "+ context fit": EV + SIGN + ["ownurl", "fit"]}
for k, cols in variants.items():
    oof = cv(cols); print(f"  {k:24s} AUC {roc_auc_score(S.y, oof):.3f} | hospitals only {roc_auc_score(S.y[hosp], oof[hosp]):.3f}")
FINAL = EV + SIGN + ["ownurl"] + (["fit"] if "--fit" in sys.argv else [])
m = LogisticRegression(max_iter=2000).fit(S[FINAL].values, S.y.values)
rng = np.random.default_rng(3); ug = np.unique(S.uid.values); B = []
for _ in range(300):
    idx = np.concatenate([np.where(S.uid.values == u)[0] for u in rng.choice(ug, len(ug))])
    if len(set(S.y.values[idx])) == 2: B.append(LogisticRegression(max_iter=2000).fit(S[FINAL].values[idx], S.y.values[idx]).coef_[0])
lo, hi = np.percentile(B, 5, 0), np.percentile(B, 95, 0)
print("\nmultipliers (90% bootstrap range):")
for i, f in enumerate(FINAL): print(f"  {f:20s} x{np.exp(m.coef_[0][i]):6.2f}  ({np.exp(lo[i]):.2f} to {np.exp(hi[i]):.2f})  n_on={int(S[f].astype(bool).sum())}")
print("  BASE x%.2f" % np.exp(m.intercept_[0]))
C["trust"] = 100 * m.predict_proba(C[FINAL].values)[:, 1]
# independent check 1: the general-hospital packet read by an agent (not used for fitting)
G = C[(C.read_src == "general") & C.y_read.notna()]
print("\ngeneral-hospital packet (not used for fitting): n", len(G), "real", int(G.y_read.sum()), "false", int((G.y_read == 0).sum()))
G2 = C[C.read_src == "general"].merge(pd.read_csv(L + "labels_general.csv")[["claim_id", "verdict"]], on="claim_id")
G2["rv"] = (G2.verdict == "real").astype(int)
print("  AUC of trust for reader verdict real vs (unclear or false):", round(roc_auc_score(G2.rv, G2.trust), 3), "| mean trust by verdict:", G2.groupby("verdict").trust.mean().round(1).to_dict())
# independent check 2: NABH dialysis list
nb = pd.read_csv(os.path.join(ROOT, "research/external/web/finer-official/nabh_dialysis.csv"), dtype=str)
tok = lambda s: set(t for t in re.sub(r"[^a-z0-9 ]", " ", str(s).lower()).split() if len(t) >= 3 and t not in {"hospital", "hospitals", "the", "and", "pvt", "ltd", "private", "limited", "centre", "center", "multispeciality", "multispecialty", "speciality", "super", "clinic", "nursing", "home", "medical", "research", "institute", "care", "health", "healthcare"})
F["pin"] = F.address_zipOrPostcode.astype(str).str.replace(r"\D", "", regex=True).str[:6]; nb["pin"] = nb.pin.astype(str).str.replace(r"\D", "", regex=True).str[:6]
bypin = nb.groupby("pin").name.apply(list).to_dict(); listed = set()
for r in F.itertuples():
    ft = tok(r.name)
    for n in bypin.get(r.pin, []):
        nt = tok(n)
        if ft and nt and len(ft & nt) / min(len(ft), len(nt)) >= 0.6: listed.add(r.unique_id); break
D = C[C.service == "dialysis"].copy(); D["nabh"] = D.uid.isin(listed)
print("\nNABH dialysis list: table facilities matched by PIN + name:", len(listed), "| of those with a dialysis claim:", int(D.nabh.sum()))
print("  median trust: listed", round(D[D.nabh].trust.median(), 1), "| not listed", round(D[~D.nabh].trust.median(), 1), "| AUC listed vs not:", round(roc_auc_score(D.nabh, D.trust), 3), "(tier alone:", round(roc_auc_score(D.nabh, D.tier), 3), ")")
# the known bad record
av = C[C.uid == "b8a5401f-42f1-422a-8cd9-686a15b4cb76"][["service", "tier", "trust"] + SIGN].round(1)
print("\nAravind record claims:"); print(av.to_string(index=False)); print("trust percentile of its dialysis claim among all dialysis claims:", round((D.trust < av[av.service == "dialysis"].trust.iloc[0]).mean() * 100, 1) if (av.service == "dialysis").any() else "claim gone")
C.to_pickle(os.path.join(ROOT, "analysis/out_refit.pkl"))
