"""Candidate features: how specific and how repeated is the evidence behind each (facility, service) claim?

Reads   facilities.csv (via common.load_facilities) and pipeline/out/hits.pkl (rebuilt with claims.build_hits if missing)
Writes  pipeline/out/feat_specificity_claim.csv   key uid + service
        pipeline/out/feat_specificity_row.csv     key uid
Run     python -I pipeline/feat_specificity.py            (about 100 seconds)
        python -I pipeline/feat_specificity.py --check 96127a43:dialysis dc48f461:dialysis
            --check adds: name-echo counts, the size-controlled test, the specialist-proxy test and named example records
            (uid prefix:service). Only --check reads the silver labels (trust.features); building the CSVs does not.

Leakage guard. The silver labels come from the facility NAME, so the name is used here for one thing only:
to recognise a sentence that merely repeats the record's own name ("Operates within Sham Nursing Home & Heart Centre").
Such a sentence matches "heart centre" because of the name, not because of a fact. Those "name echo" hits are dropped
before anything is counted. facilityTypeId and the specialties column are never read.

Terms
  sentence        one list item (procedure / equipment / capability) or one sentence of the description
  template        a sentence whose normalised wording (own name masked, digits -> #, leading "Provides/Offers/Has" removed)
                  appears in TEMPLATE_DF or more different facilities ("Provides MRI services")
  detail kinds    count, maker/model, place in the building, staff, timing, money/programme, volume/history (0 to 7)
  off-topic       the matched phrase is about teeth, eyes, skin, alternative medicine or physiotherapy
                  ("Dental chair with attached delivery unit" is not a delivery room)
  other hospital  a hospital name in a sentence that shares no identifying word with the record's own name

What the tests show (see --check): n_support, text_share, first_relpos, desc_mentions and has_staff separate the silver groups
well, but ordinary general-hospital claims look like the likely-false group on all of them. They detect "this facility is a
specialist in the service", which is how the likely-real group was chosen. Record size (n_sentences) works in the opposite
direction to the expected trap: long records are more often likely-false, because a long record gives the keyword search more
chances to fire. Do not use either group as a weight. all_offtopic and row_other_org_3plus do not have this problem.
"""
import sys, os, re
from difflib import SequenceMatcher
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load_facilities, OUT
import claims as CL                      # SPLIT, C (compiled service regexes), CX (caution regexes), QTY, build_hits

I = re.I
TEMPLATE_DF = 5                          # a wording seen at 5+ facilities is called a template
CAP = 50                                 # the upstream extractor stops every list at 50 items
FIELDS = ["procedure", "equipment", "capability"]
TOK = re.compile(r"[A-Za-z0-9]+(?:'[a-z]+)?")
LEAD = re.compile(r"^(?:(?:the|this|our) (?:hospital|clinic|cent(?:re|er)|facility|institute) )?(?:also )?(?:provides?|offers?|performs?|has|have|having|conducts?|includes?|features?|equipped with|"
                  r"availability of|specializ\w+ in|speciali[sz]\w+ in|facility for|facilities for|treatment (?:for|of)|services? (?:for|of|include))\s+(?:an? |the )?", I)
TAIL = re.compile(r"\s+(?:services?|facilit(?:y|ies)|available|is available|are available|treatments?|procedures?)$", I)

# ---- detail kinds (each is a plain, checkable property of one sentence) -------------------------------------------
D_COUNT = CL.QTY                                                                            # "10 machines", "20-bed", "1.5 T", "level II"
D_MAKER = re.compile(r"\b(?:siemens|philips|ge healthcare|wipro ge|fresenius|nipro|b\.? ?braun|baxter|gambro|nikkiso|toshiba|canon|hitachi|dr[aä]ger|medtronic|maquet|getinge|hamilton|mindray|"
                     r"samsung|carestream|fujifilm|agfa|allengers|\bbpl\b|stryker|zeiss|alcon|olympus|karl storz|storz|varian|elekta|da vinci|abbott|boston scientific|st\.? jude|"
                     r"puritan bennett|somatom|magnetom|ingenia|signa|aquilion|artis|allura|azurion|innova|phoenix|schiller|skanray|trivitron|sorin|terumo|edwards|drager)\b"
                     r"|(?-i:\bGE\b)|(?-i:\b[A-Z][A-Za-z]{2,}[- ](?:[A-Z]?\d{2,5}[A-Z]{0,2}|[A-Z]\d+|X\b|Pro\b|Plus\b))", I)
