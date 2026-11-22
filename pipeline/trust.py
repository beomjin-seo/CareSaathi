"""Step 4: trust score for every (facility, service) claim.

    odds  = BASE x E x C          trust = 100 * odds / (1 + odds)
    E (evidence)  = tier multiplier x coreq multiplier ^ (share of co-requirements found) x own-site-page multiplier
    C (coherence) = product of one multiplier (< 1) per warning sign on the row

Inputs (all rebuilt from raw data by other pipeline steps): claims.csv, location.csv, feat_attribution_row.csv,
feat_sources_row.csv, feat_sources_claim.csv.
Weights are logistic-regression coefficients. Labels: name-based control groups (likely real = the name states the service;
likely false = single-specialty facility claiming acute care), corrected by two independent readers of the likely-false group
and one reader of a sample of the likely-real group (analysis/labels/). Names are never a feature.
Trust is an index for ranking and banding, not a calibrated probability.
"""
import sys, os, json
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, OUT, load_facilities

BROAD = r"multi|general|maternity|nursing home|medical college|trauma|heart|cardiac|kidney|ortho|surgical|children|institute of medical|super ?special|poly ?clinic|hospitals? and|& ?hospital|research cent"
NEG = {"eye": r"\beye\b|netralaya|nethralaya|ophthal|\bvision\b|retina|lasik|drishti|\bnetra\b", "dental": r"dental|dentist|\btooth|teeth|smile|orthodont",
       "skin_hair": r"\bskin\b|derma|\bhair\b|cosmet|aesthetic", "physio": r"physio", "alt_med": r"ayurved|homoeo|homeo|unani|\bsiddha\b|naturopath|panchakarma"}
POS = {"dialysis": r"dialysis|kidney|nephro|\brenal", "emergency_obstetric": r"maternity|matern|women|obstet|gyna?ec|prasuti|zenana", "nicu": r"children|child ?care|pa?ediatric|neonat|newborn|nicu",
       "cardiac_surgery": r"heart|cardiac|cardio", "cath_lab": r"heart|cardiac|cardio", "burn_care": r"\bburn", "blood_bank": r"blood ?bank|blood cent"}
FIT_SERVICES = list(POS)
EVID = {"t2": "medium evidence: a named procedure or unit", "t3": "strong evidence: equipment or a unit, with a quantity or in two fields",
        "coreq": "share of supporting items found (e.g. operating theatre, anaesthesia and blood for a C-section)", "ownurl": "the facility's own website has a page named after this service"}
SIGNS = {"all_differ": "map point, postcode and city all point to different places", "far2": "the text names two or more towns over 60 km away",
         "other_sites_2plus": "the row was built from the websites of two or more other organisations"}
FEATS = list(EVID) + list(SIGNS)


def features():
    o = lambda f: pd.read_csv(os.path.join(OUT, f))
    F = load_facilities(); nm = F.name.str.lower(); F["neg"] = ""
    for k, rx in NEG.items(): F.loc[nm.str.contains(rx, regex=True) & (F.neg == ""), "neg"] = k
    F.loc[(F.facilityTypeId == "dentist") & (F.neg == ""), "neg"] = "dental"; F.loc[nm.str.contains(BROAD, regex=True), "neg"] = ""
    C = o("claims.csv").merge(F[["unique_id", "name", "address_city", "facilityTypeId", "operatorTypeId", "neg"]], left_on="uid", right_on="unique_id")
    C = C.merge(o("location.csv")[["uid", "all_differ"]], on="uid", how="left").merge(o("feat_attribution_row.csv")[["uid", "n_other_places_city"]], on="uid", how="left")
    C = C.merge(o("feat_sources_row.csv")[["uid", "other_sites_2plus"]], on="uid", how="left").merge(o("feat_sources_claim.csv")[["uid", "service", "svc_in_own_url"]], on=["uid", "service"], how="left")
    C["t2"] = (C.tier == 2).astype(int); C["t3"] = (C.tier == 3).astype(int); C["coreq"] = C.coreq_found / C.coreq_total
    C["far2"] = (C.n_other_places_city.fillna(0) >= 2).astype(int); C["ownurl"] = C.svc_in_own_url.fillna(0)
    for c in ["all_differ", "other_sites_2plus"]: C[c] = C[c].fillna(0)
    nml = C.name.str.lower(); C["y"] = np.nan
    for s, rx in POS.items(): C.loc[(C.service == s) & nml.str.contains(rx, regex=True) & (C.neg == ""), "y"] = 1
    C.loc[(C.neg != "") & C.service.isin(FIT_SERVICES) & ~((C.neg == "skin_hair") & (C.service == "burn_care")), "y"] = 0
    C["claim_id"] = C.uid.str[:8] + ":" + C.service; L = os.path.join(ROOT, "analysis", "labels")
    if os.path.exists(os.path.join(L, "labels_likely_false_A.csv")):
        a = pd.read_csv(os.path.join(L, "labels_likely_false_A.csv")).merge(pd.read_csv(os.path.join(L, "labels_likely_false_B.csv")), on="claim_id", suffixes=("_a", "_b"))
        a["v"] = np.where((a.verdict_a == "false") & (a.verdict_b == "false"), 0.0, np.where((a.verdict_a == "real") & (a.verdict_b == "real"), 1.0, np.nan))
        p = pd.read_csv(os.path.join(L, "labels_likely_real.csv")); p["v"] = p.verdict.map({"real": 1.0, "false": 0.0})
        rd = pd.concat([a[["claim_id", "v"]], p[["claim_id", "v"]]]).assign(was_read=1)
        C = C.merge(rd, on="claim_id", how="left"); C.loc[C.was_read == 1, "y"] = C.loc[C.was_read == 1, "v"]
    return C


