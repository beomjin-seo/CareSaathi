"""Candidate features, family "who is each sentence about?"

For every sentence of the free-text fields (procedure, equipment, capability, description) decide whether it
  - names the record itself                      (own_name)
  - names ANOTHER organisation as subject/place  (other_org)   e.g. "... established at Lok Nayak Hospital"
  - names a place far from the record's address  (other_place) e.g. "Located in Surat" on an Ahmedabad record
  - states a total bed count                     (used for bed-count contradictions)
and roll that up
  (a) per facility            -> pipeline/out/feat_attribution_row.csv    (key uid)
  (b) per (facility, service) -> pipeline/out/feat_attribution_claim.csv  (key uid + service), using the supporting
      sentences in pipeline/out/hits.pkl: do THEY name another place/organisation, or sit next to sentences that do?
Also rebuilds two row signals whose code was lost: distinct landline area codes among phone_numbers, distinct source ids.

Leakage guard. The silver labels come from specialty words in the facility NAME. This script uses the name only to
tell "this sentence names the record" from "this sentence names someone else". Specialty words (trust.NEG / POS / BROAD
patterns, e.g. eye, dental, kidney, heart, maternity) are deleted from both sides before any comparison, so
"Asian Hospital" and "Asian Eye Hospital" compare as the same organisation. facilityTypeId and specialties are never read.

Second leak found while building this: a sentence that only repeats the facility's name ("X Kidney Hospital is listed in ...") is counted
as support for dialysis because the keyword sits inside the NAME. By construction only likely-real silver claims can have such support, so
any feature built on raw support counts or on "the supporting sentence names the record" looks far better than it is. The claim file therefore
carries only "clean" versions (name words masked before the service keyword is re-tested). The raw versions are written, prefixed leaky_,
only with --debug, for comparison; never feed them to the formula.

Run from the project root:  python -I pipeline/feat_attribution.py [--debug DIR]
Raw inputs only: facilities.csv, the two India Post PIN files, and hits.pkl (rebuilt with claims.build_hits if missing).

Main columns
  row file    n_other_places_city   distinct places named in the text that lie > 60 km from the record's city cell (towns < 40 km apart count once)
              n_other_places        same, but a place also counts as "own" when it is near the record's postcode
              n_sent_other_place / _org / _any (+ share_, any_, _city variants)   sentences about another place / organisation
              n_sent_own_name, share_sent_own_name   sentences naming the record itself
              bed_conflict          two total-bed statements (or one and the capacity cell) differ by 1.5x and 30+ beds
              n_phone_areas         distinct landline area codes (mobiles and directory call-forwarding numbers excluded); n_source_ids
  claim file  sup_other_any / sup_near_other_any   a supporting sentence names another place or organisation / sits within 2 sentences of one
              sup_own_name_clean / sup_near_own_clean   a supporting sentence (name masked) names the record / sits within 2 sentences of one that does
              n_sup_clean, sup_share_of_record   supporting sentences after masking the name, and their share of all sentences in the record
"""
import sys, os, re, difflib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from common import load_facilities, ROOT, OUT
import trust                                   # only for the name-specialty patterns that must be ignored
from claims import SPLIT, ANY

SAME_KM = 40         # two named places closer than this count as one place ("Chinchwad" and "Pune")
FAR_KM = 60          # "another place" = more than this from the record's own city AND own postcode. A district is ~100 km across.
NEAR_SENT = 2        # "next to" = within this many list positions in the same field
I = re.I

# ----------------------------------------------------------------------------------------------- place gazetteer
STATE_ALIAS = {"tamilnadu": "TAMIL NADU", "orissa": "ODISHA", "pondicherry": "PUDUCHERRY", "uttaranchal": "UTTARAKHAND", "uttranchal": "UTTARAKHAND",
               "nct of delhi": "DELHI", "nct delhi": "DELHI", "new delhi": "DELHI", "delhi ncr": "DELHI", "jammu & kashmir": "JAMMU AND KASHMIR",
               "jammu and kashmir": "JAMMU AND KASHMIR", "kashmir": "JAMMU AND KASHMIR", "chattisgarh": "CHHATTISGARH", "telengana": "TELANGANA",
               "uttarpradesh": "UTTAR PRADESH", "madhyapradesh": "MADHYA PRADESH", "andaman and nicobar": "ANDAMAN AND NICOBAR ISLANDS"}
STATE_CODE = {"up": "UTTAR PRADESH", "u p": "UTTAR PRADESH", "mp": "MADHYA PRADESH", "m p": "MADHYA PRADESH", "ts": "TELANGANA", "gj": "GUJARAT", "mh": "MAHARASHTRA",
              "ms": "MAHARASHTRA", "dl": "DELHI", "br": "BIHAR", "cg": "CHHATTISGARH", "u k": "UTTARAKHAND", "nct": "DELHI"}      # used for the address cell only, never in sentences
CITY_ALIAS = {"madras": "chennai", "bombay": "mumbai", "calcutta": "kolkata", "trivandrum": "thiruvananthapuram", "cochin": "kochi", "baroda": "vadodara",
              "poona": "pune", "prayagraj": "allahabad", "vizag": "visakhapatnam", "trichy": "tiruchirappalli", "banaras": "varanasi", "gurugram": "gurgaon",
              "bengaluru": "bangalore", "mysuru": "mysore", "mangaluru": "mangalore", "belagavi": "belgaum", "hubballi": "hubli", "kalaburagi": "gulbarga",
              "tuticorin": "thoothukudi", "calicut": "kozhikode", "secunderabad": "hyderabad", "bhatinda": "bathinda", "simla": "shimla", "panjim": "panaji",
              "chhatrapati sambhajinagar": "aurangabad", "vijaywada": "vijayawada", "pondicherry": "puducherry", "vijayapura": "bijapur",
              "delhi ncr": "delhi", "ncr": "delhi"}