D_PLACE = re.compile(r"\b(?:\d{1,2}(?:st|nd|rd|th)|ground|first|second|third|fourth|fifth|basement) floor\b|\b(?:in|at|on) the [\w ]{0,25}(?:block|wing|building|complex|floor|annex)\b|"
                     r"\b(?:block|wing|tower)[- ][A-Z0-9]\b|\bOT complex\b|\bcasualty room\b|\badjacent to\b|\bnext to the\b", I)
D_STAFF = re.compile(r"\bDr\.?\s+[A-Z]|\b(?:nephrologists?|neonatologists?|cardiologists?|cardiac surgeons?|cardio[- ]?thoracic surgeons?|obstetricians?|gyna?ecologists?|pa?ediatricians?|intensivists?|"
                     r"ana?esthe(?:tists?|siologists?)|radiologists?|plastic surgeons?|neurosurgeons?|oncologists?|perfusionists?|technicians?|technologists?|staff nurses?|trained nurses?|"
                     r"dialysis (?:technicians?|nurses?)|headed by|led by|team of|staffed by|under the (?:care|supervision|guidance) of)\b", I)
D_TIME = re.compile(r"24\s?[x/*×]\s?7|24[- ]?h(?:ou)?rs?|round[- ]the[- ]clock|around the clock|day and night|\b\d{1,2}(?:[:.]\d\d)?\s?(?:am|pm)\b|\b(?:daily|every day|on all days|"
                    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day)\b|\bshifts?\b|\bon call\b|\bemergency basis\b", I)
D_MONEY = re.compile(r"₹|\bRs\.?\s?\d|\bINR\b|\brupees\b|\bpackages?\b|\bfree of (?:cost|charge)\b|\bfree\b|\bcashless\b|\bsubsidi[sz]ed\b|\bcharges?\b|\bPM-?JAY\b|\bAyushman\b|\bArogya ?sri\b|\bCGHS\b|"
                     r"\bECHS\b|\bESIC?\b|\bempanel|\binsurance\b|\bschemes?\b|\bprogramme\b|\bprogram\b|\byojana\b|\bPMNDP\b|\bPPP\b|\bNABH\b|\bJCI\b|\baccredit", I)
D_VOLUME = re.compile(r"\b\d[\d,]*\+?\s*(?:patients|cases|deliveries|surgeries|procedures|sessions|births|babies|transplants|operations)\b|\bper (?:year|month|day|annum)\b|\bannually\b|"
                      r"\b(?:since|in|established in|started in|commissioned in|inaugurated in) (?:19|20)\d\d\b|\bsuccess rate\b|\bmore than \d|\bover \d[\d,]+\b|\bfirst (?:in|of its kind)\b", I)
DETAILS = {"count": D_COUNT, "maker": D_MAKER, "place": D_PLACE, "staff": D_STAFF, "timing": D_TIME, "money": D_MONEY, "volume": D_VOLUME}