def fit(S):
    return LogisticRegression(max_iter=2000).fit(S[FEATS].values, S.y.values)


def main():
    C = features(); S = C[C.y.notna()].reset_index(drop=True)
    X, y, g = S[FEATS].values, S.y.values, S.uid.values; hosp = (S.facilityTypeId == "hospital").values
    oof = np.zeros(len(S))
    for tr, te in GroupKFold(5).split(X, y, g): oof[te] = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    m = fit(S); w = dict(zip(FEATS, m.coef_[0])); b0 = float(m.intercept_[0])
    rng = np.random.default_rng(3); ug = np.unique(g); B = []
    for _ in range(300):
        idx = np.concatenate([np.where(g == u)[0] for u in rng.choice(ug, len(ug))])
        if len(set(y[idx])) == 2: B.append(LogisticRegression(max_iter=2000).fit(X[idx], y[idx]).coef_[0])
    lo, hi = np.percentile(B, 5, 0), np.percentile(B, 95, 0)
    print("labelled claims:", len(S), "| real", int(y.sum()), "| false", int((y == 0).sum()))
    print("cross-validated AUC: all", round(roc_auc_score(y, oof), 3), "| hospitals only", round(roc_auc_score(y[hosp], oof[hosp]), 3))
    print("multiplier on the odds (90% bootstrap range):")
    for i, f in enumerate(FEATS): print(f"  {f:18s} x{np.exp(w[f]):6.2f}  ({np.exp(lo[i]):.2f} to {np.exp(hi[i]):.2f})")
    print(f"  BASE               x{np.exp(b0):6.2f}")
    # honesty check: refit without the known bad record, then score it
    AV = "b8a5401f-42f1-422a-8cd9-686a15b4cb76"; m2 = fit(S[S.uid != AV]); av = C[(C.uid == AV) & (C.service == "dialysis")]
    C["E"] = np.exp(sum(w[k] * C[k] for k in EVID)); C["C_row"] = np.exp(sum(w[k] * C[k] for k in SIGNS))
    C["trust"] = (100 * m.predict_proba(C[FEATS].values)[:, 1]).round(1)
    if len(av): print(f"known bad record, dialysis claim: trust {float(C.loc[av.index, 'trust'].iloc[0])} | when the record is left out of fitting: {100 * m2.predict_proba(av[FEATS].values)[0, 1]:.1f}")
    so = pd.DataFrame({"s": 100 * oof, "y": y}).sort_values("s", ascending=False); so["prec"] = so.y.expanding().mean()
    hi_thr = float(so[so.prec >= 0.95].s.min()); sa = so.sort_values("s"); sa["fal"] = (1 - sa.y).expanding().mean(); lo_thr = float(sa[sa.fal >= 0.5].s.max())
    C["band"] = np.where(C.trust >= hi_thr, "high", np.where(C.trust < lo_thr, "low", "medium"))
    print(f"bands: high >= {hi_thr:.0f} | low < {lo_thr:.0f} | all claims: {C.band.value_counts().to_dict()}")
    def reasons(r):
        out = [f"evidence tier {int(r.tier)} of 3", f"{int(r.coreq_found)} of {int(r.coreq_total)} supporting items found" + (f" ({r.coreq_list})" if isinstance(r.coreq_list, str) and r.coreq_list else "")]
        if r.ownurl == 1: out.append(EVID["ownurl"])
        return " | ".join(out + [v for k, v in SIGNS.items() if r[k] == 1])
    C["reasons"] = C.apply(reasons, axis=1)
    keep = ["uid", "name", "address_city", "facilityTypeId", "operatorTypeId", "service", "trust", "band", "E", "C_row", "tier", "coreq_found", "coreq_total", "coreq_list", "ownurl"] + list(SIGNS) + ["quote_field", "quote", "reasons"]
    C[keep].round(3).to_csv(os.path.join(OUT, "trust.csv"), index=False)
    json.dump({"base": b0, "weights": w, "features": FEATS, "high_threshold": hi_thr, "low_threshold": lo_thr, "auc_cv": float(roc_auc_score(y, oof)), "auc_cv_hospitals": float(roc_auc_score(y[hosp], oof[hosp])), "n_labelled": int(len(S))}, open(os.path.join(OUT, "weights.json"), "w"), indent=1)
    ACUTE = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "burn_care", "cath_lab", "icu", "ventilator", "blood_bank", "stroke", "chemotherapy", "radiotherapy"]
    ng = C[(C.neg != "") & C.service.isin(ACUTE)]; print("single-specialty facilities, acute-care claims:", len(ng), "| high", int((ng.band == "high").sum()), "| medium", int((ng.band == "medium").sum()), "| low", int((ng.band == "low").sum()))
    L = os.path.join(ROOT, "analysis", "labels", "labels_general.csv")
    if os.path.exists(L):
        G = pd.read_csv(L).merge(C[["claim_id", "trust", "band"]], on="claim_id"); print("general-hospital packet read by an independent reader (not used for fitting):"); print(pd.crosstab(G.band, G.verdict).to_string())
        print("  AUC, real vs unclear-or-false:", round(roc_auc_score((G.verdict == "real").astype(int), G.trust), 3))


if __name__ == "__main__":
    main()
