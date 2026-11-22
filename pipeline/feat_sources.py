"""Feature family: WHERE DID THE ROW'S INFORMATION COME FROM?

Reads only raw data (facilities.csv through common.load_facilities, the India Post PIN directory) and
pipeline/out/claims.csv (the list of facility x service claims). No dependence on research/data_work.

    python -I pipeline/feat_sources.py            # writes pipeline/out/feat_sources_row.csv and feat_sources_claim.csv
    python -I pipeline/feat_sources.py --show ID  # print the parsed URLs of one record (unique_id prefix)

Every web address attached to a row (source_urls + websites, de-duplicated) is put in one of these boxes:
    own      on the record's official website domain, or the address spells the record's own name
    social   facebook / instagram / linkedin / maps ... (says nothing either way, ignored)
    foreign  everything else: a directory page, a list, a journal article, or ANOTHER facility's page
Row features count the boxes; place features compare the places written in the addresses with the record's state.
Claim features ask whether the service word itself appears in an address path (own vs foreign).

Leakage guard: the facility name is used only to recognise "this address is about this record". Specialty and
generic words (eye, dental, kidney, hospital ...) are dropped from the name before matching, and for the claim
features every word of the record's own name is removed from the address before the service word is looked for,
so "…/abc-kidney-dialysis-centre" cannot vote for dialysis on "ABC Kidney Dialysis Centre".
facilityTypeId and the specialties column are never read.

What the yardstick said (2026-11-21, 744 silver claims; current formula AUC 0.799, hospitals only 0.741):
    other_sites_2plus   +0.007 overall, +0.017 within hospitals (bootstrap range includes 0)   <- only row sign worth adding
    svc_in_own_url      +0.004 / +0.006, fires on 25 silver claims of which 23 are likely real  <- small positive evidence
    own_share, n_foreign_log, every "other state" and e-mail / Facebook feature: gain 0 or negative. They repeat what the
    existing 'sources' sign (6+ source ids) already measures (rank correlation of n_foreign_log with it: 0.75).
    has_official_site and no_own_url show gains but in a direction with no plain reason; treat them as profile proxies.
"""
import sys, os, re
from collections import Counter
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ROOT, OUT, load_facilities, norm_name

# ---------------------------------------------------------------- web address parsing
SLD = {"gov.in", "nic.in", "co.in", "org.in", "ac.in", "edu.in", "net.in", "res.in", "gen.in", "firm.in", "ind.in", "co.uk", "org.uk", "ac.uk", "com.au", "com.sg", "co.za", "com.bd", "com.np", "business.site", "com.in"}
SOCIAL = {"facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "youtu.be", "goo.gl", "google.com", "google.co.in", "g.page", "mappls.com", "wa.me", "whatsapp.com",
          "t.me", "pinterest.com", "bit.ly", "g.co", "latlong.net", "mapcarta.com", "wikimapia.org", "mapsofindia.com", "threads.net", "linktr.ee", "threads.com"}
JOURNAL = {"nih.gov", "researchgate.net", "lww.com", "sciencedirect.com", "springer.com", "wiley.com", "biomedcentral.com", "scribd.com", "academia.edu", "semanticscholar.org", "tandfonline.com",
           "sagepub.com", "bmj.com", "nature.com", "plos.org", "mdpi.com", "frontiersin.org", "cureus.com", "jcdr.net", "ijcmr.com", "slideshare.net", "doi.org", "elsevier.com", "thelancet.com", "oup.com", "medknow.com"}
FREEMAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "hotmail.com", "rediffmail.com", "ymail.com", "outlook.com", "live.com", "icloud.com", "aol.com", "rocketmail.com", "live.in", "msn.com", "protonmail.com"}


def split_url(u):
    u = str(u).strip().lower(); u = re.sub(r"^[a-z]+://", "", u)
    m = re.split(r"[/?#]", u, maxsplit=1); h = m[0].split("@")[-1].split(":")[0]
    h = re.sub(r"^(www\d?|m|en|in)\.", "", re.sub(r"^(www\d?|m)\.", "", h))
    return h, (m[1] if len(m) > 1 else "")


def reg_domain(h):
    p = h.split(".")
    if len(p) >= 3 and ".".join(p[-2:]) in SLD: return ".".join(p[-3:])
    return ".".join(p[-2:]) if len(p) >= 2 else h