# the sentence itself is about another kind of care (word-sense slips of the keyword search):
# "Dental chair with attached delivery unit", "Ophthalmic angiography", "Ayurvedic postpartum care", "phototherapy" at a skin clinic
OFF = {"teeth": r"\bdental|\bdentist|\btooth|\bteeth|\borthodont|\bpedodont|\boral\b|\bmaxillo",
       "eyes": r"\bophthalm|\bretina|\bcornea|\bfundus|\bfluorescein|\beyes?\b|\bocular|\bRetCam\b",
       "skin": r"\bderma|\bskin\b|\bhair\b|\bcosmet|\bpsoriasis|\bvitiligo",
       "alt_medicine": r"\bayurved|\bpanch\w*karma|\bhomo?eo|\bunani\b|\bsiddha\b|\bnaturopath",
       "physio_vet": r"\bphysio|\bveterinar"}
OFF_EXEMPT = {"cataract_surgery": {"eyes"}, "burn_care": {"skin"}}          # eye words are on-topic for cataract, skin words for burns
OFFRX = {s: re.compile("|".join(v for k, v in OFF.items() if k not in OFF_EXEMPT.get(s, ())), I) for s in CL.ONT}
OFFCUT = re.compile(r",|;|/|&|\band\b|\bor\b|\bincluding\b", I)
ORG = re.compile(r"\b((?:[A-Z][\w.'-]*,? (?:& )?){1,5}?(?:Hospitals?|Medical College|Nursing Home|Medical Mission|Kendra|Netralaya|Nethralaya|Trauma Cent(?:re|er)))\b")
ORG_STOP = set("the this our provides offers has is a an at in of for and with by to from under as on listed located part unit department dept india indian government govt district civil general multi super "
               "speciality specialty private public charitable best top leading near nearby also it its hospital hospitals clinic medical college nursing home institute centre center kendra foundation "
               "mission trauma community primary health national state city new".split())


def name_tools(F):
    """Words that are common in facility names (hospital, eye, care ...) carry no identity; the rest do."""
    toks = F.name.map(lambda n: set(t.lower() for t in TOK.findall(n)))
    df = pd.Series([t for s in toks for t in s]).value_counts()
    common = set(df[df >= 30].index) | ORG_STOP
    return toks, common


def ordinary_words(segs):
    """Words that are written in lower case 20+ times in the table are ordinary words (liver, pain, network), not proper names."""
    c = pd.Series([w for s in segs for w in re.findall(r"(?<![A-Za-z])[a-z]{3,}(?![A-Za-z])", s)]).value_counts()
    return set(c[c >= 20].index)


def mask_own(seg, name, name_toks, common):
    """Blank out the record's own name inside a sentence: the exact name, and any run of 2+ consecutive name words
    that contains at least one identifying word. Returns the masked sentence (same length)."""
    out = seg
    if len(name) >= 4:
        out = re.sub(re.escape(name), lambda m: " " * len(m.group(0)), out, flags=I)
    nw = [t.lower() for t in TOK.findall(name)][:12]
    if len(nw) < 2: return out
    bi = set(zip(nw, nw[1:]))
    ms = list(TOK.finditer(out)); lw = [m.group(0).lower() for m in ms]
    hit = [False] * len(ms)
    for i in range(len(ms) - 1):
        if (lw[i], lw[i + 1]) in bi: hit[i] = hit[i + 1] = True
    i = 0; chars = list(out)
    while i < len(ms):
        if hit[i]:
            j = i
            while j + 1 < len(ms) and hit[j + 1]: j += 1
            if any(lw[k] not in common for k in range(i, j + 1)):
                for p in range(ms[i].start(), ms[j].end()): chars[p] = " "
            i = j + 1
        else: i += 1
    return "".join(chars)


def norm_key(masked):
    s = re.sub(r"\s+", " ", masked).strip()
    s = TAIL.sub("", LEAD.sub("", s))
    s = re.sub(r"\d+", "#", s.lower())
    return re.sub(r"[^a-z#]+", " ", s).strip()


def match_service(masked, s):
    """Same matching order as claims.py, on the name-masked sentence. Returns (cls, match) or None."""
    c = CL.C[s]
    m2 = c["exclude"].sub(lambda m: " " * len(m.group(0)), masked) if c["exclude"] else masked
    for cls in ("infra", "proc", "generic"):
        if c[cls] is None: continue
        m = c[cls].search(m2)
        if m: return cls, m
    return None