CITY_STATES = {"delhi", "new delhi", "delhi ncr", "chandigarh", "puducherry", "pondicherry"}      # states small enough to be judged by distance, like a city
# place names that are also ordinary words, compass points or very common personal / organisation names
PLACE_STOP = set("""central north south east west new old north east north west south west south east east district north district south district west district
anand sagar krishna gaya dhar pali guna banka bid beed una mau dang tapi narmada mandi mon nadia saran hassan korea basti banda india city town
market colony civil lines main road camp model town gandhi nagar nehru nagar shastri nagar ashok nagar ram nagar medical college cantt fort station
ganga yamuna godavari kaveri sangam bharat hind raja rani bara chota patel sardar shivaji rajendra indira rajiv mahatma nehru ambedkar
kota champa gir sidhi seoni panna rewa satna durg bastar korba mahe diu daman leh doda samba reasi moga nuh jind hapur etah lohit siang
unity hope life care apex star sun moon lotus rose city centre global royal ideal modern national sanjeevani sanjivani jeevan jivan arogya
bishop mission sector block phase ward plot tower plaza complex mall park garden circle square junction cross bridge temple church mosque""".split()) | {
    "north east", "north west", "south west", "south east", "east district", "north district", "south district", "west district", "civil lines",
    "main road", "model town", "gandhi nagar", "nehru nagar", "shastri nagar", "ashok nagar", "ram nagar", "medical college"}
PLACE_KEEP = {"kota", "goa", "agra", "puri", "pune", "durg", "rewa", "satna", "korba", "moga", "jind", "hapur", "leh"}     # real towns worth keeping despite the list above
HONORIFIC = {"dr", "dr.", "shri", "smt", "mr", "mr.", "mrs", "mrs.", "ms", "late", "prof", "prof.", "sri", "shree", "sh", "sh.", "st", "st.", "saint", "lord", "maa", "baba"}
# a place word followed by one of these is part of a name ("Bombay Hospital", "Mysore Road", "Gujarat Ayurved University"), not a location statement
AFTER_PLACE = set("""hospital hospitals clinic clinics medical eye dental heart kidney institute nursing memorial road rd nagar marg street gate chowk colony bazar bazaar
market enclave vihar university college school scan scans diagnostics diagnostic labs lab laboratory pharmacy bank public council board ayurved ayurveda ayurvedic
healthcare health care cancer ortho orthopaedic orthopedic maternity children child ent skin netralaya nethralaya trust foundation society mission tower towers plaza
complex mall club hotel cinema talkies sweets stores store traders enterprises agencies pharma surgicals opticals optical fertility ivf neuro spine diabetes
x-ray imaging pathology test polyclinic dispensary homoeo homeo physiotherapy super multi speciality specialty multispeciality multispecialty pin
panchkarma panchakarma style massage therapy therapies treatment treatments technique techniques medicine medicines""".split())

SCHEME_STATE = {r"aa?rogya ?sri": {"ANDHRA PRADESH", "TELANGANA"}, r"mahatma (?:jyotiba|jyotirao) phule|mjpjay|rajiv gandhi jeevandayee": {"MAHARASHTRA"},
                r"chief minister'?s comprehensive health insurance|cmchis": {"TAMIL NADU"}, r"karunya|\bkasp\b|medisep": {"KERALA"}, r"swasthya sathi": {"WEST BENGAL"},
                r"biju swasthya|\bbsky\b": {"ODISHA"}, r"bhamashah|chiranjeevi|\brghs\b": {"RAJASTHAN"}, r"mukhyamantri amrutam|ma vatsalya|ma yojana": {"GUJARAT"},
                r"yeshasvini|arogya karnataka|suvarna arogya|vajpayee arogya": {"KARNATAKA"}, r"atal amrit": {"ASSAM"}, r"deen ?dayal swasthya seva": {"GOA"},
                r"himcare": {"HIMACHAL PRADESH"}, r"sarbat sehat|bhagat puran singh": {"PUNJAB"}, r"mohalla clinic|govt\.? of nct|government of nct|gnctd|delhi arogya": {"DELHI"},
                r"megha health": {"MEGHALAYA"}, r"atal ayushman uttarakhand": {"UTTARAKHAND"}}
SCHEME_RX = [(re.compile(k, I), v) for k, v in SCHEME_STATE.items()]

