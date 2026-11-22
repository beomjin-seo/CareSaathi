"""Natural control groups, repeated rows and sentence collisions: evidence about the evidence."""
import sys, os, re, collections
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "pipeline"))
from common import ROOT, OUT, load_facilities, norm_name, haversine
pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30); pd.set_option("display.max_colwidth", 150)
F = load_facilities(); Cl = pd.read_csv(os.path.join(OUT, "claims.csv")); H = pd.read_pickle(os.path.join(OUT, "hits.pkl"))
M = pd.read_csv(os.path.join(ROOT, "research/data_work/record_contamination.csv")).drop_duplicates("unique_id")
L = pd.read_csv(os.path.join(ROOT, "research/data_work/facility_location.csv"), low_memory=False).drop_duplicates("unique_id")
F = F.merge(M[["unique_id", "tier", "t_located_elsewhere", "n_std", "n_ov", "n_dom"]].rename(columns={"tier": "mix"}), on="unique_id", how="left").merge(L[["unique_id", "loc_class", "loc_band", "d_pc_km"]], on="unique_id", how="left")
nm = F.name.str.lower()
SERV = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "mri", "burn_care", "trauma_emergency"]
T = Cl[Cl.service.isin(SERV)].pivot(index="uid", columns="service", values="tier").reindex(F.unique_id).fillna(0).astype(int); T.index = F.index

# ---------- 1. control groups from the facility NAME
BROAD = r"multi|general|maternity|nursing home|medical college|trauma|heart|cardiac|kidney|ortho|surgical|children|institute of medical|super ?special|poly ?clinic|hospitals? and|& ?hospital|research cent"
NEG = {"eye": r"\beye\b|netralaya|nethralaya|ophthal|\bvision\b|retina|lasik|drishti|\bnetra\b", "dental": r"dental|dentist|\btooth|teeth|smile|orthodont",
       "skin_hair": r"\bskin\b|derma|\bhair\b|cosmet|aesthetic", "physio": r"physio", "alt_med": r"ayurved|homoeo|homeo|unani|siddha|naturopath|panchakarma"}
neg = pd.Series("", index=F.index)
for k, rx in NEG.items(): neg[nm.str.contains(rx, regex=True) & (neg == "")] = k
neg[(F.facilityTypeId == "dentist") & (neg == "")] = "dental"
neg[nm.str.contains(BROAD, regex=True)] = ""
POS = {"dialysis": r"dialysis|kidney|nephro|\brenal", "emergency_obstetric": r"maternity|matern|women|obstet|gyna?ec|prasuti|zenana", "nicu": r"children|child ?care|pa?ediatric|neonat|newborn|nicu",
       "cardiac_surgery": r"heart|cardiac|cardio", "mri": r"\bmri\b|imaging|\bscan|diagnostic|radiolog", "burn_care": r"\bburn", "trauma_emergency": r"trauma|accident"}
print("NEGATIVE controls (single-specialty by name):", neg[neg != ""].value_counts().to_dict(), "total", int((neg != "").sum()))
ACUTE = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "burn_care"]
ng = neg != ""
gate = ng & ~(F.mix.eq("HIGH") | F.loc_band.eq("low"))
rows = []
for s in ACUTE:
    rows.append((s, int((T.loc[ng, s] >= 1).sum()), int((T.loc[ng, s] >= 2).sum()), int((T.loc[ng, s] >= 3).sum()), int((T.loc[gate, s] >= 2).sum()), int((T.loc[gate, s] >= 3).sum())))