def same_word(w, name_toks):
    """Own-name test that tolerates spelling variants (Geeta / Geetha, Fernandes / Fernandez, Indo Spine / Indospine)."""
    for t in name_toks:
        if w == t or (min(len(w), len(t)) >= 4 and (w.startswith(t) or t.startswith(w))): return True
        if len(w) >= 5 and len(t) >= 5 and SequenceMatcher(None, w, t).ratio() >= 0.8: return True
    return False


def other_orgs(masked, name_toks, common, subject_only=False):
    """Hospital names in a sentence that share no identifying word with the record's own name.
    subject_only=False: anywhere in the sentence, directory sentences ("listed among top hospitals in ...") skipped.
    subject_only=True : only when the other hospital is the SUBJECT, i.e. the sentence starts with its name
                        ("Navkar Hospital performs eye surgery" inside the record of Sakar Hospital)."""
    found = []
    if not subject_only and CL.CX["directory"].search(masked): return found
    for m in ORG.finditer(masked):
        if subject_only and masked[:m.start()].strip().lower() not in ("", "the"): continue
        ws = [t.lower() for t in TOK.findall(m.group(1))]
        ident = [w for w in ws if w not in common and len(w) > 2]
        if ident and not any(same_word(w, name_toks) for w in ident): found.append(" ".join(ident))
    return found


