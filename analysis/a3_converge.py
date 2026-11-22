"""Do independent kinds of warning signs point at the same rows? Plus: who really owns a mis-filed sentence?"""
import sys, os, re, collections
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, OUT, load_facilities, norm_name
pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 160)
F = load_facilities(); Cl = pd.read_csv(os.path.join(OUT, "claims.csv"))
M = pd.read_csv(os.path.join(ROOT, "research/data_work/record_contamination.csv")).drop_duplicates("unique_id")
L = pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False).drop_duplicates("unique_id")
Wn = pd.read_csv(sys.argv[1])[["unique_id", "attr_f", "coherence"]].drop_duplicates("unique_id")
F = F.merge(M[["unique_id", "t_located_elsewhere", "n_std", "n_ov", "n_dom"]], on="unique_id", how="left").merge(L[["unique_id", "loc_class", "best_state", "best_district"]], on="unique_id", how="left").merge(Wn, on="unique_id", how="left")
F["nn"] = F.name.map(norm_name)

# ---- specific sentences (contain a number) filed under hospitals with different names in different cities
sent = collections.defaultdict(set)
for r in F.itertuples():
    for fld in ("procedure_l", "equipment_l", "capability_l"):
        for t in getattr(r, fld):
            if len(t) >= 45 and re.search(r"\d", t): sent[re.sub(r"\W+", " ", t.lower()).strip()].add(r.Index)
spec = {}
for k, v in sent.items():
    if len(v) >= 2 and len({F.at[i, "nn"] for i in v}) >= 2 and len({F.at[i, "address_city"].lower() for i in v}) >= 2: spec[k] = v
cnt = collections.Counter(i for v in spec.values() for i in v); F["n_spec_collide"] = F.index.map(lambda i: cnt.get(i, 0))
print("specific sentences (>=45 chars, contain a number):", len(sent), "| filed under different-name, different-city rows:", len(spec), "| rows touched:", int((F.n_spec_collide >= 1).sum()), "| rows with >=3:", int((F.n_spec_collide >= 3).sum()))
for k, v in sorted(spec.items(), key=lambda kv: -len(kv[1]))[:5]: print("   *", k[:110], "->", [F.at[i, "name"][:26] + "/" + F.at[i, "address_city"][:10] for i in list(v)[:4]])
av = F.index[F.unique_id == "b8a5401f-42f1-422a-8cd9-686a15b4cb76"][0]
co = collections.Counter(j for k, v in spec.items() if av in v for j in v if j != av)
print("\nAravind row shares", sum(1 for v in spec.values() if av in v), "specific sentences with other rows. Co-owners:")
for j, n in co.most_common(6): print(f"   {n:3d} shared sentences with: {F.at[j,'name']} | {F.at[j,'address_city']} | PIN {F.at[j,'address_zipOrPostcode']} | type {F.at[j,'facilityTypeId']}")
dia = [k for k, v in spec.items() if av in v and "dialys" in k]
print("   dialysis sentences shared:", dia[:3])

# ---- convergence between independent families of warning signs
S = pd.DataFrame({
    "geo: location cells disagree": F.loc_class.isin(["B_latlon_outlier", "C_postcode_outlier", "D_city_outlier", "E_all_disagree", "G_ll_pc_disagree_nocity"]),
    "text: sentence names another place": F.t_located_elsewhere.fillna(0) > 0,
    "contact: phone codes from 3+ areas": F.n_std.fillna(0) >= 3,
    "source: 6+ distinct source ids": F.n_ov.fillna(0) >= 6,
    "collision: specific sentence also filed elsewhere": F.n_spec_collide >= 1,
    "LLM (1st-place team): claims about another facility": F.attr_f.fillna(1) < 0.7,
})
print("\nbase rates:", (S.mean() * 100).round(1).to_dict())
lift = pd.DataFrame({a: {b: (S[b][S[a]].mean() / S[b].mean()) if a != b else np.nan for b in S} for a in S}).round(1)
lift.index = [c.split(":")[0] for c in lift.index]; lift.columns = [c.split(":")[0] for c in lift.columns]
print("lift = P(row has sign B | has sign A) / P(sign B). 1.0 means unrelated."); print(lift.to_string())
k = S.sum(axis=1); print("rows by number of independent families firing:", k.value_counts().sort_index().to_dict())
F["n_families"] = k
# negative controls with an impossible claim, by number of families
nm = F.name.str.lower()
BROAD = r"multi|general|maternity|nursing home|medical college|trauma|heart|cardiac|kidney|ortho|surgical|children|institute of medical|super ?special|poly ?clinic|hospitals? and|& ?hospital|research cent"
ng = (nm.str.contains(r"\beye\b|netralaya|nethralaya|ophthal|\bvision\b|retina|lasik|drishti|\bnetra\b|dental|dentist|\btooth|teeth|smile|orthodont|\bskin\b|derma|\bhair\b|cosmet|aesthetic|physio|ayurved|homoeo|homeo|unani|siddha|naturopath|panchakarma", regex=True) | F.facilityTypeId.eq("dentist")) & ~nm.str.contains(BROAD, regex=True)
ACUTE = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "burn_care"]
T = Cl[Cl.service.isin(ACUTE)].pivot(index="uid", columns="service", values="tier").reindex(F.unique_id).fillna(0); T.index = F.index
imp = ng & (T >= 2).any(axis=1)
print("\nknown-wrong rows (single-specialty facility with an acute-care claim, tier>=2):", int(imp.sum()))
print("share of rows that are known-wrong, by number of families firing (within the", int(ng.sum()), "control facilities):")
print(pd.DataFrame({"controls": ng.groupby(k).sum(), "known_wrong": imp.groupby(k).sum()}).assign(rate=lambda d: (d.known_wrong / d.controls * 100).round(1)).to_string())
print("\nknown-wrong rows with ZERO families firing (the ones every detector misses):")
for i in F.index[imp & (k == 0)][:8]:
    s = T.loc[i]; s = s[s >= 2].index[0]; q = Cl[(Cl.uid == F.at[i, "unique_id"]) & (Cl.service == s)].iloc[0]
    print("   -", F.at[i, "name"][:40], "|", F.at[i, "address_city"], "|", s, "|", q.quote_field, "::", str(q.quote)[:110])