def toks(s):
    return [t for t in re.split(r"[^a-z0-9]+", s.lower()) if t]


# ---------------------------------------------------------------- the record's own name (identity only)
GENERIC = set("""hospital hospitals clinic clinics centre center centres centers care health healthcare medical medicare medicals nursing home homes multi multispeciality multispecialty
speciality specialty specialities super superspeciality dr doctor doctors the and of for pvt ltd private limited trust foundation institute research memorial charitable general society
eye eyes dental dentist dentistry skin hair kidney heart cardiac children child childrens maternity women womens ortho orthopaedic orthopedic ent diagnostic diagnostics lab labs laboratory
pathology scan scans imaging physiotherapy physio ayurveda ayurvedic homeo homeopathy homoeopathy homeopathic surgical surgery fertility ivf test tube baby cancer neuro dialysis sri shri shree
new india indian city unit services service group llp inc mission govt government district civil community primary sub polyclinic poly dispensary pharmacy medicine medicines laser cosmetic
vision netralaya nethralaya smile tooth teeth derma dermatology retina lasik trauma emergency icu institute sciences science college university school department wellness life line plus
mother mothers kids ladies gynae gynec stone urology uro gastro liver brain spine bone joint nephro renal piles diabetes diabetic thyroid chest lung clinic's www com org
plastic aesthetic aesthetics reconstructive cardiology cardio cardiothoracic oncology ophthalmic ophthalmology orthodontic orthodontics implant implants nephrology neurology gastroenterology
diabetology pediatric paediatric pediatrics paediatrics gynecology gynaecology obstetrics psychiatry psychiatric rehabilitation medicity nursinghome multispecialityhospital superspecialty
maternal neonatal newborn infertility andrology oncology radiology sonography ultrasound xray pharma chemist opticals optical optics dentals vascular endocrine ortho""".split())


def name_keys(name, city):
    t = toks(norm_name(name)); place = set(toks(norm_name(city)))
    return [x for x in dict.fromkeys(t) if len(x) >= 4 and not x.isdigit() and x not in GENERIC and x not in place], set(t)


def mentions(sq, keys):
    """Does the squashed address spell the record's name?  Two name words, one long one, or the leading name word (5+ letters)."""
    if not keys: return False
    hit = [k for k in keys if k in sq]
    if len(keys) == 1: return bool(hit)
    return len(hit) >= 2 or any(len(k) >= 7 for k in hit) or (len(keys[0]) >= 5 and keys[0] in sq)


# ---------------------------------------------------------------- places written inside addresses
STATES = {"andhra pradesh": ["andhrapradesh", "andhra"], "arunachal pradesh": ["arunachal", "arunachalpradesh"], "assam": ["assam"], "bihar": ["bihar"], "chhattisgarh": ["chhattisgarh", "chattisgarh"],
          "goa": ["goa"], "gujarat": ["gujarat", "gujrat"], "haryana": ["haryana"], "himachal pradesh": ["himachal", "himachalpradesh"], "jharkhand": ["jharkhand"], "karnataka": ["karnataka"],
          "kerala": ["kerala"], "madhya pradesh": ["madhyapradesh", "mpdoctors"], "maharashtra": ["maharashtra"], "manipur": ["manipur"], "meghalaya": ["meghalaya"], "mizoram": ["mizoram"],
          "nagaland": ["nagaland"], "odisha": ["odisha", "orissa"], "punjab": ["punjab"], "rajasthan": ["rajasthan"], "sikkim": ["sikkim"], "tamil nadu": ["tamilnadu"], "telangana": ["telangana"],
          "tripura": ["tripura"], "uttar pradesh": ["uttarpradesh"], "uttarakhand": ["uttarakhand", "uttaranchal"], "west bengal": ["westbengal", "bengal"], "delhi": ["delhi", "newdelhi"],
          "jammu and kashmir": ["jammu", "kashmir"], "chandigarh": ["chandigarh"], "puducherry": ["puducherry", "pondicherry"], "ladakh": ["ladakh"]}
