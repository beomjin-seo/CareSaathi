"""Candidate features, family "do the claims in a record fit together?"

    python -I pipeline/feat_bundles.py            # writes pipeline/out/feat_bundles_claim.csv (one row per uid x service), about 2.5 min
    python -I pipeline/feat_bundles.py --rebuild  # ignore the pipeline/out/hits.pkl cache and re-extract from facilities.csv (about 2 min more)
    python -I pipeline/feat_bundles.py --check    # also print diagnostics on the silver labels (needs trust.py; not needed for the CSV)
    python -I pipeline/feat_bundles.py --words    # also print the words that raise / lower the expectation of a service

Inputs for the CSV: facilities.csv only (through common.load_facilities and the sentence matcher claims.build_hits; pipeline/out/hits.pkl is
used as a cache of that matcher when it is newer than its inputs). No research/data_work.
Nothing here reads the facility name's specialty words, facilityTypeId or the specialties column to decide a claim. The name is used
in two ways only: its own words are DELETED from every sentence before the word model sees it, and the full name is blanked before
looking for self-descriptions, so neither can read the name back out of a sentence.

Columns written (plain meaning in brackets). All models are cross-fitted: a record is scored by a model that never saw it.
 1 bundles         comp_share        [of the 5 services that most often accompany this one in the whole table, the share found here]
                   lonely            [no other service is named at medium evidence or better]
                   pmi_mean          [average strength of association between this service and the other services the record names]
                   fit_flags         [how expected is this service given WHICH other services the record shows]
                   fit_text          [how expected is this service given the WORDS of every sentence that does not mention it]
                   fit_text_nospec   [same, after removing every word the silver labels were built from (eye, dental, kidney, heart ...)]
                   fit_text_pos      [same, companion words only: a word can raise the score, never lower it]
                   fit_text_pos_min5 [fit_text_pos, set to the service's typical value when the record has fewer than 5 other sentences]
                   n_other_t2, claims_most   [how many other services the record names; 12+ of 19 = "claims almost everything"]
 2 contradictions  bed_conflict      [two total bed counts in the record (text or capacity column) differ by 1.5x or more]
                   doc_conflict      [two doctor head-counts differ by 3x or more]
                   docs_vs_beds      [50+ beds but 2 or fewer doctors recorded]
                   year_conflict     [two founding years 10+ years apart]
                   two_facts         [how many of the four above fire: the record answers the same basic question in two ways]
                   ident_conflict    [the text describes the facility as single-specialty AND as general, or as two specialties]
                   unit_gt_total     [a single unit is stated to have more beds than the whole facility]
                   acute_vs_size     [4+ high-acuity services at a place whose stated size is tiny]
                   neg_pos           [one sentence says the service is unavailable/elsewhere/planned, another claims it]
 3 co-requirements coreq_indep       [share of co-requirements found in a sentence that does not itself mention the service]
                   coreq_clean       [... found in a sentence with no caution flag]
                   coreq_infra       [... found in the equipment list or in an infrastructure sentence]
                   coreq_near        [... found within 5 list items of the claim sentence]
                   coreq_strict      [independent + clean + infrastructure]
Not written, shown by --check only: *_resid (score minus what record length predicts), year_bad (founding year after 2025 or before 1700).
"""
import sys, os, re, time
import numpy as np, pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.preprocessing import normalize
from sklearn.model_selection import KFold
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_facilities, OUT, ROOT
import claims as CL
from ontology import SERVICE_ONTOLOGY as ONT

I = re.I
SERVICES = list(ONT)
ACUTE = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab", "icu", "ventilator", "blood_bank", "burn_care", "stroke", "chemotherapy", "radiotherapy"]
T0 = time.time()
log = lambda *a: print(f"[{time.time() - T0:5.0f}s]", *a, flush=True)


# ---------------------------------------------------------------- inputs
def get_hits(df):
    hp = os.path.join(OUT, "hits.pkl")
    src = [os.path.join(ROOT, "facilities.csv")] + [os.path.join(ROOT, "pipeline", f) for f in ("claims.py", "ontology.py", "common.py")]
    if os.path.exists(hp) and os.path.getmtime(hp) >= max(os.path.getmtime(x) for x in src) and "--rebuild" not in sys.argv:
        log("using pipeline/out/hits.pkl (newer than facilities.csv and claims.py)")
        return pd.read_pickle(hp)
    log("re-extracting service sentences from facilities.csv with claims.build_hits (about 2 min)")
    return CL.build_hits(df)