F[["unique_id", "n_spec_collide", "n_families"]].to_csv(os.path.join(ROOT, "analysis/out_families.csv"), index=False)

# ---- NFHS x claims: does text evidence line up with what the survey says happens in the district?
D = pd.read_csv(os.path.join(ROOT, "analysis/out_nfhs_district.csv"))
nz = lambda s: re.sub(r"[^A-Z]", "", str(s).upper().replace("&", "AND"))
F["st"] = F.best_state.map(nz); F["fdi"] = F.best_district.map(nz)
ob = Cl[Cl.service == "emergency_obstetric"].set_index("uid").tier.reindex(F.unique_id).fillna(0).values
F["ob2"] = ob >= 2; F["ob1"] = ob == 1; F["pub"] = F.operatorTypeId.isin(["public", "government"])
A = F.groupby(["st", "fdi"]).agg(ob_strong=("ob2", "sum"), ob_weak=("ob1", "sum"), ob_strong_public=("ob2", lambda s: (s & F.loc[s.index, "pub"]).sum())).reset_index()
D = D.merge(A, on=["st", "fdi"], how="left").fillna({"ob_strong": 0, "ob_weak": 0, "ob_strong_public": 0})
D["b"] = pd.cut(D.ob_strong, [-1, 0, 2, 9, 999], labels=["0", "1-2", "3-9", "10+"])
print("\ndistricts grouped by number of facilities with obstetric evidence tier>=2 in the table:")
print(D.groupby("b", observed=True).agg(districts=("cs", "size"), csection_rate=("cs", "median"), csection_in_private=("cs_priv", "median"), csection_in_public=("cs_pub", "median"), inst_birth=("inst", "median")).round(1).to_string())
m = D.n_fac > 0
print("spearman with district C-section rate (districts with >=1 facility): strong-evidence count", round(D[m].ob_strong.corr(D[m].cs, method="spearman"), 2), "| weak-only count", round(D[m].ob_weak.corr(D[m].cs, method="spearman"), 2), "| all facilities", round(D[m].n_fac.corr(D[m].cs, method="spearman"), 2))
low = D[D.cs_pub < 3]
print("\n49-ish districts where public facilities do almost no C-sections (<3%):", len(low), "| table has 0 facilities:", int((low.n_fac == 0).sum()), "| has >=1 obstetric tier>=2 facility:", int((low.ob_strong >= 1).sum()), "| of those facilities, public:", int(low.ob_strong_public.sum()), "of", int(low.ob_strong.sum()))
print(low.sort_values("cs_pub").head(8)[["district_name", "state_ut", "inst", "pub", "cs_pub", "cs_priv", "n_fac", "ob_strong"]].to_string(index=False))
for q in ["Araria", "Gadchiroli", "Gaya", "Patna", "Purbi Champaran", "Muzaffarpur"]:
    r = D[D.district_name.str.lower() == q.lower()]
    if len(r): r = r.iloc[0]; print(f"  {q}: births in a facility {r.inst}% (public {r['pub']}%), C-section {r.cs}% (public {r.cs_pub}%, private {r.cs_priv}%), table facilities {int(r.n_fac)}, obstetric tier>=2 {int(r.ob_strong)}")