GOV_CODE = {"tn": "tamil nadu", "up": "uttar pradesh", "mp": "madhya pradesh", "ap": "andhra pradesh", "wb": "west bengal", "hp": "himachal pradesh", "uk": "uttarakhand", "cg": "chhattisgarh", "jk": "jammu and kashmir",
            "ts": "telangana", "tg": "telangana", "pb": "punjab", "hr": "haryana", "ka": "karnataka", "mh": "maharashtra", "gj": "gujarat", "rj": "rajasthan", "br": "bihar", "od": "odisha", "as": "assam"}
STATE_FIX = {"tamilnadu": "tamil nadu", "u p": "uttar pradesh", "up": "uttar pradesh", "orissa": "odisha", "pondicherry": "puducherry", "chattisgarh": "chhattisgarh", "new delhi": "delhi", "jammu kashmir": "jammu and kashmir",
             "punjab region": "punjab", "nct of delhi": "delhi", "uttaranchal": "uttarakhand", "the government of nct of delhi": "delhi", "jammu  kashmir": "jammu and kashmir", "telengana": "telangana"}
# place words that are also everyday hospital / person names: never read as a place
AMBIG = set("""krishna ganga salem bharat north south east west central india indian nagar road city hospital rama ram sagar unity vijaya vijay chandra raja anand shanti janta seva
hope star medical kota karur durg mandi banda bid pali una mau daman diu washim patan morbi nadia doda reasi""".split())


def build_places(F):
    """place word -> state.  Sources: state names, big cities of the facility table (10+ rows, 90% in one state), PIN-directory districts."""
    P = {}
    try:
        pin = pd.concat([pd.read_csv(os.path.join(ROOT, f), dtype=str, usecols=["district", "statename"]) for f in ("indiaPincodeDirectory1.csv", "indiaPincodeDirectory2.csv")]).dropna()
        pin["d"] = pin.district.map(norm_name); pin["s"] = pin.statename.map(norm_name).replace(STATE_FIX)
        g = pin.groupby("d").s.agg(lambda x: float(x.value_counts(normalize=True).iloc[0])); gs = pin.groupby("d").s.agg(lambda x: x.value_counts().index[0])
        for d in g.index:
            if g[d] >= 0.95 and gs[d] in STATES and len(d.replace(" ", "")) >= 5: P[d.replace(" ", "")] = gs[d]
    except Exception as e:
        print("PIN directory not used:", e)
    c = F[F.state_n.isin(STATES)].assign(c=F.address_city.map(norm_name)); c = c[c.c.str.len() >= 4]
    g = c.groupby("c").state_n.agg(["size", lambda x: x.value_counts(normalize=True).iloc[0], lambda x: x.value_counts().index[0]]); g.columns = ["n", "share", "st"]
    for d, r in g[(g.n >= 10) & (g.share >= 0.9)].iterrows(): P[d.replace(" ", "")] = r.st
    for st, al in STATES.items():
        for a in al: P[a] = st
    P.update({"bangalore": "karnataka", "bengaluru": "karnataka", "bombay": "maharashtra", "calcutta": "west bengal", "madras": "tamil nadu", "gurgaon": "haryana", "gurugram": "haryana", "noida": "uttar pradesh",
              "vizag": "andhra pradesh", "trivandrum": "kerala", "cochin": "kerala", "kochi": "kerala", "mysore": "karnataka", "baroda": "gujarat", "pune": "maharashtra", "agra": "uttar pradesh", "goa": "goa",
              "dwarka": "delhi", "secunderabad": "telangana", "navimumbai": "maharashtra", "thane": "maharashtra"})
    for a in AMBIG: P.pop(a, None)
    return P


BIGRAM_OK = {a for al in STATES.values() for a in al} | {"newdelhi", "navimumbai", "tamilnadu", "andhrapradesh", "madhyapradesh", "uttarpradesh", "himachalpradesh", "westbengal", "arunachalpradesh"}


def url_places(host, path, P, skip=frozenset()):
    """States named in an address: whole words of the path, word pairs, and labels of the host (nashik.gov.in, health.delhi.gov.in)."""
    t = toks(path); out = set()
    for i, x in enumerate(t):
        if x in P and x not in skip: out.add(P[x])
        if i + 1 < len(t) and (x + t[i + 1]) in BIGRAM_OK and (x + t[i + 1]) in P and x not in skip: out.add(P[x + t[i + 1]])
    lab = host.split(".")
    for x in lab[:-1]:
        for y in toks(x):
            if y in P and y not in skip: out.add(P[y])
        if x in P and x not in skip: out.add(P[x])
    if host.endswith((".gov.in", ".nic.in")):
        for x in lab[:-2]:
            for y in toks(x):
                if y in GOV_CODE: out.add(GOV_CODE[y])
                for code, st in GOV_CODE.items():        # tnhealth, upnrhm, mphealth, cghealth, wbhealth
                    if re.fullmatch(code + r"(health|nrhm|nhm|medical|hfw|govt|police|esic)\w*", y): out.add(st)
    return out