R = pd.DataFrame(rows, columns=["service", "keyword_any", "tier>=2", "tier3", "tier>=2 after row gate", "tier3 after row gate"])
print("how many of the", int(ng.sum()), "negative-control facilities 'offer' each acute service:"); print(R.to_string(index=False))
anyk = (T.loc[ng, ACUTE] >= 1).any(axis=1); any2 = (T.loc[ng, ACUTE] >= 2).any(axis=1); any2g = (T.loc[gate, ACUTE] >= 2).any(axis=1)
print("negative controls with >=1 impossible claim: keyword", int(anyk.sum()), f"({anyk.mean():.1%}) | tier>=2", int(any2.sum()), f"({any2.mean():.1%}) | tier>=2 after gate", int(any2g.sum()), f"({any2g.sum()/ng.sum():.1%} of all controls)")
bad = ng & (T[ACUTE] >= 2).any(axis=1)
print("  among controls WITH an impossible tier>=2 claim: mix HIGH", f"{F[bad].mix.eq('HIGH').mean():.0%}", "| loc not consistent", f"{(~F[bad].loc_class.eq('A_all_agree')).mean():.0%}", "| other-place sentence", f"{(F[bad].t_located_elsewhere > 0).mean():.0%}")
okc = ng & ~(T[ACUTE] >= 1).any(axis=1)
print("  among controls with NO impossible claim   : mix HIGH", f"{F[okc].mix.eq('HIGH').mean():.0%}", "| loc not consistent", f"{(~F[okc].loc_class.eq('A_all_agree')).mean():.0%}", "| other-place sentence", f"{(F[okc].t_located_elsewhere > 0).mean():.0%}")
print("\nPOSITIVE controls vs NEGATIVE controls: share with each evidence tier, and likelihood ratio (pos/neg)")
out = []
hosp = F.facilityTypeId.eq("hospital")
for s, rx in POS.items():
    p = nm.str.contains(rx, regex=True) & (neg == "")
    for lab, mask in [("tier3", T[s] == 3), ("tier2", T[s] == 2), ("tier1", T[s] == 1), ("none", T[s] == 0)]:
        pp = (mask & p).sum() / p.sum(); pn = ((mask & ng).sum() + 0.5) / (ng.sum() + 1)
        out.append((s, int(p.sum()), lab, round(pp * 100, 1), round(pn * 100, 2), round(pp / pn, 1), round(np.log2(pp / pn), 1) if pp > 0 else np.nan))
O = pd.DataFrame(out, columns=["service", "n_pos", "evidence", "%pos", "%neg", "LR", "log2LR"])
print(O.to_string(index=False))
# specialties enum circularity
spec = F.specialties_l.map(lambda l: " ".join(set(l)).lower())
for s, rx, sp in [("dialysis", POS["dialysis"], "nephrolog"), ("cardiac", POS["cardiac_surgery"], "cardio"), ("eye(neg)", NEG["eye"], "ophthal")]:
    p = nm.str.contains(rx, regex=True)
    print(f"specialties has '{sp}': when name matches {s}: {spec[p].str.contains(sp).mean():.0%} | otherwise: {spec[~p].str.contains(sp).mean():.0%}")

# ---------- 2. the same facility recorded twice: do the two rows agree?
F["nn"] = F.name.map(norm_name)
g = F[F.latitude_n.notna()].groupby("nn").filter(lambda d: 2 <= len(d) <= 6)
pairs = []
for _, d in g.groupby("nn"):
    ix = list(d.index)
    for i in range(len(ix)):
        for j in range(i + 1, len(ix)):
            a, b = F.loc[ix[i]], F.loc[ix[j]]
            if haversine(a.latitude_n, a.longitude_n, b.latitude_n, b.longitude_n) <= 1.0: pairs.append((ix[i], ix[j]))
print("\nREPEATED ROWS: same normalised name within 1 km:", len(pairs), "pairs")
rep = collections.defaultdict(lambda: [0, 0])
for i, j in pairs:
    for s in SERV:
        for a, b in ((i, j), (j, i)):
            t = T.at[a, s]; rep[t][0] += 1; rep[t][1] += int(T.at[b, s] >= 1)
print("if one row has evidence tier t for a service, how often does its twin row mention that service at all?")
for t in [3, 2, 1, 0]: print(f"  tier {t}: {rep[t][1]}/{rep[t][0]} = {rep[t][1]/max(1,rep[t][0]):.0%}")

# ---------- 3. sentence collisions: the same long sentence filed under different hospitals
sent = collections.defaultdict(set)
for r in F.itertuples():
    for fld in ("procedure_l", "equipment_l", "capability_l"):
        for t in getattr(r, fld):
            if len(t) >= 45: sent[re.sub(r"\W+", " ", t.lower()).strip()].add(r.Index)