def build(F, H):
    name_toks, common = name_tools(F)
    ntok = dict(zip(F.unique_id, name_toks)); nname = dict(zip(F.unique_id, F.name))
    # ---- every sentence of every record -----------------------------------------------------------------------
    rows = []                                   # uid, field, item index, n items in field, sentence, masked sentence
    rowstat = {}
    for r in F.itertuples():
        uid = r.unique_id; nm = r.name.strip(); raw_n = {}; uniq_n = {}
        for fld in FIELDS:
            items = getattr(r, fld + "_l"); raw_n[fld] = len(items); seen = set(); kept = []
            for t in items:
                t = t.strip(); k = re.sub(r"\W+", " ", t.lower()).strip()
                if t and k not in seen: seen.add(k); kept.append(t)
            uniq_n[fld] = len(kept)
            for i, t in enumerate(kept):
                for seg in CL.SPLIT.split(t):
                    if seg and len(seg) >= 3: rows.append((uid, fld, i, len(kept), seg))
        dsegs = [s for s in CL.SPLIT.split(r.description) if s and len(s) >= 3]
        for i, seg in enumerate(dsegs): rows.append((uid, "description", i, len(dsegs), seg))
        rowstat[uid] = (sum(raw_n.values()), sum(uniq_n.values()), sum(v == CAP for v in raw_n.values()), len(r.description))
    U = pd.DataFrame(rows, columns=["uid", "field", "idx", "n_items", "seg"])
    common_org = common | ordinary_words(U.seg)
    U["masked"] = [mask_own(s, nname[u], ntok[u], common) for u, s in zip(U.uid, U.seg)]
    U["key"] = U.masked.map(norm_key)
    df = U[U.key != ""].drop_duplicates(["uid", "key"]).key.value_counts()
    U["df"] = U.key.map(df).fillna(1).astype(int)
    U["words"] = U.seg.str.split().map(len)
    for k, rx in DETAILS.items(): U["d_" + k] = U.masked.map(lambda s: bool(rx.search(s)))
    U["n_detail"] = U[["d_" + k for k in DETAILS]].sum(axis=1)
    U["bio"] = U.masked.map(lambda s: bool(CL.CX["bio"].search(s)))
    U["orgs"] = [other_orgs(m, ntok[u], common_org) for u, m in zip(U.uid, U.masked)]
    U["n_org"] = U.orgs.map(len)
    U["subj"] = [other_orgs(m, ntok[u], common_org, True) for u, m in zip(U.uid, U.masked)]
    U["n_subj"] = U.subj.map(len)

    # ---- row level ----------------------------------------------------------------------------------------------
    g = U.groupby("uid")
    R = pd.DataFrame({
        "n_sentences": g.size(),
        "row_template_share": g.df.apply(lambda x: (x >= TEMPLATE_DF).mean()),
        "row_unique_share": g.df.apply(lambda x: (x == 1).mean()),
        "row_mean_words": g.words.mean(),
        "row_detail_share": g.n_detail.apply(lambda x: (x > 0).mean()),
        "row_count_share": g.d_count.mean(),
        "row_other_org_sentences": g.n_org.apply(lambda x: (x > 0).sum()),
        "row_other_org_nonbio": U[~U.bio].groupby("uid").n_org.apply(lambda x: (x > 0).sum()),
        "row_other_org_distinct": g.orgs.apply(lambda x: len(set(o for l in x for o in l))),
        "row_other_subject_sentences": g.n_subj.apply(lambda x: (x > 0).sum()),
        "row_other_subject_distinct": g.subj.apply(lambda x: len(set(o for l in x for o in l))),
    }).reindex(F.unique_id).fillna(0)
    st = pd.DataFrame.from_dict(rowstat, orient="index", columns=["raw_items", "uniq_items", "lists_at_cap", "desc_chars"]).reindex(F.unique_id)
    R["log_n_sentences"] = np.log1p(R.n_sentences)
    R["lists_at_cap"] = st.lists_at_cap.values
    R["all_lists_at_cap"] = (st.lists_at_cap.values == 3).astype(int)
    R["row_repeat_share"] = ((st.raw_items - st.uniq_items) / st.raw_items.clip(lower=1)).values     # same item written twice inside one list
    R["row_other_org_share"] = R.row_other_org_sentences / R.n_sentences.clip(lower=1)
    R["row_other_org_2plus"] = (R.row_other_org_distinct >= 2).astype(int)
    R["row_other_org_3plus"] = (R.row_other_org_distinct >= 3).astype(int)
    R["row_other_subject_any"] = (R.row_other_subject_sentences >= 1).astype(int)
    R["row_other_subject_2plus"] = (R.row_other_subject_sentences >= 2).astype(int)
    R = R.drop(columns=["n_sentences"]).assign(n_sentences=R.n_sentences).reset_index().rename(columns={"unique_id": "uid", "index": "uid"})

    # ---- claim level --------------------------------------------------------------------------------------------
    H = H.copy()
    H["masked"] = [mask_own(s, nname.get(u, ""), ntok.get(u, set()), common) for u, s in zip(H.uid, H.seg)]
    mm = [match_service(m, s) for m, s in zip(H.masked, H.service)]
    H["echo"] = [x is None for x in mm]                               # the service word only occurs inside the record's own name
    H["key"] = H.masked.map(norm_key); H["df"] = H.key.map(df).fillna(1).astype(int)
    H["words"] = H.seg.str.split().map(len)
    for k, rx in DETAILS.items(): H["d_" + k] = H.masked.map(lambda s: bool(rx.search(s)))
    H["orgs"] = [other_orgs(m, ntok.get(u, set()), common_org) for u, m in zip(H.uid, H.masked)]
    H["subj"] = [other_orgs(m, ntok.get(u, set()), common_org, True) for u, m in zip(H.uid, H.masked)]

    def offtopic(masked, x, s):
        """Is the matched phrase itself about teeth / eyes / skin / alternative medicine / physiotherapy?
        Looks only at the words attached to the match (35 characters before, 20 after, not past a comma, slash or 'and')."""
        if x is None: return False
        m = x[1]; pre = OFFCUT.split(masked[max(0, m.start() - 35):m.start()])[-1]; post = OFFCUT.split(masked[m.end():m.end() + 20])[0]
        return bool(OFFRX[s].search(pre + " " + m.group(0) + " " + post))
    H["offtopic"] = [offtopic(m, x, s) for m, x, s in zip(H.masked, mm, H.service)]
    pos = U.drop_duplicates(["uid", "field", "seg"]).set_index(["uid", "field", "seg"])[["idx", "n_items"]]
    H = H.join(pos, on=["uid", "field", "seg"])
    H["relpos"] = (H.idx / (H.n_items - 1).clip(lower=1)).fillna(0)
    nsent = dict(zip(R.uid, R.n_sentences)); desc = dict(zip(F.unique_id, F.description))
    out = []
    for (uid, s), h0 in H.groupby(["uid", "service"], sort=False):
        h = h0[~h0.echo].drop_duplicates("key")
        n = len(h); e = int(h0.echo.sum())
        d = mask_own(desc.get(uid, ""), nname.get(uid, ""), ntok.get(uid, set()), common)
        rec = {"uid": uid, "service": s, "n_support": n, "log_n_support": np.log1p(n), "single_support": int(n <= 1), "n_fields_noecho": h.field.nunique(),
               "desc_mentions": int(match_service(d, s) is not None)}
        if n:
            ok = h[h["flags"].eq("") & ~h.offtopic]                    # usable sentences: no caution flag, not about another kind of care
            dk = [k for k in DETAILS if h["d_" + k].any()]
            rec.update({
                "n_detail_kinds": len(dk), **{"has_" + k: int(k in dk) for k in DETAILS},
                "detail_sentence_share": float((h[["d_" + k for k in DETAILS]].any(axis=1)).mean()),
                "template_share": float((h.df >= TEMPLATE_DF).mean()),
                "all_template": int((h.df >= TEMPLATE_DF).all()),
                "n_unique_wording": int((h.df == 1).sum()),
                "any_unique_wording": int((h.df == 1).any()),
                "min_log_df": float(np.log(h.df.min())),
                "max_words": int(h.words.max()), "bare_share": float((h.words <= 3).mean()),
                "flag_share": float(h["flags"].ne("").mean()),
                "offtopic_share": float(h.offtopic.mean()), "all_offtopic": int(h.offtopic.all()),
                "n_usable": len(ok), "any_usable": int(len(ok) > 0),
                "usable_named_only": int(len(ok[ok.cls.isin(["infra", "proc"])]) > 0),
                "text_share": n / max(1, nsent.get(uid, 1)),
                "first_relpos": float(h.relpos.min()), "mean_relpos": float(h.relpos.mean()),
                "support_other_org": int(h.orgs.map(len).gt(0).any()),
                "support_other_subject": int(h.subj.map(len).gt(0).any()),
            })
        rec["n_echo_hits"] = e                                          # diagnostic, dropped from the CSV (it is name information)
        out.append(rec)
    Cf = pd.DataFrame(out).fillna(0)
    return Cf, R, U, H