# ---------------------------------------------------------------- service words inside address paths (claim level)
SVC_URL = {
 "dialysis": r"dialysis|hemodialysis|haemodialysis|nephrolog", "emergency_obstetric": r"obstetric|maternity|caesarean|cesarean|c section|lscs|labour room|labor room|high risk pregnancy|normal delivery|delivery",
 "nicu": r"nicu|neonat|newborn|sncu", "cardiac_surgery": r"cardiac surg|cardio ?thoracic|ctvs|cabg|bypass|heart surg|open heart|cardiovascular surg", "cath_lab": r"cath ?lab|angioplast|angiograph|interventional cardiolog|catheteri",
 "burn_care": r"burns?\b", "blood_bank": r"blood ?bank|blood cent|transfusion", "mri": r"\bmri\b|magnetic resonance", "ct_scan": r"\bct ?scan|computed tomograph|\bct\b", "icu": r"\bicu\b|intensive care|critical care",
 "trauma_emergency": r"trauma|emergency|casualty", "cataract_surgery": r"cataract|phaco", "chemotherapy": r"chemo|oncolog", "radiotherapy": r"radiotherap|radiation oncolog|linac", "ventilator": r"ventilat",
 "stroke": r"stroke|thrombolys", "snakebite_poison": r"snake|poison|venom", "tb": r"\btb\b|tubercul|dots", "ortho_surgery": r"joint replace|knee replace|hip replace|arthroplast|arthroscop|orthop"}


SVC_DEPT = {"dialysis": r"nephrolog|kidney|renal", "emergency_obstetric": r"gyna?ecolog|obstetric|\bobg\b|obgyn|maternity|women", "nicu": r"neonat|pa?ediatric|child", "cardiac_surgery": r"cardiac|cardiolog|heart|ctvs|cardio",
            "cath_lab": r"cardiac|cardiolog|heart|cardio", "burn_care": r"plastic surg|burn", "blood_bank": r"blood", "mri": r"radiolog|imaging|\bmri\b", "ct_scan": r"radiolog|imaging|\bct\b", "icu": r"critical care|intensive|\bicu\b|emergency",
            "trauma_emergency": r"trauma|emergency|casualty|accident", "cataract_surgery": r"ophthalm|cataract|eye", "chemotherapy": r"oncolog|cancer|chemo", "radiotherapy": r"oncolog|cancer|radiation|radiotherap",
            "ventilator": r"critical care|intensive|\bicu\b|ventilat", "stroke": r"neurolog|stroke|neuro", "snakebite_poison": r"toxicolog|poison|snake|emergency", "tb": r"pulmonolog|chest|\btb\b|tubercul|respiratory",
            "ortho_surgery": r"orthop|joint|arthro"}


# ---------------------------------------------------------------- per record
def parse_record(r, P):
    keys, alln = name_keys(r["name"], r.address_city)
    oh, _ = split_url(r.officialWebsite) if r.officialWebsite else ("", "")
    od = reg_domain(oh) if oh else ""
    if od in SOCIAL or od in JOURNAL: od = ""
    urls = list(dict.fromkeys([u for u in list(r.source_urls_l) + list(r.websites_l) if isinstance(u, str) and "." in u]))
    rows = []
    for u in urls:
        h, p = split_url(u); d = reg_domain(h); sq = re.sub(r"[^a-z0-9]", "", h + p)
        kind = "social" if d in SOCIAL else ("own" if (od and d == od) or mentions(sq, keys) else "foreign")
        rows.append({"url": u, "host": h, "path": p, "dom": d, "kind": kind, "on_official": int(bool(od) and d == od), "journal": int(d in JOURNAL), "gov": int(h.endswith((".gov.in", ".nic.in"))),
                     "states": url_places(h, p, P, alln) if kind != "social" else set(), "ptoks": toks(p)})
    return keys, alln, od, rows