def tiers(H):
    """One row per (facility, service) with the evidence tier, same rule as claims.build_claims but vectorised."""
    v = H[H["flags"].eq("")]
    g = lambda d, name, f: d.groupby(["uid", "service"])[f[0]].agg(f[1]).rename(name)
    T = pd.concat([H.groupby(["uid", "service"]).size().rename("n_hits"),
                   g(v[v.cls == "infra"], "vi", ("seg", "size")), g(v[v.cls == "infra"], "viq", ("qty", "any")), g(v[v.cls == "proc"], "vp", ("seg", "size")),
                   g(v[v.cls.isin(["infra", "proc"])], "nf", ("field", "nunique"))], axis=1).fillna({"vi": 0, "viq": False, "vp": 0, "nf": 0})
    T["tier"] = np.where((T.vi > 0) & ((T.nf >= 2) | T.viq.astype(bool)), 3, np.where((T.vi > 0) | (T.vp > 0), 2, 1))
    T = T.reset_index()[["uid", "service", "tier"]]
    cp = os.path.join(OUT, "claims.csv")
    if os.path.exists(cp):
        old = pd.read_csv(cp)[["uid", "service", "tier"]].merge(T, on=["uid", "service"], how="outer", suffixes=("_csv", ""))
        log(f"tiers recomputed here agree with pipeline/out/claims.csv on {(old.tier_csv == old.tier).mean():.1%} of {len(old)} claims")
    return T


def segments(df):
    """Every sentence of every record, split exactly as claims.py splits them. seg_id is the row number."""
    rows = []
    for u, r in enumerate(df.itertuples()):
        for fld in ["procedure", "equipment", "capability"]:
            seen = set()
            for i, t in enumerate(getattr(r, fld + "_l")):
                t = t.strip(); k = re.sub(r"\W+", " ", t.lower()).strip()
                if not t or k in seen: continue
                seen.add(k)
                for seg in CL.SPLIT.split(t):
                    if seg and len(seg) >= 3: rows.append((u, fld, i, seg))
        for seg in CL.SPLIT.split(r.description):
            if seg and len(seg) >= 3: rows.append((u, "description", 0, seg))
    return pd.DataFrame(rows, columns=["u", "field", "item", "seg"])


# ---------------------------------------------------------------- 1. bundles
def crossfit_logit(X, y, folds, C=1.0):
    """Score every row with a model trained on the other folds (the row's own facility is never in training)."""
    out = np.zeros(X.shape[0])
    for tr, te in folds:
        if y[tr].sum() < 5: continue
        out[te] = LogisticRegression(C=C, max_iter=300, solver="liblinear").fit(X[tr], y[tr]).decision_function(X[te])
    return out


# word stems that the silver labels were built from (facility-name specialty words). fit_text_nospec never sees them.
SPEC = re.compile(r"(eye|netra|nethra|ophthal|vision|retina|lasik|drishti|dental|dentist|tooth|teeth|smile|orthodont|skin|derma|hair|cosmet|aesthet|physio|ayurved|homoeo|homeo|unani|siddha|naturopath|panchakarma|"
                  r"dialysis|kidney|nephro|renal|matern|women|obstet|gynec|gynaec|prasuti|child|pediatric|paediatric|neonat|newborn|nicu|heart|cardiac|cardio|burn|blood)")
WORD_SERVICES = ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab"]


def crossfit_text(X, y, folds, pos=True, C=3.0):
    """Cross-fitted word model. Second output: companions-only score = the same model restricted to words with a positive weight,
    so it can reward the presence of usual companions but can never punish a record for containing another specialty's words."""
    full, comp = np.zeros(X.shape[0]), np.zeros(X.shape[0])
    for tr, te in folds:
        if y[tr].sum() < 5: continue
        m = LogisticRegression(C=C, max_iter=300, solver="liblinear").fit(X[tr], y[tr]); full[te] = m.decision_function(X[te])
        if pos:
            k = np.where(m.coef_[0] > 0)[0]
            m2 = LogisticRegression(C=C, max_iter=300, solver="liblinear").fit(X[tr][:, k], y[tr])
            comp[te] = X[te][:, k] @ np.clip(m2.coef_[0], 0, None) + m2.intercept_[0]
    return full, comp