def check(Cf, R, H, F):
    """Extra tests the shared yardstick does not run: (1) does a feature still help once record size is in the model,
    (2) what the features say about named records."""
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "analysis"))
    import trust
    from eval_feature import cv_auc
    from sklearn.metrics import roc_auc_score
    C = trust.features().merge(Cf, on=["uid", "service"], how="left").merge(R, on="uid", how="left")
    S = C[C.y.notna()].reset_index(drop=True); hosp = (S.facilityTypeId == "hospital").values
    print("\n== name echo ==")
    e = S.assign(only_echo=(S.n_support == 0) & (S.n_echo_hits > 0), any_echo=S.n_echo_hits > 0)
    print(e.groupby("y")[["any_echo", "only_echo"]].agg(["sum", "mean"]).round(3).to_string())
    base = trust.FEATS; size = base + ["log_n_sentences"]
    b0, b0h, b1, b1h = cv_auc(S, base), cv_auc(S, base, hosp), cv_auc(S, size), cv_auc(S, size, hosp)
    print(f"\n== size control ==\ncurrent formula {b0:.3f} (hospitals {b0h:.3f}) | + record size (log sentences in the record) {b1:.3f} (hospitals {b1h:.3f})")
    print("own AUC of record size:", round(roc_auc_score(S.y, S.log_n_sentences), 3), "| hospitals:", round(roc_auc_score(S.y[hosp], S.log_n_sentences[hosp]), 3))
    rows = []
    for c in [c for c in list(Cf.columns) + list(R.columns) if c not in ("uid", "service", "log_n_sentences", "n_sentences", "n_echo_hits")]:
        v = S[c].fillna(0)
        if v.nunique() < 2: continue
        rows.append((c, round(float(np.corrcoef(v, S.log_n_sentences)[0, 1]), 2), round(cv_auc(S, base + [c]) - b0, 3), round(cv_auc(S, base + [c], hosp) - b0h, 3),
                     round(cv_auc(S, size + [c]) - b1, 3), round(cv_auc(S, size + [c], hosp) - b1h, 3)))
    print(pd.DataFrame(rows, columns=["feature", "corr_with_size", "gain", "gain_hosp", "gain_after_size", "gain_after_size_hosp"]).to_string(index=False))
    # (3) the silver "likely real" group is made of facilities NAMED for the service, i.e. specialists in it.
    #     A feature that only detects "this record is mostly about the service" will separate the silver groups and still say
    #     nothing about an ordinary general hospital. Test: where do the unlabelled claims (general hospitals) sit, between the two groups?
    T = C[C.service.isin(trust.FIT_SERVICES) & (C.facilityTypeId == "hospital")].copy()
    T["grp"] = np.where(T.y == 1, "likely_real", np.where(T.y == 0, "likely_false", "unlabelled"))
    feats = [c for c in list(Cf.columns) + list(R.columns) if c not in ("uid", "service", "n_echo_hits")]
    m = T.groupby("grp")[feats].mean().T
    m["unlabelled_position"] = (m.unlabelled - m.likely_false) / (m.likely_real - m.likely_false)
    print("\n== specialist-proxy test, hospitals only, 7 fitted services ==  group sizes:", T.grp.value_counts().to_dict())
    print("unlabelled_position: 0 = general-hospital claims look like the likely-false group on this feature, 1 = they look like the likely-real group")
    print(m.round(3).to_string())
    med = T.groupby("grp")[["n_support", "text_share", "first_relpos", "n_sentences"]].median()
    print("medians:\n", med.round(3).to_string())
    # same question asked inside the likely-real group: names that ALSO carry a broad word (multi, general, nursing home ...) vs pure specialist names
    broad = S.name.str.lower().str.contains(trust.BROAD, regex=True).values
    print("\nlikely-real claims with a broad word in the name:", int((broad & (S.y == 1)).sum()), "| pure specialist names:", int((~broad & (S.y == 1)).sum()))
    rows = []
    for c in ["n_support", "text_share", "first_relpos", "desc_mentions", "has_staff", "offtopic_share", "all_offtopic", "row_other_org_distinct", "row_other_subject_any", "log_n_sentences"]:
        a = (S.y == 0) | ((S.y == 1) & broad); b = (S.y == 0) | ((S.y == 1) & ~broad)
        rows.append((c, round(roc_auc_score(S.y[a], S[c][a]), 3), round(roc_auc_score(S.y[b], S[c][b]), 3), round(S[c][(S.y == 1) & broad].mean(), 3), round(S[c][(S.y == 1) & ~broad].mean(), 3), round(S[c][S.y == 0].mean(), 3)))
    print(pd.DataFrame(rows, columns=["feature", "AUC_false_vs_broad_named_real", "AUC_false_vs_pure_specialist_real", "mean_broad_real", "mean_pure_real", "mean_false"]).to_string(index=False))
    # (4) what the recommended features would do to the score of each named record
    from sklearn.linear_model import LogisticRegression
    for extra in (["all_offtopic"], ["all_offtopic", "row_other_org_3plus"], ["all_offtopic", "row_other_subject_any"], ["all_offtopic", "row_other_org_3plus", "n_support"]):
        mdl = LogisticRegression(max_iter=2000).fit(S[base + extra].fillna(0).values, S.y.values)
        C["trust_" + "+".join(extra)] = 100 * mdl.predict_proba(C[base + extra].fillna(0).values)[:, 1]
        print("refit with", extra, "| odds multipliers:", {k: round(float(np.exp(v)), 2) for k, v in zip(extra, mdl.coef_[0][len(base):])})
    C["trust_now"] = 100 * LogisticRegression(max_iter=2000).fit(S[base].values, S.y.values).predict_proba(C[base].values)[:, 1]
    tc = [c for c in C.columns if c.startswith("trust_")]
    print("\n== named records ==")
    pd.set_option("display.width", 250)
    show = ["n_support", "n_fields_noecho", "n_detail_kinds", "template_share", "any_unique_wording", "offtopic_share", "all_offtopic", "desc_mentions", "text_share", "first_relpos", "support_other_org"]
    rshow = ["n_sentences", "row_template_share", "row_detail_share", "lists_at_cap", "row_other_org_distinct", "row_other_org_nonbio", "row_other_org_3plus", "row_other_subject_sentences", "row_repeat_share"]
    for uid, svc in ARGS_RECORDS:
        r = F[F.unique_id.str.startswith(uid)].iloc[0]
        print(f"\n{r['name']} | {r.address_city} | {svc}")
        print("  claim:", Cf[(Cf.uid == r.unique_id) & (Cf.service == svc)][show].round(2).to_dict("records"))
        print("  row:  ", R[R.uid == r.unique_id][rshow].round(2).to_dict("records"))
        print("  percentile among all rows:", {c: round(float((R[c] <= R[R.uid == r.unique_id][c].iloc[0]).mean()), 3) for c in ["n_sentences", "row_other_org_distinct", "lists_at_cap"]})
        print("  score:", C[(C.uid == r.unique_id) & (C.service == svc)][tc].round(1).to_dict("records"))
        hh = H[(H.uid == r.unique_id) & (H.service == svc)]
        for x in hh.head(6).itertuples(): print(f"     [{x.field[:4]}|{x.cls}|echo {int(x.echo)}|off {int(x.offtopic)}|seen at {x.df} facilities] {x.seg[:140]}")