LISTY = re.compile(r"\b(hospitals|clinics|doctors|list|lists|listing|directory|directories|network|empanelled|empaneled|cashless|best|top|near|nearby|category|search)\b")
PROFILE = re.compile(r"\b(clinic|hospital|doctor|dr|profile|centre|center)\b")


OTHER_SITE_MAX = 10
ROW_COLS = ["own_share", "n_foreign", "n_foreign_log", "n_domains_log", "n_other_sites", "other_sites_2plus", "other_sites_strict_2plus", "n_other_hosts_log", "other_profiles_3plus", "n_list_pages_log",
            "directory_share", "journal_share", "gov_share", "n_url_other_state", "url_other_state_share", "url_other_state_2plus", "most_urls_other_state", "gov_other_state",
            "email_mismatch", "fb_slug_other", "site_not_name", "site_shared_by_records", "contact_conflicts", "has_official_site", "no_own_url", "n_source_ids_log", "web_page_share", "n_source_types"]
CLAIM_COLS = ["svc_in_own_url", "svc_on_official_site", "dept_on_official_site", "svc_in_foreign_url", "svc_only_in_foreign_url", "svc_on_other_facility_page", "svc_on_doctor_page", "svc_on_list_page", "svc_in_any_url"]


def row_features(r, P, shared, offn=None):
    keys, alln, od, U = parse_record(r, P)
    st = r.state_n if r.state_n in STATES else P.get(str(r.state_n).replace(" ", ""), P.get(norm_name(r.address_city).replace(" ", "")))   # state cell sometimes holds a district
    ns = [u for u in U if u["kind"] != "social"]; own = [u for u in ns if u["kind"] == "own"]; fo = [u for u in ns if u["kind"] == "foreign"]
    n = len(ns); f = {"uid": r.unique_id}
    f["own_share"] = len(own) / n if n else np.nan                       # share of non-social addresses that are the record's own
    f["no_own_url"] = int(n > 0 and not own)
    f["n_foreign"] = len(fo)                                              # distinct addresses about something else
    f["n_foreign_log"] = np.log1p(len(fo))
    f["n_domains_log"] = np.log1p(len({u["dom"] for u in ns}))
    f["n_foreign_domains_log"] = np.log1p(len({u["dom"] for u in fo}))
    # OTHER ORGANISATIONS' WEBSITES: foreign addresses on a site that at most 10 of the 9,989 records carry.
    # A directory (practo, justdial ...) is on hundreds of records; a site on a handful of records is somebody's own website.
    oth = {u["dom"] for u in fo if shared.get(u["dom"], 0) <= OTHER_SITE_MAX and not u["journal"]}
    f["n_other_sites"] = len(oth); f["other_sites_2plus"] = int(len(oth) >= 2)
    f["other_sites_strict_2plus"] = int(len({u["dom"] for u in fo if shared.get(u["dom"], 0) <= 3 and not u["gov"] and not u["journal"]}) >= 2)   # stricter: on 3 records at most, no government sites
    f["n_other_hosts_log"] = np.log1p(len({u["host"] for u in fo if shared.get(u["dom"], 0) < 30 and not u["journal"]}))                            # wider: distinct hosts, sites on < 30 records
    # kinds of foreign address: a list of many facilities / one other provider's profile on a directory
    fdir = [u for u in fo if shared.get(u["dom"], 0) >= 30 and not u["gov"] and not u["journal"]]
    lst = [u for u in fo if LISTY.search(" ".join(u["ptoks"]))]
    prof = [u for u in fdir if u not in lst and PROFILE.search(" ".join(u["ptoks"]))]
    f["n_list_pages_log"] = np.log1p(len(lst)); f["n_other_profiles_log"] = np.log1p(len(prof)); f["other_profiles_3plus"] = int(len(prof) >= 3)
    # a second website that spells the record's name but is not the official one (sister organisation / copy)
    f["own_alt_site"] = int(any(u["kind"] == "own" and not u["on_official"] and shared.get(u["dom"], 0) <= 3 for u in ns))
    f["journal_share"] = np.mean([u["journal"] for u in ns]) if n else np.nan
    f["gov_share"] = np.mean([u["gov"] for u in ns]) if n else np.nan
    f["directory_share"] = np.mean([int(shared.get(u["dom"], 0) >= 30 and not u["gov"] and not u["journal"]) for u in ns]) if n else np.nan
    # places
    pl = [u for u in ns if u["states"]]
    other = [u for u in pl if st and st not in u["states"]]
    f["n_url_other_state"] = len(other) if st else np.nan
    f["url_other_state_share"] = (len(other) / len(pl)) if (st and pl) else (0.0 if st else np.nan)
    f["url_other_state_2plus"] = int(len(other) >= 2) if st else np.nan
    f["n_url_states"] = len(set().union(*[u["states"] for u in pl])) if pl else 0
    govo = [u for u in other if u["gov"]]
    f["gov_other_state"] = int(len(govo) >= 1) if st else np.nan
    f["n_gov_other_state"] = len(govo) if st else np.nan
    f["most_urls_other_state"] = int(len(other) >= 3 and len(other) / len(pl) >= 0.5) if st else np.nan
    f["foreign_other_state"] = len([u for u in other if u["kind"] == "foreign"]) if st else np.nan
    # contact identity
    sqn = lambda s: re.sub(r"[^a-z0-9]", "", str(s).lower())
    em = str(r.email).lower() if isinstance(r.email, str) else ""
    em = em if "@" in em and "protected" not in em else ""
    if em:
        loc, ed = em.split("@")[0], re.sub(r"[^a-z0-9.\-]", "", em.split("@")[-1])
        ok = (od and reg_domain(ed) == od) or mentions(sqn(em), keys) or any(k[:5] in sqn(loc) for k in keys)
        f["email_matches"] = int(bool(ok)); f["email_mismatch"] = int(not ok and bool(keys))
        f["email_own_domain"] = int(bool(od) and reg_domain(ed) == od)
    else:
        f["email_matches"] = 0; f["email_mismatch"] = 0; f["email_own_domain"] = 0
    fb = str(r.facebookLink).lower() if isinstance(r.facebookLink, str) else ""
    slug = re.sub(r"\d{6,}", "", split_url(fb)[1]) if "facebook" in fb else ""
    slug_words = [t for t in toks(slug) if len(t) >= 4 and t not in ("pages", "people", "profile")]
    f["fb_slug_other"] = int(bool(slug_words) and bool(keys) and not mentions(sqn(slug), keys) and not any(k in sqn(slug) for k in keys))
    f["site_matches_name"] = int(bool(od) and bool(keys) and any(k[:5] in sqn(od) for k in keys))
    f["has_official_site"] = int(bool(od))
    f["site_not_name"] = int(bool(od) and bool(keys) and not f["site_matches_name"])                 # official website spells some other name
    f["site_shared_by_records"] = int(bool(od) and offn is not None and offn.get(od, 0) >= 2)          # same official website on 2+ records (chain or host hospital)
    f["contact_conflicts"] = f["email_mismatch"] + f["fb_slug_other"] + int(bool(od) and bool(keys) and not f["site_matches_name"] and shared.get(od, 0) <= 3)
    # source ids / types
    ids = list(r.source_ids_l); ty = Counter(r.source_types_l); nt = sum(ty.values())
    f["n_source_ids_log"] = np.log1p(len(set(ids)))
    f["web_page_share"] = ty.get("dynamic", 0) / nt if nt else np.nan      # 'dynamic' = scraped web pages; 'overture' = map listing
    f["n_source_types"] = len(ty)
    f["has_name_key"] = int(bool(keys))
    return f, U, alln