# sentence contexts in which another place / organisation is legitimately mentioned by the record's own page
BIO_RX = re.compile(r"\b(?:MBBS|M\.B\.B\.S|M\.?D|M\.?S|DNB|M\.?Ch|D\.?M|FRCS|MRCP|MRCS|BDS|MDS|BAMS|BHMS|DGO|DCH)\b|(?i:\b(?:fellowship|fellow|trained|training (?:at|from|in)|graduat\w*|alumn\w*|residency|internship|completed|studied|degree|worked (?:at|as|in|with)|formerly|previously|served (?:as|at|in)|experience (?:at|in|from)|visiting|born in|native of)\b)")
CATCH_RX = re.compile(r"patients? from|serv(?:es|ing)\b.{0,40}\b(?:districts?|region|areas?|states?|patients|cities|towns)|nearby (?:districts|cities|towns|areas)|neighbou?ring|catchment|across (?:india|the country)|all over|distance from|\bkm\b|kilomet|from across|largest|\bfirst\b|only (?:in|one)|best (?:in|of)|one of the|pioneer|\bserv(?:es|ing)\b|regist(?:ered|ration)|\bROC\b|universit|council|\bboard\b", I)
CHAIN_RX = re.compile(r"\bnetwork (?:includes|operates)\b|\b(?:cent(?:re|er)s|locations|outlets|units)\b.{0,30}\b(?:in|across|at|include[sd]?|located|established)\b|\bclinics are located\b|\blocations? include|\boperates (?:\w+ ){0,4}cent(?:re|er)s?\b|\bmajor (?:indian )?cities\b|\bbranch(?:es)?\b|\b(?:cent(?:re|er)s|locations|hospitals|clinics|units|outlets|presence|offices)\s+(?:in|across|at)\b|\bnetwork of\b|\bchain\b|\bpan[- ]india\b|\bheadquarter|\bhead office|\bregistered office|\bcorporate office", I)
AFFIL_RX = re.compile(r"affiliat|accredit|certified by|quality control|recogni[sz]ed by|approved by|\bunit of\b|venture of|\bpart of\b|managed by|run by|operated by|owned by|under the aegis|sister concern|subsidiary|collaborat|tie[- ]?up|association with|associated with|attached to|partner|founded by|established by|group of|parent", I)
LANDMARK_RX = re.compile(r"\bnear\b|\bnearby\b|opposite|\bopp\b|behind|next to|beside|adjacent|landmark|metres|meters|\bkm\b|in front of", I)
ORG_KEY = {"hospital", "hospitals", "clinic", "clinics", "netralaya", "nethralaya", "polyclinic", "institute", "sanatorium", "infirmary"}
ORG_KEY2 = {("nursing", "home"), ("maternity", "home"), ("medical", "college"), ("medical", "centre"), ("medical", "center"), ("health", "centre"), ("health", "center")}
CONNECT = {"of", "and", "&", "the", "for", "in"}
# words that never identify an organisation: legal forms, generic health words, insurers and web directories that the pages quote
ORG_GENERIC = set("""hospital hospitals clinic clinics centre center centres centers medical health healthcare care nursing home institute institutes research
pvt ltd limited private llp the and of for in at a an dr sri shri shree sree smt st new city life general district civil government govt public charitable trust
memorial mission foundation society super multi speciality specialty specialities multispeciality multispecialty superspeciality polyclinic top best leading
network empanelled empaneled cashless insurance listed star niva bupa hdfc ergo icici lombard bajaj allianz iffco tokio religare manipalcigna cigna aditya birla acko
tata aig reliance sbi oriental united national india indian future generali cholamandalam royal sundaram digit liberty magma kotak medi assist paramount vidal raksha
policybazaar practo justdial hexahealth lybrate medindia latlong sulekha credihealth docindia apollo247 google facebook ayushman bharat pmjay pm-jay cghs echs esic
referral related nearby society corporate tertiary teaching charitable community primary rural urban sub divisional taluk taluka area regional state
ent ivf icu nicu picu opd ipd covid nabh nabl iso jci unicef who sciences science wise dots stoma vitreo american armed forces yeshasvini aarogyasri arogyasri
policyx universal sompo capf ehs tpa ncd mtp tmd pcod pcos icl baby friendly municipal corporation cantonment railway esi phc chc uphc
tamil nadu uttar madhya andhra arunachal himachal pradesh bengal jammu kashmir east west north south navi nagar goverment
monday tuesday wednesday thursday friday saturday sunday brownfield catholic oncofertility obs gyn copd stabilisation stabilization""".split())
LEAK_RX = re.compile("|".join([trust.BROAD] + list(trust.NEG.values()) + list(trust.POS.values())), I)        # name-specialty words: always ignored
BED_RATIO, BED_DIFF = 1.5, 30     # two total-bed statements "contradict" when one is 1.5x the other and at least 30 beds apart
BED_RX = re.compile(r"(\d{1,2},\d{3}|\d{1,4})\s*\+?\s*-?\s*bed(?:ded|s)?\b", I)
BED_UNIT_RX = re.compile(r"\b(?:icu|iccu|nicu|picu|sicu|micu|ccu|hdu|sncu|wards?|emergency|casualty|dialysis|isolation|covid|ventilators?|oxygen|intensive|critical|trauma|burns?|day ?care|recovery|private rooms?|deluxe|cabins?|labou?r|neonatal|observation|triage|rooms?|hostel|college|sanctioned|proposed|planned|expan\w+|upcoming|will|originally|initially|started|began|founded|established|launched|functional|upgrad\w+|under development|historical|formerly|earlier|grew|grown)\b|\bin (?:19|20)\d\d\b", I)
TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9'’.\-]*|[,;:()&/]")
WORD = re.compile(r"[a-z]{3,}")


def nrm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()


def km(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, [la1, lo1, la2, lo2])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return float(6371 * 2 * np.arcsin(np.sqrt(h)))