ARGS_RECORDS = [("b8a5401f", "dialysis")]

if __name__ == "__main__":
    F = load_facilities()
    hp = os.path.join(OUT, "hits.pkl")
    H = pd.read_pickle(hp) if os.path.exists(hp) else CL.build_hits(F)
    Cf, R, U, Hx = build(F, H)
    Cf.drop(columns=["n_echo_hits"]).round(4).to_csv(os.path.join(OUT, "feat_specificity_claim.csv"), index=False)
    R.round(4).to_csv(os.path.join(OUT, "feat_specificity_row.csv"), index=False)
    print("sentences", len(U), "| distinct wordings", U.key.nunique(), "| share of sentences that are templates (wording at", TEMPLATE_DF, "or more facilities):", round(float((U.df >= TEMPLATE_DF).mean()), 3))
    print("claims", len(Cf), "| hits", len(Hx), "| name-echo hits", int(Hx.echo.sum()), "| claims left with no support after removing echoes", int((Cf.n_support == 0).sum()))
    print("rows", len(R), "| all three lists cut at", CAP, ":", int(R.all_lists_at_cap.sum()), "| any list cut:", int((R.lists_at_cap > 0).sum()))
    if "--check" in sys.argv:
        ARGS_RECORDS += [tuple(a.split(":")) for a in sys.argv[1:] if ":" in a]
        check(Cf, R, Hx, F)