LISTPAT = re.compile(r"\b(in|near|nct|doctors|hospitals|clinics|categories|category|best|top|list|listing|search|network|cashless)\b")
FACPAT = re.compile(r"\b(hospital|clinic|nursing|home|centre|center|institute)\b")
DOCPAT = re.compile(r"\b(dr|doctor)\b")


def page_kind(u):
    """A foreign address is a LIST of many providers, ONE other facility's page, or ONE doctor's page."""
    t = re.sub(r"^directories (hospitals|doctors) ", "", " ".join(u["ptoks"]))
    if LISTPAT.search(t): return "list"
    if DOCPAT.search(t): return "doctor"
    return "facility" if FACPAT.search(t) else "other"


def claim_features(uid, services, U, alln):
    out = []
    ns = [u for u in U if u["kind"] != "social"]
    # address text with every word of the record's own name removed, and every word that starts like one (nephro / nephrology) -- leak guard
    stems = {n[:5] for n in alln if len(n) >= 4}
    txt = [(u, " ".join(t for t in u["ptoks"] if t not in alln and t[:5] not in stems)) for u in ns]
    for s in services:
        rx = re.compile(SVC_URL[s]) if s in SVC_URL else None
        hit = [u for u, t in txt if rx and rx.search(t)]
        o = [u for u in hit if u["kind"] == "own"]; fo = [u for u in hit if u["kind"] == "foreign"]
        rd = re.compile(SVC_DEPT[s]) if s in SVC_DEPT else None
        dep = [u for u, t in txt if rd and rd.search(t) and u["on_official"]]
        out.append({"uid": uid, "service": s, "dept_on_official_site": int(bool(dep)), "svc_on_official_site": int(any(u["on_official"] for u in o)), "svc_in_own_url": int(bool(o)), "svc_in_foreign_url": int(bool(fo)), "svc_in_any_url": int(bool(hit)),
                    "svc_only_in_foreign_url": int(bool(fo) and not o),
                    "svc_on_other_facility_page": int(any(page_kind(u) == "facility" for u in fo)), "svc_on_doctor_page": int(any(page_kind(u) == "doctor" for u in fo)),
                    "svc_on_list_page": int(any(page_kind(u) == "list" for u in fo)), "svc_only_on_other_facility_page": int(any(page_kind(u) == "facility" for u in fo) and not o),
                    "_own_hit": o[0]["url"] if o else "", "_foreign_hit": fo[0]["url"] if fo else ""})
    return out