def load_pin():
    P = pd.concat([pd.read_csv(os.path.join(ROOT, f), dtype=str) for f in ["indiaPincodeDirectory1.csv", "indiaPincodeDirectory2.csv"]]).drop_duplicates()
    P["lat"] = pd.to_numeric(P.latitude, errors="coerce"); P["lon"] = pd.to_numeric(P.longitude, errors="coerce")
    P.loc[~(P.lat.between(6, 37.5) & P.lon.between(68, 97.5)), ["lat", "lon"]] = np.nan
    P["statename"] = P.statename.str.upper().str.strip(); P["district"] = P.district.str.upper().str.strip()
    mode = lambda s: s.mode().iloc[0] if s.notna().any() else np.nan
    pin = P.groupby("pincode").agg(state=("statename", mode), district=("district", mode), lat=("lat", "median"), lon=("lon", "median"))
    dist = P.dropna(subset=["district", "statename"]).groupby(["statename", "district"]).agg(lat=("lat", "median"), lon=("lon", "median"), n=("lat", "size")).reset_index()
    return pin, dist


def build_gazetteer(F, pin, dist):
    """name -> list of (lat, lon, STATE). Sources: PIN-directory districts and states, and the facility table's own city names."""
    states = {s.lower(): s for s in pin.state.dropna().unique()}
    states.update(STATE_ALIAS)
    gaz = collections.defaultdict(list)
    for r in dist.itertuples():
        if np.isnan(r.lat): continue
        name = re.sub(r"\(.*?\)", " ", r.district.lower()); name = nrm(re.sub(r"\b(urban|rural|metro|nagar district|district)\b", " ", name)) if len(name.split()) > 1 else nrm(name)
        if name: gaz[name].append((r.lat, r.lon, r.statename))
    pc = F.address_zipOrPostcode.astype(str).str.replace(r"\D", "", regex=True).str[:6]
    C = pd.DataFrame({"city": F.address_city.map(nrm), "pc": pc}).join(pin, on="pc")
    C = C[(C.city.str.len() >= 3) & C.lat.notna()]
    for city, g in C.groupby("city"):
        if len(g) < 2: continue
        for st, h in g.groupby("state"):
            if len(h) >= 2 and len(h) >= 0.2 * len(g):          # keep each state cluster that is not a stray contaminated row
                gaz[city].append((float(h.lat.median()), float(h.lon.median()), st))
    for a, b in CITY_ALIAS.items():
        if b in gaz and a not in gaz: gaz[a] = list(gaz[b])
        elif a in gaz and b not in gaz: gaz[b] = list(gaz[a])
    for k in list(gaz):
        if (k in PLACE_STOP and k not in PLACE_KEEP) or (k in states and k not in CITY_STATES) or (len(k) < 4 and k not in PLACE_KEEP) or k.isdigit(): del gaz[k]
    return dict(gaz), states


# ----------------------------------------------------------------------------------------------- phones and sources
METRO2 = {"11", "20", "22", "33", "40", "44", "79", "80"}
STD3_678 = set("612 621 631 641 651 657 661 663 671 674 680 712 721 724 731 733 734 744 747 751 755 761 771 788 816 820 821 824 831 832 836 861 863 866 870 877 878 883 884 891".split())


def phone_area(p):
    """Landline area key for an Indian number, or None for mobiles / toll-free / unparseable.
    National numbers are 10 digits. First digit 9 = mobile. First digit 1-5 = landline (2-digit metro code or first 3 digits of the STD code).
    First digit 6-8 is ambiguous: counted as landline only for well-known city codes followed by a subscriber digit 2-6."""
    d = re.sub(r"\D", "", str(p))
    if len(d) == 12 and d.startswith("91"): d = d[2:]
    elif len(d) == 11 and d.startswith("0"): d = d[1:]
    if len(d) != 10 or d[:4] in ("1800", "1860"): return None
    if d[0] in "12345":
        return d[:2] if d[:2] in METRO2 else d[:3]
    if d[0] in "678":
        if d[:2] in ("79", "80") and d[2] in "23456": return d[:2]
        if d[:3] in STD3_678 and d[3] in "23456": return d[:3]
    return None


def phone_prefix(p):
    d = re.sub(r"\D", "", str(p))
    return d[-10:-6] if len(d) >= 10 else ""


def phone_features(F):
    own = F.address_stateOrRegion.map(nrm)
    # Call-forwarding numbers used by web directories (e.g. 07947..., 08048...) look like landlines but belong to no place, and mobile series
    # overlap the Ahmedabad (79) and Bengaluru (80) codes. Learn them from the table: a 4-digit number prefix whose rows are NOT concentrated
    # in the state where its area code is mostly seen is dropped.
    area_state, pre_state = collections.defaultdict(collections.Counter), collections.defaultdict(collections.Counter)
    for L, s_ in zip(F.phone_numbers_l, own):
        if not s_: continue
        for a, pre in {(phone_area(p), phone_prefix(p)) for p in L}:
            if a: area_state[a][s_] += 1; pre_state[pre][s_] += 1
    home = {a: c.most_common(1)[0][0] for a, c in area_state.items()}
    bad = set()
    for pre, c in pre_state.items():
        a = pre[:2] if pre[:2] in METRO2 else pre[:3]; n = sum(c.values()); share = c[home.get(a, "")] / n
        if (n >= 8 and share < 0.5) or (pre[:2] in ("79", "80") and pre[2] != "2" and (n < 8 or share < 0.8)): bad.add(pre)
    areas = F.phone_numbers_l.map(lambda L: sorted({phone_area(p) for p in L if phone_area(p) and phone_prefix(p) not in bad}))
    vote = collections.defaultdict(collections.Counter)          # learn area code -> state from the table itself (rows with exactly one area code)
    for a, s in zip(areas, own):
        if len(a) == 1 and s: vote[a[0]][s] += 1
    a2s = {a: c.most_common(1)[0][0] for a, c in vote.items() if sum(c.values()) >= 3 and c.most_common(1)[0][1] >= 0.6 * sum(c.values())}
    out = pd.DataFrame({"uid": F.unique_id})
    out["n_phone_areas"] = areas.map(len).values
    out["phone_areas_3plus"] = (out.n_phone_areas >= 3).astype(int)
    out["n_phone_states"] = areas.map(lambda a: len({a2s[x] for x in a if x in a2s})).values
    out["n_phone_areas_other_state"] = [sum(1 for x in a if x in a2s and s and a2s[x] != s) for a, s in zip(areas, own)]
    out["n_phones_distinct"] = F.phone_numbers_l.map(lambda L: len({re.sub(r"\D", "", x)[-10:] for x in L})).values
    out["n_source_ids"] = F.source_ids_l.map(lambda L: len(set(L))).values
    out["source_ids_6plus"] = (out.n_source_ids >= 6).astype(int)
    return out, areas, a2s, sorted(bad)