def bundles(df, Cl, SG, H):
    n = len(df); uidx = {u: i for i, u in enumerate(df.unique_id)}
    T = np.zeros((n, len(SERVICES)), int)                       # evidence tier of every service in every record, 0 = not mentioned
    for u, s, t in zip(Cl.uid, Cl.service, Cl.tier): T[uidx[u], SERVICES.index(s)] = t
    B2 = (T >= 2).astype(float); B1 = (T >= 1).astype(float)
    folds = list(KFold(5, shuffle=True, random_state=0).split(np.arange(n)))
    # which sentences mention which service
    key = pd.Series(np.arange(len(SG)), index=pd.MultiIndex.from_arrays([df.unique_id.values[SG.u.values], SG.field, SG.seg])).groupby(level=[0, 1, 2]).first()
    hs = H.drop_duplicates(["uid", "service", "field", "seg"])
    hs = hs.assign(sid=key.reindex(pd.MultiIndex.from_arrays([hs.uid, hs.field, hs.seg])).values).dropna(subset=["sid"])
    hs["sid"] = hs.sid.astype(int)
    # the same sentence can occur twice in a record (two list items with different punctuation); mark all copies
    same = SG.assign(first=key.reindex(pd.MultiIndex.from_arrays([df.unique_id.values[SG.u.values], SG.field, SG.seg])).values)
    copies = same.groupby("first").indices
    # companion table: PMI between services at medium evidence or better
    p = B2.mean(0); joint = (B2.T @ B2) / n
    with np.errstate(divide="ignore", invalid="ignore"): PMI = np.log(joint / np.outer(p, p))
    np.fill_diagonal(PMI, -np.inf); PMI[(B2.T @ B2) < 20] = -np.inf
    comp = {s: [SERVICES[j] for j in np.argsort(-PMI[i]) if j != i and np.isfinite(PMI[i, j])][:5] for i, s in enumerate(SERVICES)}
    # words: sentences with the record's own name words deleted
    log("building the word table")
    names = [set(w for w in re.findall(r"[a-z]{3,}", str(nm).lower())) for nm in df.name]
    tok = re.compile(r"[a-z][a-z0-9]+")
    docs = [" ".join(w for w in tok.findall(s.lower()) if w not in names[u]) for u, s in zip(SG.u.values, SG.seg.values)]
    cv = CountVectorizer(binary=True, ngram_range=(1, 2), min_df=30, max_features=15000, token_pattern=r"[a-z][a-z0-9]+", stop_words="english")
    Xs = cv.fit_transform(docs).astype(np.float32)
    G = sparse.csr_matrix((np.ones(len(SG), np.float32), (SG.u.values, np.arange(len(SG)))), shape=(n, len(SG)))
    nseg = np.asarray(G.sum(1)).ravel(); vocab = cv.get_feature_names_out()
    NOSPEC = np.array([not any(SPEC.match(w) for w in t.split()) for t in vocab])     # columns left after blanking the label vocabulary
    log(f"vocabulary {len(vocab)} words and word pairs; {int((~NOSPEC).sum())} contain a specialty word used to build the silver labels")
    res = {}
    for j, s in enumerate(SERVICES):
        y = (T[:, j] >= 2).astype(int)
        oth = [k for k in range(len(SERVICES)) if k != j]
        Xf = np.hstack([B1[:, oth], B2[:, oth]])
        sid = hs.sid[hs.service == s].values
        sid = np.unique(np.concatenate([copies.get(k, np.array([k])) for k in sid])) if len(sid) else sid
        keep = np.ones(len(SG), np.float32); keep[sid] = 0
        Gs = sparse.csr_matrix((keep, (SG.u.values, np.arange(len(SG)))), shape=(n, len(SG)))
        Ds = (Gs @ Xs).tocsr(); Ds.data[:] = 1; Ds = normalize(Ds)
        nrest = np.asarray(Gs.sum(1)).ravel()
        Xsize = np.c_[np.log1p(nrest), np.log1p(nrest) ** 2]
        f_flags, f_size = crossfit_logit(Xf, y, folds), crossfit_logit(Xsize, y, folds)
        f_text, f_pos = crossfit_text(Ds, y, folds)
        f_nospec, _ = crossfit_text(Ds[:, NOSPEC], y, folds, pos=False)
        if "--words" in sys.argv and s in WORD_SERVICES:
            m = LogisticRegression(C=3.0, max_iter=300, solver="liblinear").fit(Ds, y); o = np.argsort(m.coef_[0])
            print(f"    words elsewhere in the record that RAISE the expectation of {s}: {', '.join(vocab[o[::-1][:22]])}")
            print(f"    words that LOWER it: {', '.join(vocab[o[:22]])}")
        ci = [SERVICES.index(c) for c in comp[s]]
        pm = np.where(np.isfinite(PMI[j]), PMI[j], 0.0)
        res[s] = pd.DataFrame({"u": np.arange(n), "service": s, "fit_flags": f_flags, "fit_text": f_text, "fit_text_nospec": f_nospec, "fit_text_pos": f_pos,
                               "fit_flags_resid": f_flags - f_size, "fit_text_resid": f_text - f_size,
                               "comp_share": B2[:, ci].mean(1) if ci else np.zeros(n), "lonely": (B2[:, oth].sum(1) == 0).astype(int),
                               "pmi_mean": (B2[:, oth] * pm[oth]).sum(1) / np.maximum(B2[:, oth].sum(1), 1),
                               "n_other_t2": B2[:, oth].sum(1), "n_rest_sent": nrest})
        log(f"  {s:20s} base rate {y.mean():.3f} | companions: {', '.join(comp[s])}")
    R = pd.concat(res.values(), ignore_index=True)
    R["claims_most"] = (B1.sum(1) >= 12).astype(int)[R.u.values]
    R["n_services"] = B1.sum(1)[R.u.values]
    R["n_acute_t2"] = B2[:, [SERVICES.index(a) for a in ACUTE]].sum(1)[R.u.values]
    return R, hs, nseg