def main():
    F = load_facilities()
    F["state_n"] = F.address_stateOrRegion.map(norm_name).replace(STATE_FIX)
    P = build_places(F)
    # how many records carry each domain (directory = shared by many rows)
    shared = Counter()
    for a, b in zip(F.source_urls_l, F.websites_l):
        for d in {reg_domain(split_url(u)[0]) for u in set(a) | set(b) if isinstance(u, str) and "." in u}: shared[d] += 1
    offn = Counter()
    for w in F.officialWebsite:
        if w:
            d = reg_domain(split_url(w)[0])
            if d not in SOCIAL and d not in JOURNAL: offn[d] += 1
    if "--show" in sys.argv:
        r = F[F.unique_id.str.startswith(sys.argv[sys.argv.index("--show") + 1])].iloc[0]; f, U, _ = row_features(r, P, shared, offn)
        print(r["name"], "|", r.address_city, "|", r.state_n, "| official:", r.officialWebsite, "| email:", r.email, "| fb:", r.facebookLink)
        for u in U: print(f"  {u['kind']:8s} {','.join(sorted(u['states'])) or '-':22s} {u['url'][:110]}")
        print({k: round(float(f[k]), 3) for k in ROW_COLS})
        for c in claim_features(r.unique_id, list(SVC_URL), U, _): print("  ", c["service"], {k: c[k] for k in CLAIM_COLS if c[k]}, c["_own_hit"][:80], c["_foreign_hit"][:80]) if any(c[k] for k in CLAIM_COLS) else None
        return
    C = pd.read_csv(os.path.join(OUT, "claims.csv"), usecols=["uid", "service"]); svc = C.groupby("uid").service.apply(list).to_dict()
    R, K = [], []
    for _, r in F.iterrows():
        f, U, alln = row_features(r, P, shared, offn); R.append(f)
        if r.unique_id in svc: K += claim_features(r.unique_id, svc[r.unique_id], U, alln)
    R = pd.DataFrame(R); K = pd.DataFrame(K)
    R = R[["uid"] + ROW_COLS]; K = K[["uid", "service"] + CLAIM_COLS]
    R.round(4).to_csv(os.path.join(OUT, "feat_sources_row.csv"), index=False); K.to_csv(os.path.join(OUT, "feat_sources_claim.csv"), index=False)
    print("rows", len(R), "| claims", len(K), "| place words", len(P))
    print(R.drop(columns="uid").describe().T[["count", "mean", "50%", "max"]].round(3).to_string())
    print(K.drop(columns=["uid", "service"]).mean().round(4).to_string())


if __name__ == "__main__":
    main()