# ----------------------------------------------------------------------------------------------- sentence attribution
def units_of(r):
    """Sentences of one record: every list item of procedure / equipment / capability, and the description split into sentences."""
    U = []
    for fld in ["procedure", "equipment", "capability"]:
        U += [(fld, i, t.strip()) for i, t in enumerate(getattr(r, fld + "_l")) if t and t.strip()]
    U += [("description", i, s.strip()) for i, s in enumerate(x for x in SPLIT.split(r.description) if x and len(x.strip()) >= 3)]
    return U


def clean_tok(t):
    return t.strip(".'’-").lower()


class Attributor:
    def __init__(self, F, gaz, states, pin):
        self.gaz, self.states, self.pin = gaz, states, pin
        self.maxn = max(len(k.split()) for k in list(gaz) + list(states))
        low, cap = collections.Counter(), collections.Counter()      # how often a word is written in lower case inside sentences:
        for r in F.itertuples():                                     # proper names almost never are, ordinary words often are
            for _, _, t in units_of(r):
                for j, w in enumerate(TOK.findall(t)):
                    if j == 0 or not w[0].isalpha(): continue
                    (cap if w[0].isupper() else low)[clean_tok(w)] += 1
        self.common = {w for w in low if low[w] >= 5 and low[w] >= 0.1 * (low[w] + cap[w])}
        self.in_names = {w for nm in F.name for w in re.findall(r"[a-z]+", nm.lower())}      # words seen in any facility name of the table
        self._fz = {}

    def is_name_word(self, w, raw=""):
        if raw.isupper() and len(raw) <= 5 and w not in self.in_names: return False       # stray acronym (OPD, TPA, NABH ...) rather than a hospital's short name
        return len(w) >= 3 and w.isalpha() and w not in ORG_GENERIC and w not in self.common and not LEAK_RX.search(w) and w not in self.gaz and w not in self.states

    def same(self, a, b):
        if a == b: return True
        k = (a, b)
        if k not in self._fz:
            self._fz[k] = (min(len(a), len(b)) >= 4 and (a.startswith(b) or b.startswith(a))) or difflib.SequenceMatcher(None, a, b).ratio() >= 0.82
        return self._fz[k]

    def profile(self, r):
        """The record's own identity: name words (specialty words removed), own city / state / postcode place."""
        raw = [w for w in re.findall(r"[a-z]+", r.name.lower()) if len(w) >= 3]
        loose = [w for w in raw if w not in ORG_GENERIC and not LEAK_RX.search(w)]
        own_words = set(loose); core = [w for w in loose if w not in self.gaz and w not in self.states][:2]
        addr = nrm(" ".join(str(getattr(r, c)) for c in ["address_line1", "address_line2", "address_line3"] if isinstance(getattr(r, c), str)))
        name_n = nrm(r.name)
        st = nrm(r.address_stateOrRegion); own_states = set(); refs = []
        if st in self.states: own_states.add(self.states[st])
        elif st in STATE_CODE: own_states.add(STATE_CODE[st])
        elif st in self.gaz: own_states |= {c[2] for c in self.gaz[st]}; refs += [(c[0], c[1]) for c in self.gaz[st]]
        addr_states = set(own_states); city_refs = []
        pc = re.sub(r"\D", "", str(r.address_zipOrPostcode))[:6]
        if pc in self.pin.index:
            p = self.pin.loc[pc]
            if isinstance(p.state, str): own_states.add(p.state)
            if not np.isnan(p.lat): refs.append((p.lat, p.lon))
        city = nrm(r.address_city); city = CITY_ALIAS.get(city, city) if city not in self.gaz else city
        if city in self.gaz:
            cands = [c for c in self.gaz[city] if not own_states or c[2] in own_states] or self.gaz[city]
            refs += [(c[0], c[1]) for c in cands]; own_states |= {c[2] for c in cands} if not own_states else set()
            cc = [c for c in self.gaz[city] if not addr_states or c[2] in addr_states] or self.gaz[city]
            city_refs = [(c[0], c[1]) for c in cc]; addr_states = addr_states or {c[2] for c in cc}
        elif city in self.states: own_states.add(self.states[city]); addr_states.add(self.states[city])
        # "strict" view = judged against the city and state cells only (what a reader sees); falls back to the lenient view when the city is unknown
        strict = dict(refs=city_refs or refs, own_states=addr_states or own_states, cache={})
        return dict(own_words=own_words, core=core, addr=" " + addr + " ", name_n=" " + name_n + " ", own_states=own_states, refs=refs, city=nrm(r.address_city), cache={}, strict=strict)

    def place_class(self, g, P, V=None):
        """'own' / 'other' / None for a gazetteer or state name seen in a sentence of record P. V = P (lenient: city + postcode) or P['strict'] (city only)."""
        V = V or P; c = V["cache"]
        if g in c: return c[g]
        res = None
        if g == P["city"] or f" {g} " in P["name_n"] or f" {g} " in P["addr"]: res = ("own", None, None, None)
        elif g in self.states and not (g in self.gaz and V["refs"]):
            s = self.states[g]
            if V["own_states"]: res = ("own", s, None, None) if s in V["own_states"] else ("other", s, None, None)
        else:
            cands = self.gaz[g]
            if V["refs"]:
                d, s, la, lo = min((km(a[0], a[1], b[0], b[1]), a[2], a[0], a[1]) for a in cands for b in V["refs"])
                res = ("own", s, la, lo) if d <= FAR_KM else ("other", s, la, lo)
            elif V["own_states"]:
                res = ("own", cands[0][2], None, None) if any(a[2] in V["own_states"] for a in cands) else ("other", cands[0][2], cands[0][0], cands[0][1])
        c[g] = res
        return res

    def sentence(self, t, P):
        toks = TOK.findall(t); n = len(toks); low = [clean_tok(w) for w in toks]
        isw = [w[0].isalnum() for w in toks]
        bio, catch, chain = bool(BIO_RX.search(t)), bool(CATCH_RX.search(t)), bool(CHAIN_RX.search(t))
        # ---- places
        oplace, ostate, own_place, oplace_city = {}, set(), False, {}
        i = 0
        while i < n:
            hit = None
            if isw[i] and toks[i][0].isupper():
                for k in range(min(self.maxn, n - i), 0, -1):
                    if not all(isw[i:i + k]): continue
                    g = " ".join(low[i:i + k])
                    if g in self.gaz or g in self.states: hit = (g, k); break
            if not hit: i += 1; continue
            g, k = hit
            prev = low[i - 1] if i > 0 else ""; nxt = low[i + k] if i + k < n else ""
            if prev not in HONORIFIC and nxt not in AFTER_PLACE:
                pcl = self.place_class(g, P)
                if pcl:
                    if pcl[0] == "own": own_place = True
                    else: oplace[g] = pcl[1:]; ostate.add(pcl[1])
                pcs = self.place_class(g, P, P["strict"])
                if pcs and pcs[0] == "other": oplace_city[g] = pcs[1:]
            i += k
        for rx, sts in SCHEME_RX:                                     # state-run schemes are tied to a place
            if P["own_states"] and rx.search(t) and not (sts & P["own_states"]):
                oplace["scheme:" + "/".join(sorted(sts))] = oplace_city["scheme:" + "/".join(sorted(sts))] = (sorted(sts)[0], None, None); ostate |= sts
        if bio or catch or chain or AFFIL_RX.search(t): oplace, ostate, oplace_city = {}, set(), {}
        # ---- organisations
        oorg, own_name = set(), False
        skip_org = bio or bool(AFFIL_RX.search(t)) or bool(LANDMARK_RX.search(t)) or chain
        for j in range(n):
            if not isw[j]: continue
            two = j + 1 < n and (low[j], low[j + 1]) in ORG_KEY2
            if not (low[j] in ORG_KEY or two): continue
            k = j - 1; phrase = []
            while k >= 0 and len(phrase) < 6 and isw[k] and (toks[k][0].isupper() or low[k] in CONNECT):
                phrase.append((low[k], toks[k].strip(".'’-"))); k -= 1
            words = [(w, raw) for w, raw in phrase if w.isalpha() and len(w) >= 3]
            if any(self.same(w, o) for w, _ in words for o in P["own_words"]): own_name = True; continue
            names = [w for w, raw in words if self.is_name_word(w, raw)]
            if names and P["own_words"] and not skip_org: oorg.add(" ".join(reversed(names)))
        if not own_name and P["core"]:
            caps = {low[j] for j in range(n) if isw[j] and toks[j][0].isupper()}
            own_name = all(w in caps for w in P["core"])
        # ---- total bed statements
        beds = None
        if not BED_UNIT_RX.search(t):
            m = BED_RX.search(t)
            if m:
                v = int(m.group(1).replace(",", ""))
                if v >= 5: beds = v
        return dict(oplace=oplace, ostate=ostate, oorg=oorg, own_place=own_place, own_name=own_name, beds=beds, oplace_city=oplace_city)