# ---------------------------------------------------------------- 2. contradictions inside one record
UNITW = r"ICU|NICU|PICU|SNCU|CCU|ICCU|HDU|SICU|MICU|RICU|intensive|critical|coronary|dialysis|emergency|casualty|accident|trauma|burns?|wards?|units?|isolation|covid|neonat\w*|nursery|day ?care|recovery|labou?r|maternity|pa?ediatric\w*|cardiac|oncolog\w*|chemo\w*|psychiat\w*|de-?addiction|ventilator\w*|observation|triage|private|deluxe|semi|block|wing|annex\w*|expansion|additional|extra|more|new|hostel|rooms?|suites?|theat\w+|OT|department|cent(?:re|er)|clinic|floor|each|per"
TOTALW = r"hospital|facility|capacity|multi\w*|super\w*|nursing home|institut\w+|healthcare|medical college|tertiary|charitable|in-?patients?"
BED = re.compile(r"(?<![\d.,/-])(\d{1,2},\d{3}|\d{1,4})\+?\s*[- ]?\s*bed(?:ded|s)?\b", I)
UNIT_RX, TOTAL_RX = re.compile(r"\b(?:" + UNITW + r")\b", I), re.compile(r"\b(?:" + TOTALW + r")\b", I)
UNIT_BEFORE = re.compile(r"\b(?:" + UNITW + r")\b[^.;|]{0,25}$", I)
# a bed count that is history, a plan, or about a hospital group is not a statement about this facility today
NOT_NOW = re.compile(r"\b(?:originally|initially|start(?:ed|ing|s)?|began|commenced|humble|grew|grown|launched as|from \d+|expanded from|earlier|formerly|previously|then|planned|proposed|will|upcoming|to be|expand(?:ed|ing)? to|upgrad\w+ to|"
                     r"approved|sanctioned|add|chain|group|network|across|hospitals|branches|centres|centers|in (?:1[89]|20)\d\d)\b", I)


def bed_is_unit(pre, post):
    p = post[:34]; mu, mt = UNIT_RX.search(p), TOTAL_RX.search(p)
    if mu and (not mt or mu.start() < mt.start()): return True
    return bool(UNIT_BEFORE.search(pre)) and not TOTAL_RX.search(pre[-25:])


DOCS = re.compile(r"(?<![\d.,/-])(\d{1,2},\d{3}|\d{1,4})\+?\s*(?:qualified |experienced |full[- ]time |resident |specialist |expert )?doctors?\b(?!\.in| and nurses|[- ]to[- ]| on call)", I)
YEAR = re.compile(r"\b(?:establish(?:ed|ment)|founded|estd\.?|inception|incorporated)\b[^.;|]{0,20}?\b(1[6-9]\d\d|20[0-2]\d)\b", I)
SUBUNIT = re.compile(r"\b(?:department|dept|program(?:me)?|clinic|unit|cent(?:re|er)|wing|block|bank|lab(?:oratory)?|course|college|school|division|section|ward|branch|trust|society|group|company|chain|foundation|institute of|services?)\b", I)
BAD_FLAG = re.compile(r"neg|meta|referral|future")


# how the record describes ITSELF in its own sentences ("Eye care hospital", "Is a government hospital", "Multi-speciality hospital")
_K = r"(?:care |super ?special(?:i?ty)? |special(?:i?ty) |charitable |tertiary )?(?:hospital|clinic|cent(?:re|er)|institute|nursing home)\b"
IDENT_SINGLE = {k: re.compile(r"\b(?:" + v + r")\w*,? (?:and \w+ )?" + _K, I) for k, v in {
    "eye": "eye|ophthalm", "dental": "dental|dentist", "skin": "skin|dermatolog|cosmet|hair", "alt": "ayurved|homoeo|homeo|unani|siddha|naturopath|panchakarma",
    "physio": "physio", "kidney": "kidney|dialysis|nephrolog|urolog", "heart": "heart|cardiac|cardiolog", "mother_child": "maternity|women'?s?|gyna?ecolog|children'?s?|pa?ediatric|neonatal|mother and child",
    "cancer": "cancer|oncolog", "ortho": "ortho\\w*|bone|spine|joint", "ent": "ENT|ear,? nose", "psych": "psychiatr|mental health|de-?addiction", "fertility": "IVF|fertility|infertility",
    "diagnostic": "diagnostic|imaging|patholog|scan"}.items()}
KIND = re.compile(r"hospital|clinic|cent(?:re|er)|institute|nursing home|medical college", I)
IDENT_GENERAL = re.compile(r"\b(?:multi[- ]?(?:super[- ]?)?special\w*|general|government|govt\.?|district|civil|sub[- ]?district|municipal|teaching|tertiary care|medical college(?: and)?) (?:\w+ ){0,2}hospital\b|\bmedical college\b", I)