multi = {k: v for k, v in sent.items() if len(v) >= 2}
print("\nSENTENCE COLLISIONS: distinct long sentences (>=45 chars):", len(sent), "| filed under 2+ rows:", len(multi), f"({len(multi)/len(sent):.1%}) | under 5+ rows:", sum(1 for v in multi.values() if len(v) >= 5))
diff = {}
for k, v in multi.items():
    names = {F.at[i, "nn"] for i in v}; cities = {F.at[i, "address_city"].lower() for i in v}
    if len(names) >= 2 and len(cities) >= 2: diff[k] = v
rows_hit = set().union(*diff.values()) if diff else set()
print("  filed under rows with DIFFERENT names AND different cities:", len(diff), "sentences, touching", len(rows_hit), "rows")
cnt = collections.Counter(i for v in diff.values() for i in v); F["n_collide"] = F.index.map(lambda i: cnt.get(i, 0))
print("  rows with >=3 colliding sentences:", int((F.n_collide >= 3).sum()), "| >=10:", int((F.n_collide >= 10).sum()))
ex = sorted(diff.items(), key=lambda kv: -len(kv[1]))
for k, v in [e for e in ex if re.search(r"dialys|nicu|cath lab|c section|caesar|cardiac surg|burn|mri", e[0])][:6]:
    print("   *", k[:120], "->", [F.at[i, "name"][:28] + "/" + F.at[i, "address_city"][:12] for i in list(v)[:4]])
# does collision agree with the other, independent problem signals?
print("  collision (>=3) vs other signals:")
for lab, m in [("mix HIGH (draft detector)", F.mix.eq("HIGH")), ("location cells disagree", ~F.loc_class.isin(["A_all_agree", "F_ll_pc_agree_nocity", "H_ll_city_agree_nopc"])), ("phone area codes >=3", F.n_std >= 3), ("distinct source ids >=6", F.n_ov >= 6), ("negative control w/ impossible claim", bad)]:
    a = m[F.n_collide >= 3].mean(); b = m[F.n_collide == 0].mean(); print(f"    {lab:38s} {a:.0%} among colliding rows vs {b:.0%} among non-colliding  (x{a/max(b,1e-9):.1f})")
F[["unique_id", "n_collide"]].to_csv(os.path.join(ROOT, "analysis/out_collisions.csv"), index=False)

# ---------- 4. coordinates stacked on one point; numbers that should move together
xy = F.latitude_n.round(5).astype(str) + "," + F.longitude_n.round(5).astype(str); vc = xy[F.latitude_n.notna()].value_counts()
print("\nSTACKED COORDINATES: rows sharing an identical point with 2+ others:", int(vc[vc >= 3].sum()), "| biggest stacks:", vc.head(4).to_dict())
d, c = F.numberDoctors_n, F.capacity_n
both = d.notna() & c.notna() & (d > 0) & (c > 0)
print("doctors & beds both present:", int(both.sum()), "| spearman:", round(d[both].corr(c[both], method="spearman"), 2), "| more doctors than beds x3:", int((d[both] > 3 * c[both]).sum()), "| beds>=100 at a 'clinic'/'dentist':", int(((c >= 100) & F.facilityTypeId.isin(["clinic", "dentist"])).sum()))
print("capability list length by type (median):", F.groupby("facilityTypeId").capability_l.apply(lambda s: s.map(len).median()).to_dict())
pubname = nm.str.contains(r"\bgovt\b|government|district hospital|civil hospital|\bchc\b|\bphc\b|community health|primary health|sadar|sub ?divisional|\besi\b|railway hospital|municipal|\baiims\b|taluk|general hospital", regex=True)
print("\nPUBLIC by name:", int(pubname.sum()), "| of those, operatorTypeId:", F[pubname].operatorTypeId.replace("", "unknown").value_counts().to_dict())
print("public by name OR operator:", int((pubname | F.operatorTypeId.isin(["public", "government"])).sum()), "of", len(F))