def n_places(info):
    """Distinct places among {name: (state, lat, lon)}: names closer than SAME_KM are one place; a bare state counts only if no named town lies in it."""
    reps, seen = [], set()
    for st, la, lo in info.values():
        if la is None: continue
        seen.add(st)
        if not any(km(la, lo, a, b) <= SAME_KM for a, b in reps): reps.append((la, lo))
    return len(reps) + len({st for st, la, lo in info.values() if la is None and st not in seen})


def bed_conflict(vals, cap):
    v = sorted(set(vals)); txt = int(len(v) >= 2 and v[-1] >= BED_RATIO * v[0] and v[-1] - v[0] >= BED_DIFF)
    capc = int(bool(v) and cap == cap and cap >= 1 and any(max(x, cap) >= BED_RATIO * min(x, cap) and abs(x - cap) >= BED_DIFF for x in v))
    return txt, capc


def main(debug=None):
    F = load_facilities()
    pin, dist = load_pin()
    gaz, states = build_gazetteer(F, pin, dist)
    A = Attributor(F, gaz, states, pin)
    hp = os.path.join(OUT, "hits.pkl")
    if os.path.exists(hp): H = pd.read_pickle(hp)
    else:
        from claims import build_hits
        H = build_hits(F)
    hits_by_uid = {u: g for u, g in H.groupby("uid")}
    rows, claims, dbg = [], [], []
    for r in F.itertuples():
        P = A.profile(r); U = units_of(r)
        S = [A.sentence(t, P) for _, _, t in U]
        n = len(U)
        op = np.array([bool(s["oplace"]) for s in S], bool); oo = np.array([bool(s["oorg"]) for s in S], bool)
        opc = np.array([bool(s["oplace_city"]) for s in S], bool); othc = opc | oo
        oth = op | oo; ownn = np.array([s["own_name"] for s in S], bool); ownp = np.array([s["own_place"] for s in S], bool)
        places, places_c = {}, {}
        for s in S: places.update(s["oplace"]); places_c.update(s["oplace_city"])
        ostates = set().union(*[s["ostate"] for s in S]) if S else set()
        orgs = set().union(*[s["oorg"] for s in S]) if S else set()
        beds = [s["beds"] for s in S if s["beds"]]; btxt, bcap = bed_conflict(beds, r.capacity_n)
        d = max(n, 1)
        rows.append(dict(uid=r.unique_id, n_sent=n,
                         n_sent_other_place=int(op.sum()), n_sent_other_org=int(oo.sum()), n_sent_other_any=int(oth.sum()),
                         share_sent_other_place=op.sum() / d, share_sent_other_org=oo.sum() / d, share_sent_other_any=oth.sum() / d,
                         any_other_place=int(op.any()), any_other_org=int(oo.any()), any_other=int(oth.any()), other_any_2plus=int(oth.sum() >= 2),
                         n_other_places=n_places(places), n_other_states=len(ostates), n_other_orgs=len(orgs), other_places_2plus=int(n_places(places) >= 2),
                         n_sent_other_place_city=int(opc.sum()), share_sent_other_place_city=opc.sum() / d, n_sent_other_any_city=int(othc.sum()),
                         share_sent_other_any_city=othc.sum() / d, other_any_city_2plus=int(othc.sum() >= 2), other_any_city_3plus=int(othc.sum() >= 3),
                         n_other_places_city=n_places(places_c), other_places_city_2plus=int(n_places(places_c) >= 2),
                         n_sent_own_name=int(ownn.sum()), share_sent_own_name=ownn.sum() / d, n_sent_own_place=int(ownp.sum()),
                         other_minus_own=int(oth.sum()) - int((ownn | ownp).sum()),
                         other_vs_own_share=oth.sum() / max(oth.sum() + (ownn | ownp).sum(), 1),
                         n_bed_totals=len(set(beds)), bed_conflict_text=btxt, bed_conflict_capacity=bcap, bed_conflict=int(btxt or bcap),
                         name_has_words=int(bool(P["own_words"])), place_known=int(bool(P["refs"] or P["own_states"]))))
        if debug is not None:
            dbg += [(r.unique_id, f, i, t, "|".join(sorted(s["oplace"])), "|".join(sorted(s["oorg"])), s["own_name"], s["own_place"], s["beds"], "|".join(sorted(s["oplace_city"]))) for (f, i, t), s in zip(U, S)]
        h = hits_by_uid.get(r.unique_id)
        if h is None: continue
        # position of every sentence inside its field, and distance to the nearest "other" / "own" sentence of that field
        byf = collections.defaultdict(list)
        for k, (f, i, t) in enumerate(U): byf[f].append(k)
        dist_o, dist_w, fshare, dist_c = np.full(n, 99.0), np.full(n, 99.0), np.zeros(n), np.full(n, 99.0)
        own_anchor = ownn | ownp
        for f, ks in byf.items():
            ks = np.array(ks); o = np.where(oth[ks])[0]; w = np.where(own_anchor[ks])[0]; pos = np.arange(len(ks))
            if len(o): dist_o[ks] = np.abs(pos[:, None] - o[None, :]).min(1)
            oc = np.where(othc[ks])[0]
            if len(oc): dist_c[ks] = np.abs(pos[:, None] - oc[None, :]).min(1)
            if len(w): dist_w[ks] = np.abs(pos[:, None] - w[None, :]).min(1)
            fshare[ks] = oth[ks].mean()
        # A sentence that merely repeats the facility's name ("X Kidney Hospital is listed in ...") matches the service keyword through the NAME.
        # Such name-induced support is circular (and would leak the name-based silver label), so "clean" features mask the name words first.
        nw = sorted({w for w in re.findall(r"[a-z]+", r.name.lower()) if len(w) >= 3 and w not in ORG_GENERIC}, key=len, reverse=True)
        mask = re.compile(r"\b(?:" + "|".join(map(re.escape, nw)) + r")(?:'?s)?\b", I) if nw else None
        for svc, g in h.groupby("service"):
            idx, clean = [], set()
            for f, seg in zip(g.field, g.seg):
                seg = seg.strip(); k = next((k for k in byf.get(f, []) if seg in U[k][2]), None)
                if k is None and f == "description": k = next((k for k in byf.get(f, []) if U[k][2][:40] in seg or seg[:40] in U[k][2]), None)
                if k is not None:
                    idx.append(k)
                    if mask is None or ANY[svc].search(mask.sub(" ", seg)): clean.add(k)
            if not idx:
                claims.append(dict(uid=r.unique_id, service=svc, sup_found=0)); continue
            idx = np.array(sorted(set(idx))); do, dw, dc = dist_o[idx], dist_w[idx], dist_c[idx]
            cl = np.array(sorted(clean), int); isclean = np.isin(idx, cl)
            closer = (do < dw) & (do <= 5)
            claims.append(dict(uid=r.unique_id, service=svc, sup_found=1, n_sup=len(idx),
                               sup_other_any=int(oth[idx].any()), sup_other_share=float(oth[idx].mean()), sup_other_all=int(oth[idx].all()),
                               sup_other_place=int(op[idx].any()), sup_other_org=int(oo[idx].any()),
                               sup_near_other_any=int((do <= NEAR_SENT).any()), sup_near_other_share=float((do <= NEAR_SENT).mean()),
                               sup_near_other_all=int((do <= NEAR_SENT).all()),
                               sup_closeness_other=float((1 / (1 + do)).max()), sup_closeness_other_mean=float((1 / (1 + do)).mean()),
                               sup_other_closer_any=int(closer.any()), sup_other_closer_share=float(closer.mean()),
                               sup_own_name=int(ownn[idx].any()), sup_near_own_any=int((dw <= NEAR_SENT).any()), sup_near_own_share=float((dw <= NEAR_SENT).mean()),
                               n_sup_clean=len(cl), sup_share_of_record=len(cl) / max(n, 1), sup_name_only=int(len(cl) == 0), share_sup_name_induced=float(1 - isclean.mean()),
                               sup_own_name_clean=int(ownn[cl].any()) if len(cl) else 0, sup_near_own_clean=int((dist_w[cl] <= NEAR_SENT).any()) if len(cl) else 0,
                               sup_other_any_clean=int(oth[cl].any()) if len(cl) else 0, sup_near_other_clean=int((dist_o[cl] <= NEAR_SENT).any()) if len(cl) else 0,
                               sup_field_other_share=float(fshare[idx].mean()),
                               sup_other_any_city=int(othc[idx].any()), sup_near_other_any_city=int((dc <= NEAR_SENT).any()), sup_closeness_other_city=float((1 / (1 + dc)).max()),
                               sup_other_and_row2=int(oth[idx].any() or ((do <= NEAR_SENT).any() and oth.sum() >= 2))))
    R = pd.DataFrame(rows)
    ph, areas, a2s, bad_pre = phone_features(F)
    R = R.merge(ph, on="uid")
    Cl = pd.DataFrame(claims).fillna(0)
    Cl = Cl.merge(R[["uid", "share_sent_other_any", "n_other_places"]].rename(columns={"share_sent_other_any": "row_share_other", "n_other_places": "row_n_other_places"}), on="uid")
    LEAKY = ["n_sup", "sup_own_name", "sup_near_own_any", "sup_near_own_share", "sup_name_only", "share_sup_name_induced"]      # see module docstring
    R.round(4).to_csv(os.path.join(OUT, "feat_attribution_row.csv"), index=False)
    Cl.drop(columns=LEAKY).round(4).to_csv(os.path.join(OUT, "feat_attribution_claim.csv"), index=False)
    print(f"facilities {len(R)} | sentences {int(R.n_sent.sum())} | gazetteer names {len(gaz)} | claims {len(Cl)} (supporting sentence located for {int(Cl.sup_found.sum())})")
    print(f"rows with a sentence about another place {int(R.any_other_place.sum())} | another organisation {int(R.any_other_org.sum())} | either {int(R.any_other.sum())} | 2+ such sentences {int(R.other_any_2plus.sum())}")
    print(f"rows with bed-count conflict {int(R.bed_conflict.sum())} | 3+ landline area codes {int(R.phone_areas_3plus.sum())} | 6+ source ids {int(R.source_ids_6plus.sum())}")
    print(f"claims whose supporting sentence names another place/organisation {int(Cl.sup_other_any.sum())} | or sits within {NEAR_SENT} sentences of one {int(Cl.sup_near_other_any.sum())}")
    print(f"claims supported ONLY by sentences that repeat the facility's own name {int(Cl.sup_name_only.sum())} | claims with at least one such sentence {int((Cl.share_sup_name_induced > 0).sum())}")
    if debug is not None:
        os.makedirs(debug, exist_ok=True)
        Cl.rename(columns={c: "leaky_" + c for c in LEAKY}).round(4).to_csv(os.path.join(debug, "feat_attribution_claim_with_leaky.csv"), index=False)
        pd.DataFrame(dbg, columns=["uid", "field", "i", "text", "oplace", "oorg", "own_name", "own_place", "beds", "oplace_city"]).to_pickle(os.path.join(debug, "attr_sentences.pkl"))
        pd.Series({k: str(v) for k, v in gaz.items()}).to_csv(os.path.join(debug, "attr_gazetteer.csv"))
        pd.DataFrame({"uid": F.unique_id, "areas": areas.map("|".join)}).to_csv(os.path.join(debug, "attr_phone_areas.csv"), index=False)
        pd.Series(a2s).to_csv(os.path.join(debug, "attr_area_state.csv")); open(os.path.join(debug, "attr_bad_prefix.txt"), "w").write(" ".join(bad_pre))


if __name__ == "__main__":
    main(sys.argv[sys.argv.index("--debug") + 1] if "--debug" in sys.argv else None)
