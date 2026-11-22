"""Shared yardstick for a candidate feature file.

usage:  python -I analysis/eval_feature.py path/to/features.csv
The CSV needs a `uid` column (facility unique_id) and optionally `service`; every other numeric column is a candidate feature.
Reports, on the name-based silver set (744 claims): each feature's own AUC, the AUC when added to the current formula,
the same restricted to facilityTypeId == 'hospital' (guards against features that only detect "small clinic"), and leave-one-service-out.
"""
import sys, os
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.metrics import roc_auc_score
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
import trust

def cv_auc(S, cols, mask=None):
    X, y, g = S[cols].fillna(0).values, S.y.values, S.uid.values
    oof = np.zeros(len(S))
    for tr, te in GroupKFold(5).split(X, y, g):
        oof[te] = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    if mask is None: return roc_auc_score(y, oof)
    return roc_auc_score(y[mask], oof[mask]) if len(set(y[mask])) == 2 else float("nan")

if __name__ == "__main__":
    C = trust.features(); new = pd.read_csv(sys.argv[1])
    keys = ["uid", "service"] if "service" in new.columns else ["uid"]
    cand = [c for c in new.columns if c not in keys and pd.api.types.is_numeric_dtype(new[c])]
    new = new.rename(columns={c: "f_" + c for c in cand}); cand = ["f_" + c for c in cand]   # avoid clashes with existing columns
    C = C.merge(new[keys + cand].drop_duplicates(keys), on=keys, how="left")
    S = C[C.y.notna()].reset_index(drop=True); hosp = (S.facilityTypeId == "hospital").values
    base = trust.FEATS
    print(f"silver claims {len(S)} | likely real {int(S.y.sum())} | likely false {int((S.y==0).sum())} | of which at hospitals: {int(hosp.sum())} ({int(S.y[hosp].sum())} real, {int((S.y[hosp]==0).sum())} false)")
    b_all, b_h = cv_auc(S, base), cv_auc(S, base, hosp)
    print(f"current formula: AUC {b_all:.3f} | hospitals only {b_h:.3f}")
    rows = []
    for c in cand:
        v = S[c].fillna(0)
        if v.nunique() < 2: rows.append((c, round(S[c].notna().mean(), 2), np.nan, np.nan, np.nan, np.nan)); continue
        a = roc_auc_score(S.y, v); rows.append((c, round(S[c].notna().mean(), 2), round(a, 3), round(roc_auc_score(S.y[hosp], v[hosp]), 3), round(cv_auc(S, base + [c]) - b_all, 3), round(cv_auc(S, base + [c], hosp) - b_h, 3)))
    print(pd.DataFrame(rows, columns=["feature", "coverage", "own_AUC(0.5=useless; <0.5 means higher=false)", "own_AUC_hospitals", "gain_when_added", "gain_hospitals_only"]).to_string(index=False))
    if cand:
        allc = base + cand; print(f"\nall candidates together: AUC {cv_auc(S, allc):.3f} (was {b_all:.3f}) | hospitals only {cv_auc(S, allc, hosp):.3f} (was {b_h:.3f})")
        for s in ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab"]:
            te = (S.service == s).values; X = S[allc].fillna(0).values; Xb = S[base].values
            m = LogisticRegression(max_iter=2000).fit(X[~te], S.y[~te]); mb = LogisticRegression(max_iter=2000).fit(Xb[~te], S.y[~te])
            print(f"  train without {s:20s} test on it: {roc_auc_score(S.y[te], m.predict_proba(X[te])[:,1]):.3f} (current formula {roc_auc_score(S.y[te], mb.predict_proba(Xb[te])[:,1]):.3f})")