def contradictions(df, SG):
    seg_by_u = SG.groupby("u").seg.apply(list).to_dict()
    rows = []
    for u, r in enumerate(df.itertuples()):
        totals, units, docs, years = set(), set(), set(), set()
        for seg in seg_by_u.get(u, []):
            for m in BED.finditer(seg):
                v = int(m.group(1).replace(",", ""))
                if v < 2 or v > 5000: continue
                pre, post = seg[max(0, m.start() - 45):m.start()], seg[m.end():m.end() + 45]
                if NOT_NOW.search(pre) or NOT_NOW.search(post[:25]): continue
                (units if bed_is_unit(pre, post) else totals).add(v)
            for m in DOCS.finditer(seg):
                v = int(m.group(1).replace(",", ""))
                if 1 <= v <= 5000 and not NOT_NOW.search(seg[max(0, m.start() - 45):m.start()]): docs.add(v)
            for m in YEAR.finditer(seg):
                if not SUBUNIT.search(seg[max(0, m.start() - 60):m.start()]): years.add(int(m.group(1)))
        cap, nd, yr = r.capacity_n, r.numberDoctors_n, r.yearEstablished_n
        tot = set(totals) | ({float(cap)} if cap == cap and 2 <= cap <= 5000 else set())
        dd = set(docs) | ({float(nd)} if nd == nd and 1 <= nd <= 5000 else set())
        yy = set(years) | ({float(yr)} if yr == yr and 1600 <= yr <= 2025 else set())
        beds = min(tot) if tot else np.nan
        bed_ratio = max(tot) / min(tot) if len(tot) >= 2 else 1.0
        nm = r.name.strip() if isinstance(r.name, str) else ""          # the record's own name is blanked first; what is left is the text's own description
        own = re.compile(re.escape(nm), I) if len(nm) >= 4 else None
        short = [own.sub(" ", seg) if own else seg for seg in seg_by_u.get(u, []) if len(seg) <= 160 and KIND.search(seg)]
        single = {k for k, rx in IDENT_SINGLE.items() if any(rx.search(seg) for seg in short)}
        general = any(IDENT_GENERAL.search(seg) for seg in short)
        rows.append(dict(u=u, ident_conflict=int(bool(single) and general) + int(len(single) >= 2), ident_single=len(single),
                         bed_conflict=int(bed_ratio >= 1.5 and max(tot) - min(tot) >= 10), bed_spread=np.log(bed_ratio),
                         unit_gt_total=int(bool(units) and bool(tot) and max(units) > min(tot)),
                         doc_conflict=int(len(dd) >= 2 and max(dd) / min(dd) >= 3 and max(dd) - min(dd) >= 5),
                         docs_vs_beds=int(bool(tot) and bool(dd) and max(tot) >= 50 and min(dd) <= 2),
                         year_conflict=int(len(yy) >= 2 and max(yy) - min(yy) >= 10),
                         year_bad=int(yr == yr and (yr > 2025 or yr < 1700)),
                         beds_stated=beds, docs_stated=(min(dd) if dd else np.nan), n_bed_statements=len(tot)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 3. stricter co-requirement checklists
def coreq_variants(df, Cl, SG, H, hs):
    uidx = {u: i for i, u in enumerate(df.unique_id)}
    sg_u, sg_field, sg_item, sg_seg = SG.u.to_numpy(), SG.field.to_numpy(dtype=object), SG["item"].to_numpy(), SG.seg.to_numpy(dtype=object)
    start = np.searchsorted(sg_u, np.arange(len(df)), "left"); end = np.searchsorted(sg_u, np.arange(len(df)), "right")     # SG is ordered by record
    joined = [" || ".join(sg_seg[a:b]) for a, b in zip(start, end)]
    infra_sid = set(hs.sid[hs.cls == "infra"].to_numpy())
    hit_sid = {}
    for uid, sv, sid in zip(hs.uid.to_numpy(dtype=object), hs.service.to_numpy(dtype=object), hs.sid.to_numpy()): hit_sid.setdefault((uid, sv), set()).add(int(sid))
    names = df.name.to_numpy(dtype=object)
    cache = {}
    def found(u, own, name, rx):
        """Every sentence of record u that matches the co-requirement: (seg_id, field, item, has no caution flag)."""
        k = (u, rx.pattern)                      # the same pattern (ICU, blood bank, 24x7 ...) is a co-requirement of several services
        if k not in cache:
            out = []
            if rx.search(joined[u]):
                for sid in range(start[u], end[u]):
                    m = rx.search(sg_seg[sid])
                    if m: out.append((sid, sg_field[sid], sg_item[sid], not CL.flags_for(sg_seg[sid], m.start(), m.end(), own)))
            cache[k] = out
        return cache[k]
    rows = []
    for uid, s in zip(Cl.uid.to_numpy(dtype=object), Cl.service.to_numpy(dtype=object)):
        u = uidx[uid]; nm = names[u].strip()
        own = re.compile(re.escape(nm), I) if len(nm) >= 4 else None
        mine = hit_sid.get((uid, s), set()); pos = [(sg_field[k], sg_item[k]) for k in mine]
        c = dict(any=0, indep=0, clean=0, infra=0, near=0, strict=0)
        for name, rx in CL.CQ[s].items():
            f = found(u, own, s + "/" + name, rx)
            if not f: continue
            c["any"] += 1
            ind = [x for x in f if x[0] not in mine]
            c["indep"] += bool(ind)
            c["clean"] += any(x[3] for x in f)
            inf = lambda x: x[1] == "equipment" or x[0] in infra_sid
            c["infra"] += any(inf(x) for x in f)
            c["near"] += any(x[1] == pf and abs(x[2] - pi) <= 5 for x in ind for pf, pi in pos)
            c["strict"] += any(x[3] and inf(x) for x in ind)
        tot = len(CL.CQ[s])
        rows.append((uid, s, c["any"] / tot, c["indep"] / tot, c["clean"] / tot, c["infra"] / tot, c["near"] / tot, c["strict"] / tot, c["indep"]))
    return pd.DataFrame(rows, columns=["uid", "service", "coreq_seg", "coreq_indep", "coreq_clean", "coreq_infra", "coreq_near", "coreq_strict", "coreq_indep_n"])


# ---------------------------------------------------------------- assemble
KEEP = ["comp_share", "lonely", "pmi_mean", "fit_flags", "fit_text", "fit_text_nospec", "fit_text_pos", "fit_text_pos_min5", "n_other_t2", "claims_most",
        "bed_conflict", "doc_conflict", "docs_vs_beds", "year_conflict", "two_facts", "ident_conflict", "unit_gt_total", "acute_vs_size", "neg_pos",
        "coreq_indep", "coreq_clean", "coreq_infra", "coreq_near", "coreq_strict"]
DIAG = ["fit_flags_resid", "fit_text_resid", "n_contra", "year_bad", "coreq_zero_indep", "ident_single"]      # printed by --check, not written


def main():
    df = load_facilities(); H = get_hits(df); Cl = tiers(H)
    log("facilities", len(df), "| claims", len(Cl))
    SG = segments(df); log("sentences", len(SG))
    R, hs, nseg = bundles(df, Cl, SG, H)
    R["uid"] = df.unique_id.values[R.u.values]
    K = contradictions(df, SG); log("contradictions done")
    Q = coreq_variants(df, Cl, SG, H, hs); log("co-requirement variants done")
    O = Cl[["uid", "service", "tier"]].merge(R, on=["uid", "service"], how="left").merge(K, on="u", how="left").merge(Q, on=["uid", "service"], how="left")
    # high-acuity services against stated size: 4+ at a place stating 15 beds or fewer, or (no bed count) 2 doctors or fewer
    tiny = (O.beds_stated <= 15) | (O.beds_stated.isna() & (O.docs_stated <= 2))
    O["acute_vs_size"] = ((O.n_acute_t2 >= 4) & tiny).astype(int)
    hb = H.assign(bad=H["flags"].str.contains(BAD_FLAG), ok=H["flags"].eq("")).groupby(["uid", "service"]).agg(bad=("bad", "any"), ok=("ok", "any")).reset_index()
    O = O.merge(hb, on=["uid", "service"], how="left"); O["neg_pos"] = (O.bad & O.ok).astype(int)
    O["two_facts"] = O[["bed_conflict", "doc_conflict", "docs_vs_beds", "year_conflict"]].sum(axis=1)      # same basic question, two answers
    O["n_contra"] = O[["bed_conflict", "unit_gt_total", "doc_conflict", "docs_vs_beds", "year_conflict", "year_bad", "acute_vs_size", "neg_pos"]].sum(axis=1)
    O["coreq_zero_indep"] = (O.coreq_indep_n == 0).astype(int)
    # a record with almost no other text cannot show companions; do not let that count against it (stand-alone dialysis centres)
    enough = O.n_rest_sent >= 5
    O["fit_text_pos_min5"] = O.fit_text_pos.where(enough, O.service.map(O[enough].groupby("service").fit_text_pos.median()))
    out = os.path.join(OUT, "feat_bundles_claim.csv")
    O[["uid", "service"] + KEEP].round(4).to_csv(out, index=False)
    log("wrote", out, f"{len(O)} rows, {len(KEEP)} feature columns")
    print("\nshare of all claims / facilities with each warning:")
    for c in ["lonely", "claims_most", "bed_conflict", "doc_conflict", "docs_vs_beds", "year_conflict", "two_facts", "ident_conflict", "unit_gt_total", "year_bad", "acute_vs_size", "neg_pos", "coreq_zero_indep"]:
        f = O[c] > 0
        print(f"  {c:17s} claims {f.mean():6.1%}   facilities {f.groupby(O.uid).max().mean():6.1%}")
    O.to_pickle(os.path.join(os.environ.get("FEAT_BUNDLES_DEBUG", ""), "feat_bundles_debug.pkl")) if os.environ.get("FEAT_BUNDLES_DEBUG") else None
    if "--check" in sys.argv: check(O)


def check(O):
    """Diagnostics only (needs the silver labels and warning signs from trust.py). Nothing here feeds the CSV."""
    import trust
    from sklearn.model_selection import GroupKFold
    from sklearn.metrics import roc_auc_score
    extra = ["n_rest_sent", "n_services"] + KEEP + DIAG
    C = trust.features().merge(O[["uid", "service"] + extra], on=["uid", "service"], how="left", suffixes=("", "_f"))
    S = C[C.y.notna()].reset_index(drop=True); hosp = (S.facilityTypeId == "hospital").values
    S["len1"] = np.log1p(S.n_rest_sent); S["len2"] = np.log1p(S.n_services)
    def oof(cols):
        X, y, g = S[cols].fillna(0).values, S.y.values, S.uid.values; o = np.zeros(len(S))
        for tr, te in GroupKFold(5).split(X, y, g): o[te] = LogisticRegression(max_iter=2000).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
        return o
    auc = lambda o, m=None: roc_auc_score(S.y, o) if m is None else roc_auc_score(S.y[m], o[m])
    cv = lambda cols, m=None: auc(oof(cols), m)
    base = trust.FEATS; sized = base + ["len1", "len2"]
    # 1. record length is a confound, and it points the other way from the "small clinic" trap
    print(f"\n[1] record length | median number of other sentences: likely real {S.n_rest_sent[S.y == 1].median():.0f}, likely false {S.n_rest_sent[S.y == 0].median():.0f}"
          f" | hospitals {S.n_rest_sent[hosp & (S.y == 1)].median():.0f} vs {S.n_rest_sent[hosp & (S.y == 0)].median():.0f}")
    print("    own AUC of record length alone:", round(roc_auc_score(S.y, S.len1), 3), "hospitals", round(roc_auc_score(S.y[hosp], S.len1[hosp]), 3),
          "| number of services alone:", round(roc_auc_score(S.y, S.len2), 3), "hospitals", round(roc_auc_score(S.y[hosp], S.len2[hosp]), 3))
    print(f"    formula {cv(base):.3f} (hospitals {cv(base, hosp):.3f}) | formula + record length {cv(base + ['len1']):.3f} ({cv(base + ['len1'], hosp):.3f})"
          f" | formula + record length + number of services {cv(sized):.3f} ({cv(sized, hosp):.3f})")
    for combo in (["fit_text"], ["fit_text", "n_other_t2"], ["fit_text", "len1"], ["fit_text_pos_min5"], ["fit_text_pos_min5", "len1"], ["fit_text_pos_min5", "two_facts"]):
        print(f"    formula + {' + '.join(combo):32s} {cv(base + combo):.3f} (hospitals {cv(base + combo, hosp):.3f})")
    # 2. every feature: group means and the gain that is left once record length is already in the model
    b, bh = cv(sized), cv(sized, hosp); rows = []
    for c in KEEP + DIAG:
        if S[c].nunique() < 2: continue
        rows.append((c, round(S[c][S.y == 1].mean(), 3), round(S[c][S.y == 0].mean(), 3), round(S[c][hosp & (S.y == 1)].mean(), 3), round(S[c][hosp & (S.y == 0)].mean(), 3),
                     round(cv(sized + [c]) - b, 3), round(cv(sized + [c], hosp) - bh, 3)))
    print("\n[2] gain over formula + record length + number of services")
    print(pd.DataFrame(rows, columns=["feature", "mean_real", "mean_false", "mean_real_hosp", "mean_false_hosp", "gain_over_formula+size", "same_hospitals_only"]).to_string(index=False))
    # 3. uncertainty: resample facilities
    rng = np.random.default_rng(0); ug = S.uid.unique(); idx_by = {u: np.where(S.uid.values == u)[0] for u in ug}
    samples = [np.concatenate([idx_by[u] for u in rng.choice(ug, len(ug))]) for _ in range(400)]
    P0 = oof(base); print("\n[3] 90% range of the AUC gain over the formula (facilities resampled 400 times) and of the multiplier on the odds")
    for c in ["fit_text", "fit_text_nospec", "fit_text_pos", "fit_text_pos_min5", "pmi_mean", "two_facts", "n_other_t2", "coreq_near"]:
        P1 = oof(base + [c]); d, dh, mult = [], [], []
        for ii in samples:
            y = S.y.values[ii]; d.append(roc_auc_score(y, P1[ii]) - roc_auc_score(y, P0[ii]))
            jj = ii[hosp[ii]]; dh.append(roc_auc_score(S.y.values[jj], P1[jj]) - roc_auc_score(S.y.values[jj], P0[jj]))
        for ii in samples[:200]: mult.append(np.exp(LogisticRegression(max_iter=2000).fit(S[base + [c]].values[ii], S.y.values[ii]).coef_[0][-1]))
        pt = np.exp(LogisticRegression(max_iter=2000).fit(S[base + [c]].values, S.y.values).coef_[0][-1])
        print(f"    {c:18s} gain {auc(P1) - auc(P0):+.3f} ({np.percentile(d, 5):+.3f} to {np.percentile(d, 95):+.3f}) | hospitals {auc(P1, hosp) - auc(P0, hosp):+.3f} ({np.percentile(dh, 5):+.3f} to {np.percentile(dh, 95):+.3f})"
              f" | multiplier per unit x{pt:.2f} ({np.percentile(mult, 5):.2f} to {np.percentile(mult, 95):.2f})")
    # 4. per service
    print("\n[4] own AUC inside each service (likely real / likely false counts)")
    for sv in ["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "cath_lab"]:
        m = (S.service == sv).values
        print(f"    {sv:20s} {int(S.y[m].sum()):3d}/{int((S.y[m] == 0).sum()):3d} ", {c: round(roc_auc_score(S.y[m], S[c][m]), 3) for c in ["fit_text", "fit_text_nospec", "fit_text_pos_min5", "pmi_mean", "coreq", "coreq_near", "len1"]})
    # 5. contradictions against evidence that does not come from the 744 labels
    R = C.drop_duplicates("uid").copy(); tf = (R.two_facts >= 1); R["nsign"] = R[list(trust.SIGNS)].sum(axis=1)
    print(f"\n[5] contradictions | facilities with a claim {len(R)} | with 1+ contradiction {int(tf.sum())} | with 2+ {int((R.two_facts >= 2).sum())}")
    for c in trust.SIGNS: print(f"    existing sign {c:10s}: present in {R[c][tf].mean():.1%} of records with a contradiction vs {R[c][~tf].mean():.1%} without (lift {(tf & (R[c] == 1)).mean() / (tf.mean() * R[c].mean()):.2f})")
    print("    share of records with 2+ existing signs, by number of contradictions 0 / 1 / 2+:", R.groupby(R.two_facts.clip(upper=2)).nsign.apply(lambda x: round((x >= 2).mean(), 3)).to_dict())
    q = pd.qcut(R.n_rest_sent, 4, labels=False, duplicates="drop")
    print("    same inside record-length quarters (short to long), with vs without a contradiction:", {int(k): (round((g.nsign[g.two_facts >= 1] >= 2).mean(), 3), round((g.nsign[g.two_facts == 0] >= 2).mean(), 3), int((g.two_facts >= 1).sum())) for k, g in R.groupby(q)})
    N = C[C.neg != ""]; nf = N.drop_duplicates("uid").set_index("uid")
    imp = nf.index.isin(N[N.service.isin(["dialysis", "emergency_obstetric", "nicu", "cardiac_surgery", "burn_care"]) & (N.tier >= 2)].uid.unique()); g = (nf.two_facts >= 1).values
    print(f"    name-based single-specialty facilities: impossible acute claim (medium+) in {imp[g].sum()} of {g.sum()} with a contradiction ({imp[g].mean():.1%}) vs {imp[~g].sum()} of {(~g).sum()} without ({imp[~g].mean():.1%})")
    print("    silver claims with a contradiction, by facility type:", S.groupby([S.facilityTypeId.where(S.facilityTypeId.isin(["hospital", "clinic"]), "other"), "y"]).two_facts.agg(lambda x: f"{int((x >= 1).sum())}/{len(x)}").to_dict())
    for c in ["bed_conflict", "doc_conflict", "docs_vs_beds", "year_conflict", "two_facts", "ident_conflict", "claims_most", "lonely", "unit_gt_total", "acute_vs_size", "neg_pos"]:
        f = (S[c] > 0).values
        print(f"    {c:15s} hospitals: {f[hosp & (S.y == 0)].mean():.1%} of likely-false vs {f[hosp & (S.y == 1)].mean():.1%} of likely-real claims | all: {f[S.y == 0].mean():.1%} vs {f[S.y == 1].mean():.1%} | {S.uid[f].nunique()} silver facilities")
    # 6. known records
    show = {"b8a5401f-42f1-422a-8cd9-686a15b4cb76": "known bad", "38cbdd06-e01b-4c41-b02f-c46e693c822c": "good, kidney hospital", "c3017603-060e-4e86-a526-c648b44d9293": "good, general hospital"}
    D = C[C.service == "dialysis"]; K = D[D.uid.isin(show)].set_index("uid").loc[list(show)]
    cols = ["tier", "coreq"] + list(trust.SIGNS) + ["n_rest_sent", "n_services"] + KEEP
    print(f"\n[6] dialysis claim of three records (percentile among all {len(D)} dialysis claims in brackets for the fit scores)")
    T = K[cols].T; T.columns = [f"{K.name[u][:28]} ({show[u]})" for u in K.index]; print(T.round(2).to_string())
    for c in ["fit_text", "fit_text_pos_min5", "pmi_mean", "n_services"]: print(f"    percentile {c:18s}", [round(float((D[c] < v).mean() * 100)) for v in K[c]])
    for combo in ([], ["two_facts"], ["fit_text_pos_min5"], ["fit_text_pos_min5", "two_facts"], ["fit_text", "two_facts"]):
        m = LogisticRegression(max_iter=2000).fit(S[base + combo].fillna(0).values, S.y)
        sc = 100 / (1 + np.exp(-(m.intercept_[0] + D[base + combo].fillna(0).values @ m.coef_[0]))); me = pd.Series(sc, index=D.uid.values)
        print(f"    trust with formula + {str(combo):38s}", [round(float(me[u]), 1) for u in show], f"| the known bad claim outranks {(sc < me[list(show)[0]]).mean():.0%} of dialysis claims")
    dn = D[D.name.str.contains("dialysis", case=False)]
    print(f"    {len(dn)} dialysis claims at facilities with 'dialysis' in the name: median other sentences {dn.n_rest_sent.median():.0f} (all dialysis claims {D.n_rest_sent.median():.0f}),"
          f" median fit_text_pos {dn.fit_text_pos.median():.2f} vs {D.fit_text_pos.median():.2f}, after the fewer-than-5 rule {dn.fit_text_pos_min5.median():.2f}")


if __name__ == "__main__":
    main()
