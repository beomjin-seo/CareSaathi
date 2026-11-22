"""Location agreement, rebuilt from raw data only (facilities.csv + the two India Post PIN directory files).

Three independent location signals per facility:
    L  coordinates          -> nearest post offices (7-nearest majority for state and district)
    P  postcode             -> PIN lookup (robust centre, radius, state, district)
    C  stated city / state  -> a place found by name (other facilities stating the same city, or post offices
                               and districts carrying that name inside the stated state)
Two signals "agree" when they are within a tolerance (see AGREE_* below) or name the same district.

Outputs
    pipeline/out/pin_lookup.csv   one row per PIN
    pipeline/out/location.csv     one row per facility (uid) with best coordinates, class, distances and feature columns

Nothing here reads the facility name, facilityTypeId, specialties or any research/data_work table.
Run:  python -I pipeline/location.py
"""
import sys, os, re, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, pandas as pd
from sklearn.neighbors import BallTree
from common import ROOT, OUT, load_facilities, haversine

R_EARTH = 6371.0
BOX = dict(la0=6.0, la1=37.5, lo0=68.0, lo1=97.5)     # India bounding box
SHARED_PINS = 3          # an exact coordinate pair used by this many different PINs is a placeholder, not a location
K_STATE = 7              # nearest post offices used for the state / district vote
AGREE_LP_NEAR = 10.0     # coordinates within this many km of ANY post office of the stated PIN -> agree
AGREE_LP_CENTRE = 10.0   # or within PIN radius + this many km of the PIN centre
AGREE_CITY = 15.0        # slack added to the city radius (and the PIN radius) when comparing with the city
NEIGHBOUR_MIN = 2         # of the 10 nearest post offices from other PINs, this many must share the first 3 PIN digits
FAR_KM = 100.0           # "different part of the country" threshold used for the plain-language flag

STATES = ["ANDAMAN AND NICOBAR ISLANDS", "ANDHRA PRADESH", "ARUNACHAL PRADESH", "ASSAM", "BIHAR", "CHANDIGARH", "CHHATTISGARH", "DELHI", "GOA",
          "GUJARAT", "HARYANA", "HIMACHAL PRADESH", "JAMMU AND KASHMIR", "JHARKHAND", "KARNATAKA", "KERALA", "LADAKH", "LAKSHADWEEP",
          "MADHYA PRADESH", "MAHARASHTRA", "MANIPUR", "MEGHALAYA", "MIZORAM", "NAGALAND", "ODISHA", "PUDUCHERRY", "PUNJAB", "RAJASTHAN", "SIKKIM",
          "TAMIL NADU", "TELANGANA", "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "TRIPURA", "UTTAR PRADESH", "UTTARAKHAND", "WEST BENGAL"]
STATE_ALIAS = {"tamilnadu": "TAMIL NADU", "tn": "TAMIL NADU", "orissa": "ODISHA", "up": "UTTAR PRADESH", "uttarpradesh": "UTTAR PRADESH", "uttaranchal": "UTTARAKHAND",
               "uttranchal": "UTTARAKHAND", "uk": "UTTARAKHAND", "pondicherry": "PUDUCHERRY", "ut of puducherry": "PUDUCHERRY", "nct of delhi": "DELHI", "nct delhi": "DELHI",
               "nct": "DELHI", "new delhi": "DELHI", "dl": "DELHI", "west delhi": "DELHI", "east delhi": "DELHI",
               "south delhi": "DELHI", "north west delhi": "DELHI", "south east delhi area": "DELHI", "jammu kashmir": "JAMMU AND KASHMIR", "jk": "JAMMU AND KASHMIR",
               "j k": "JAMMU AND KASHMIR", "kashmir": "JAMMU AND KASHMIR", "srinagar kashmir": "JAMMU AND KASHMIR", "jammu": "JAMMU AND KASHMIR", "chattisgarh": "CHHATTISGARH",
               "cg": "CHHATTISGARH", "telengana": "TELANGANA", "ts": "TELANGANA", "tg": "TELANGANA", "mh": "MAHARASHTRA", "ms": "MAHARASHTRA", "gj": "GUJARAT", "mp": "MADHYA PRADESH",
               "madhyapradesh": "MADHYA PRADESH", "madhya": "MADHYA PRADESH", "br": "BIHAR", "ap": "ANDHRA PRADESH", "wb": "WEST BENGAL", "ka": "KARNATAKA", "kl": "KERALA",
               "hr": "HARYANA", "pb": "PUNJAB", "punjab region": "PUNJAB", "rj": "RAJASTHAN", "hp": "HIMACHAL PRADESH", "jh": "JHARKHAND", "chandigarh ut": "CHANDIGARH",
               "daman and diu": "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "dadra and nagar haveli and daman and diu": "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
               "dadra nagar haveli daman diu": "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "dadra and nagar haveli": "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU",
               "andaman and nicobar": "ANDAMAN AND NICOBAR ISLANDS", "andaman nicobar islands": "ANDAMAN AND NICOBAR ISLANDS"}
AMBIGUOUS_STATE = {"delhi ncr", "ncr delhi", "delhi ncr region", "ncr", "central india", "ut", "india"}     # the capital region spans Delhi, Haryana and Uttar Pradesh
# old / alternative spellings of places, applied to city strings, district names and post office names alike
PLACE_ALIAS = {"bangalore": "bengaluru", "bombay": "mumbai", "calcutta": "kolkata", "madras": "chennai", "gurgaon": "gurugram", "trivandrum": "thiruvananthapuram",
               "cochin": "kochi", "baroda": "vadodara", "mysore": "mysuru", "mangalore": "mangaluru", "belgaum": "belagavi", "pondicherry": "puducherry",
               "allahabad": "prayagraj", "vizag": "visakhapatnam", "vishakhapatnam": "visakhapatnam", "calicut": "kozhikode", "trichy": "tiruchirappalli",
               "tiruchirapalli": "tiruchirappalli", "tiruchy": "tiruchirappalli", "hubli": "hubballi", "gulbarga": "kalaburagi", "bellary": "ballari", "shimoga": "shivamogga",
               "tumkur": "tumakuru", "bijapur": "vijayapura", "poona": "pune", "benares": "varanasi", "banaras": "varanasi", "new delhi": "delhi", "ahmadabad": "ahmedabad",
               "trichur": "thrissur", "quilon": "kollam", "alleppey": "alappuzha", "palghat": "palakkad", "cannanore": "kannur", "tuticorin": "thoothukudi",
               "ooty": "udhagamandalam", "kanpur nagar": "kanpur", "bhubaneshwar": "bhubaneswar", "panjim": "panaji", "simla": "shimla", "faizabad": "ayodhya",
               "mohali": "sas nagar", "sahibzada ajit singh nagar": "sas nagar", "s a s nagar": "sas nagar", "noida": "gautam buddha nagar", "kochi": "ernakulam",
               "ernakulam": "ernakulam", "vizianagaram": "vizianagaram", "rajahmundry": "rajamahendravaram", "bezawada": "vijayawada", "mehsana": "mahesana", "north cachar hills": "dima hasao", "hoogly": "hooghly", "kutch": "kachchh"}
OFFICE_SUFFIX = re.compile(r"\s*\b(b\.?\s?o\.?|s\.?\s?o\.?|h\.?\s?o\.?|g\.?\s?p\.?\s?o\.?|p\.?\s?o\.?|h\.?\s?q\.?|ndc|edbo|ed|rs|r\.s\.?)\s*$", re.I)
TAIL_WORDS = re.compile(r"\s+(east|west|north|south|central|cantt|cant|cantonment|junction|jn|road|rural|urban|extension|extn|camp)$")
DROP_WORDS = re.compile(r"\b(district|dist|distt|city|town|taluk|taluka|tehsil|mandal|post)\b")


def nplace(s):
    """Normalised place key: lower case, letters only, generic words dropped, old spellings mapped."""
    s = re.sub(r"\(.*?\)", " ", str(s).lower())
    s = re.sub(r"[^a-z ]", " ", s.replace("-", " ").replace(".", " "))
    s = re.sub(r"\s+", " ", DROP_WORDS.sub(" ", s)).strip()
    return PLACE_ALIAS.get(s, s)


def hav(la1, lo1, la2, lo2):
    return haversine(np.asarray(la1, float), np.asarray(lo1, float), np.asarray(la2, float), np.asarray(lo2, float))


def robust_centre(la, lo, floor_km=20.0):
    """Median centre after dropping points far from a first median (further than max(floor, 4 x median distance))."""
    cla, clo = np.median(la), np.median(lo)
    d = hav(la, lo, cla, clo)
    keep = d <= max(floor_km, 4 * np.median(d))
    cla, clo = np.median(la[keep]), np.median(lo[keep])
    return cla, clo, keep, hav(la, lo, cla, clo)


# ---------------------------------------------------------------- 1. PIN lookup
def load_post_offices():
    d = pd.concat([pd.read_csv(os.path.join(ROOT, f), dtype=str, keep_default_na=False) for f in ("indiaPincodeDirectory1.csv", "indiaPincodeDirectory2.csv")], ignore_index=True)
    n_raw = len(d)
    d = d.drop_duplicates().reset_index(drop=True)
    for c in ("district", "statename"):
        d[c] = d[c].str.strip().str.upper().replace({"NA": "", "NAN": ""})
    la, lo = pd.to_numeric(d.latitude, errors="coerce"), pd.to_numeric(d.longitude, errors="coerce")
    inbox = la.between(BOX["la0"], BOX["la1"]) & lo.between(BOX["lo0"], BOX["lo1"])
    swapped = ~inbox & lo.between(BOX["la0"], BOX["la1"]) & la.between(BOX["lo0"], BOX["lo1"])     # latitude and longitude typed the wrong way round
    la2, lo2 = la.where(~swapped, lo), lo.where(~swapped, la)
    d["la"], d["lo"] = la2, lo2
    d["has_raw"] = la.notna() & lo.notna()
    d["ok"] = d.la.between(BOX["la0"], BOX["la1"]) & d.lo.between(BOX["lo0"], BOX["lo1"])
    d["swapped"] = swapped
    # placeholder coordinates (a division or district default, not a location):
    #   the very same point reused by several PINs, or one precise latitude / longitude value reused by 10+ PINs
    key = d.la.round(4).astype(str) + "," + d.lo.round(4).astype(str)
    npin = d[d.ok].groupby(key[d.ok]).pincode.nunique()
    shared = d.ok & key.map(npin).fillna(0).ge(SHARED_PINS)
    for ax in ("la", "lo"):
        v = d[ax].round(6)
        n_ax = v.map(d[d.ok].groupby(v[d.ok]).pincode.nunique()).fillna(0)
        precise = (v * 1000 - (v * 1000).round()).abs() > 1e-6          # more than 3 decimals, so a repeat is not a rounding coincidence
        shared |= d.ok & ((precise & n_ax.ge(10)) | n_ax.ge(25))
    d["shared"] = shared
    # state box test: a post office must lie inside the lat / lon range of the state on its own label
    # (10th to 90th percentile of that state's post offices, widened by half that range or 1 degree; skipped for the scattered union territories)
    lab = d[d.ok & (d.statename != "")]
    q = lab.groupby("statename")[["la", "lo"]].quantile([0.1, 0.9]).unstack()
    in_box = pd.Series(True, index=d.index)
    for ax in ("la", "lo"):
        lo_, hi_ = d.statename.map(q[(ax, 0.1)]), d.statename.map(q[(ax, 0.9)])
        m = np.maximum(1.0, 0.5 * (hi_ - lo_))
        in_box &= ~((d[ax] < lo_ - m) | (d[ax] > hi_ + m))
    in_box |= d.statename.isin(["PUDUCHERRY", "THE DADRA AND NAGAR HAVELI AND DAMAN AND DIU", "ANDAMAN AND NICOBAR ISLANDS", "LAKSHADWEEP", ""])
    d["in_state_box"] = d.ok & in_box
    # district box test, same idea one level down (districts with 20+ located post offices; margin half the range or 0.25 degree, about 28 km).
    # It removes systematic conversion errors that push a whole town's offices 100 km away, where they would otherwise support each other.
    lab = d[d.in_state_box & (d.district != "") & (d.statename != "")]
    dk = d.statename + "|" + d.district
    g = lab.groupby(dk[lab.index])
    q = g[["la", "lo"]].quantile([0.1, 0.9]).unstack(); big = g.size() >= 20
    in_dbox = pd.Series(True, index=d.index)
    for ax in ("la", "lo"):
        lo_, hi_ = dk.map(q[(ax, 0.1)][big]), dk.map(q[(ax, 0.9)][big])
        m = np.maximum(0.25, 0.5 * (hi_ - lo_))
        in_dbox &= ~((d[ax] < lo_ - m) | (d[ax] > hi_ + m))
    d["in_district_box"] = d.in_state_box & in_dbox
    # neighbour test: PIN numbers are handed out area by area, so a post office should have neighbours from its own 3-digit postal area.
    # Among the 10 nearest post offices that belong to OTHER PINs, at least 2 must share the first 3 digits; if not, the point sits in the wrong area.
    d["p3"] = d.pincode.str[:3]
    ref = d[d.in_district_box].drop_duplicates(["pincode", "la", "lo"])
    xy = np.radians(ref[["la", "lo"]].values)
    _, idx = BallTree(xy, metric="haversine").query(xy, k=min(81, len(ref)))
    pin, p3 = ref.pincode.to_numpy(dtype=object), ref.p3.to_numpy(dtype=object)
    other = pin[idx[:, 1:]] != pin[:, None]
    first10 = other & (np.cumsum(other, axis=1) <= 10)
    n_same = ((p3[idx[:, 1:]] == p3[:, None]) & first10).sum(1)
    ref = ref.assign(sup=(first10.sum(1) == 0) | (n_same >= NEIGHBOUR_MIN))
    d = d.merge(ref[["pincode", "la", "lo", "sup"]], on=["pincode", "la", "lo"], how="left")
    d["supported"] = d.in_district_box & d["sup"].fillna(False).astype(bool)
    d["clean"] = d.ok & ~d.shared & d.supported
    stats = dict(rows_raw=n_raw, rows_distinct=len(d), no_coord=int((~d.has_raw).sum()), swapped_fixed=int(swapped.sum()), out_of_india=int((d.has_raw & ~d.ok).sum()),
                 placeholder=int(d.shared.sum()), outside_own_state=int((d.ok & ~d.in_state_box).sum()), outside_own_district=int((d.in_state_box & ~d.in_district_box).sum()), no_neighbour_from_own_postal_area=int((d.in_district_box & ~d.supported).sum()), clean=int(d.clean.sum()))
    return d, stats


def build_pin_lookup(d):
    rows = []
    lab = d[d.statename != ""]
    st_mode = lab.groupby("pincode").statename.agg(lambda s: s.value_counts().index[0])
    st_all = lab.groupby("pincode").statename.agg(lambda s: "|".join(sorted(set(s))))
    di_mode = lab[lab.district != ""].groupby("pincode").district.agg(lambda s: s.value_counts().index[0])
    di_all = lab[lab.district != ""].groupby("pincode").district.agg(lambda s: "|".join(sorted(set(s))))
    n_off = d.groupby("pincode").size(); n_raw = d[d.has_raw].groupby("pincode").size()
    pts = {}
    for pinc, g in d[d.clean].groupby("pincode"):
        la, lo = g.la.values, g.lo.values
        # the sub / head offices mark the town the PIN is named after; branch offices are villages around it and are more often mis-placed
        core = np.array(g.officetype.isin(["PO", "HO"]), dtype=bool)
        if not core.any(): core[:] = True
        cla, clo, kc, dcore = robust_centre(la[core], lo[core])
        dist = hav(la, lo, cla, clo)
        keep = dist <= max(30.0, 4 * np.median(dcore[kc]))
        dk = dist[keep]
        p90_all = float(np.percentile(dist, 90)); p90 = float(np.percentile(dk, 90)) if len(dk) > 1 else 0.0
        rows.append(dict(pincode=pinc, lat=cla, lon=clo, coord_source="pin_median" if keep.sum() >= 2 else "pin_single", n_coord=int(keep.sum()), n_pin_outlier=int((~keep).sum()),
                         p90_km=p90, max_km=float(dk.max()), p90_all_km=p90_all))
        pts[pinc] = (la[keep], lo[keep])
    anypts = {k: (g.la.values, g.lo.values) for k, g in d[d.ok].groupby("pincode")}
    P = pd.DataFrame(rows).set_index("pincode").reindex(sorted(d.pincode.unique()))
    P["n_offices"] = n_off; P["n_raw_coord"] = n_raw.reindex(P.index).fillna(0).astype(int)
    # fallbacks for PINs left without a clean point:
    #   (1) placeholder points of that PIN that pass the region test (a town or division default: right area, low precision)
    #   (2) the median of the clean PIN centres sharing the first 4, then 3, then 2 digits
    sh = d[d.ok & d.shared & d.supported & ~d.pincode.isin(set(pts))].groupby("pincode")[["la", "lo"]].median()
    P.loc[sh.index, "lat"] = sh.la; P.loc[sh.index, "lon"] = sh.lo; P.loc[sh.index, "coord_source"] = "shared_point"; P.loc[sh.index, "p90_km"] = 20.0; P.loc[sh.index, "max_km"] = 20.0
    have = P.coord_source.isin(["pin_median", "pin_single"])
    for n, tag in ((4, "prefix4"), (3, "prefix3"), (2, "prefix2")):
        pre = P.index.str[:n]
        grp = P[have].groupby(pre[have])
        cen = grp[["lat", "lon"]].median(); cnt = grp.size()
        need = P.lat.isna() & pd.Series(pre, index=P.index).map(cnt).fillna(0).ge(2)
        if need.any():
            k = pre[need]
            P.loc[need, "lat"] = cen.lat.reindex(k).values; P.loc[need, "lon"] = cen.lon.reindex(k).values
            P.loc[need, "coord_source"] = tag
            # radius of a fallback = 90th percentile distance of the member PIN centres from the prefix centre
            dd = hav(P.lat[have].values, P.lon[have].values, cen.lat.reindex(pre[have]).values, cen.lon.reindex(pre[have]).values)
            r90 = pd.Series(dd, index=pre[have]).groupby(level=0).quantile(0.9)
            P.loc[need, "p90_km"] = r90.reindex(k).values; P.loc[need, "max_km"] = r90.reindex(k).values
    P["coord_source"] = P.coord_source.fillna("none")
    P[["n_coord", "n_pin_outlier"]] = P[["n_coord", "n_pin_outlier"]].fillna(0).astype(int)
    exact = P.coord_source.isin(["pin_median", "pin_single"])
    P["approx_radius_km"] = np.where(exact, P.p90_km.clip(3, 75), np.where(P.coord_source == "shared_point", 20.0, (P.p90_km.fillna(50) + 5).clip(10, 150))).round(1)
    P.loc[P.coord_source == "pin_single", "approx_radius_km"] = 5.0
    P["state"] = st_mode.reindex(P.index); P["district"] = di_mode.reindex(P.index)
    P["states"] = st_all.reindex(P.index).fillna(""); P["districts"] = di_all.reindex(P.index).fillna("")
    P["n_states"] = P.states.map(lambda s: len(s.split("|")) if s else 0); P["n_districts"] = P.districts.map(lambda s: len(s.split("|")) if s else 0)
    # "several states" only when the second state holds at least 20% of the PIN's labelled offices (a single stray label is a typing error)
    share2 = lab.groupby("pincode").statename.agg(lambda s: (s.value_counts(normalize=True).iloc[1] if s.nunique() > 1 else 0.0))
    P["multi_state"] = (share2.reindex(P.index).fillna(0) >= 0.2).astype(int); P["multi_district"] = (P.n_districts > 1).astype(int)
    P["scattered"] = ((P.p90_all_km > 25) | (P.n_pin_outlier >= np.maximum(2, 0.25 * (P.n_coord + P.n_pin_outlier)))).fillna(False).astype(int)
    # repair missing state / district labels from the nearest clean post offices of other PINs
    c = d[d.clean & (d.statename != "") & (d.district != "")]
    tree = BallTree(np.radians(c[["la", "lo"]].values), metric="haversine")
    miss = P.state.isna() & P.lat.notna()
    P["label_repaired"] = 0
    if miss.any():
        _, idx = tree.query(np.radians(P.loc[miss, ["lat", "lon"]].values), k=K_STATE)
        cs_, cd_ = c.statename.to_numpy(dtype=object), c.district.to_numpy(dtype=object)
        P.loc[miss, "state"] = [pd.Series(cs_[i]).value_counts().index[0] for i in idx]
        P.loc[miss, "district"] = [pd.Series(cd_[i]).value_counts().index[0] for i in idx]
        P.loc[miss, "label_repaired"] = 1
    P = P.reset_index().rename(columns={"index": "pincode"})
    cols = ["pincode", "state", "district", "lat", "lon", "coord_source", "approx_radius_km", "n_offices", "n_raw_coord", "n_coord", "n_pin_outlier", "p90_km", "max_km",
            "p90_all_km", "n_states", "states", "n_districts", "districts", "multi_state", "multi_district", "scattered", "label_repaired"]
    return P[cols].round({"lat": 6, "lon": 6, "p90_km": 2, "max_km": 2, "p90_all_km": 2}), anypts


# ---------------------------------------------------------------- 2. state names
def make_state_normaliser(d, F):
    canon = {re.sub(r"[^a-z ]", " ", s.lower()).strip(): s for s in STATES}
    canon.update({"dadra and nagar haveli and daman and diu": STATES[31]})
    dist_state = d[(d.district != "") & (d.statename != "")].groupby("district").statename.agg(lambda s: sorted(set(s)))
    dist_state = {nplace(k): v[0] for k, v in dist_state.items() if len(v) == 1}
    DIRECTION = {"uttar": "north", "dakshin": "south", "dakshina": "south", "purba": "east", "purbi": "east", "paschim": "west", "pashchim": "west", "pgs": "parganas", "kutch": "kachchh"}
    tok = lambda k: " ".join(sorted(DIRECTION.get(w, w) for w in k.split()))          # word order and Hindi / English direction words do not matter
    dist_tok = {tok(k): v for k, v in dist_state.items()}
    # a city written in the state field: use the state that other rows give for that city (3+ rows, 80%+ agreement)
    tmp = pd.DataFrame({"c": F.address_city.map(nplace), "s": F.address_stateOrRegion.map(lambda x: canon.get(re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", str(x).lower())).strip()))}).dropna()
    g = tmp.groupby("c").s.agg(lambda s: (s.value_counts().index[0], s.value_counts().iloc[0], len(s)))
    city_state = {k: v[0] for k, v in g.items() if v[2] >= 3 and v[1] / v[2] >= 0.8}

    def one(part):
        k = re.sub(r"\s+", " ", re.sub(r"[^a-z ]", " ", part.lower().replace("&", " and ").replace(".", ""))).strip()
        if not k: return None, "unknown"
        if k in AMBIGUOUS_STATE: return None, "ambiguous"
        if k in canon: return canon[k], "state"
        if k in STATE_ALIAS: return STATE_ALIAS[k], "alias"
        k2 = k.replace(" ", "")
        for a, v in list(canon.items()) + list(STATE_ALIAS.items()):
            if len(k2) > 3 and a.replace(" ", "") == k2: return v, "alias"
        m = difflib.get_close_matches(k, list(canon), n=1, cutoff=0.88)
        if m: return canon[m[0]], "fuzzy"
        p = nplace(k)
        if p in dist_state: return dist_state[p], "district"
        if p in city_state: return city_state[p], "city"
        t = tok(p)
        if t in dist_tok: return dist_tok[t], "district"
        m = difflib.get_close_matches(t, list(dist_tok), n=1, cutoff=0.86)
        if m: return dist_tok[m[0]], "district"
        return None, "unknown"

    def norm(raw):
        if not isinstance(raw, str) or not raw.strip(): return None, "missing"
        res = one(raw)
        if res[0] or res[1] == "ambiguous": return res
        parts = [p for p in re.split(r"[,;/]", raw) if p.strip()]
        found = [one(p) for p in parts]
        strong = [f for f in found if f[0] and f[1] in ("state", "alias", "fuzzy")] or [f for f in found if f[0]]
        if strong:
            vc = pd.Series([f[0] for f in strong]).value_counts()
            return vc.index[0], strong[0][1]
        # last resort: a state name contained in a longer string ("Satara District Maharashtra")
        k = re.sub(r"[^a-z ]", " ", raw.lower())
        for a, v in canon.items():
            if re.search(r"\b" + a + r"\b", k): return v, "contains"
        return None, "unknown"
    return norm


# ---------------------------------------------------------------- 3. city gazetteer
def build_gazetteer(d, F):
    """name key -> list of candidate places (lat, lon, radius_km, state, source)."""
    c = d[d.in_district_box & (d.supported | d.shared)].copy()      # right district; a placeholder point is still the right town, only less precise
    c["key"] = c.officename.map(lambda s: nplace(OFFICE_SUFFIX.sub("", OFFICE_SUFFIX.sub("", str(s)))))
    gaz = {}

    def add(key, la, lo, r, st, src):
        gaz.setdefault(key, []).append((float(la), float(lo), float(r), st, src))
    # (a) post offices carrying exactly this name, one candidate per (state, ~20 km cell)
    c["cell"] = (c.la / 0.2).round().astype(int).astype(str) + "_" + (c.lo / 0.2).round().astype(int).astype(str)
    for (key, st, _), g in c[c.key.str.len() >= 3].groupby(["key", "statename", "cell"]):
        add(key, g.la.median(), g.lo.median(), 5.0 if (~g.shared).any() else 15.0, st, "office")
    # (b) districts: centre = head office of the district if one carries the district name, else median of the district's post offices
    for (dist, st), g in c[(c.district != "") & ~c.shared].groupby(["district", "statename"]):
        cla, clo, keep, dist_km = robust_centre(g.la.values, g.lo.values, floor_km=60.0)
        add(nplace(dist), cla, clo, float(np.clip(np.percentile(dist_km[keep], 75), 10, 60)), st, "district")
    # (c) head / sub offices whose name starts with the city name ("Pune City H.O", "Lucknow Chowk HO")
    ho = c[c.officetype.isin(["HO", "PO"]) & ~c.shared]
    first = {}
    for key, st, la, lo in zip(ho.key, ho.statename, ho.la, ho.lo):
        w = key.split(" ")
        for n in (1, 2):
            if len(w) > n: first.setdefault((" ".join(w[:n]), st), []).append((la, lo))
    for (key, st), pts in first.items():
        if len(key) < 4: continue
        a = np.array(pts); cla, clo, keep, dist_km = robust_centre(a[:, 0], a[:, 1])
        if keep.sum() >= 2 and np.percentile(dist_km[keep], 90) <= 25:
            add(PLACE_ALIAS.get(key, key), cla, clo, float(np.clip(np.percentile(dist_km[keep], 90), 5, 25)), st, "office_prefix")
    return gaz


def facility_consensus(F):
    """Where do the OTHER facilities that state the same city and state sit? (5+ rows, robust median of their PIN centres and coordinates)."""
    cons = {}
    for (key, st), g in F[F.city_key.str.len() >= 3].groupby(["city_key", F.st_state.fillna("")]):
        la = np.concatenate([g.lat[g.ll_ok].values, g.pc_lat[g.pc_lat.notna()].values]); lo = np.concatenate([g.lon[g.ll_ok].values, g.pc_lon[g.pc_lat.notna()].values])
        if len(g) < 5 or len(la) < 6: continue
        cla, clo, keep, dist = robust_centre(la, lo, floor_km=40.0)
        if keep.mean() < 0.6: continue                        # the rows do not agree among themselves
        cons[(key, st)] = (float(cla), float(clo), float(np.clip(np.percentile(dist[keep], 75), 5, 30)), st or None, "facility_consensus", len(g))
    return cons


# ---------------------------------------------------------------- 4. per facility
def main(write=True):
    os.makedirs(OUT, exist_ok=True)
    d, st = load_post_offices()
    print("post offices:", st)
    P, pin_pts = build_pin_lookup(d)
    print("PIN lookup:", len(P), "PINs | centre source", P.coord_source.value_counts().to_dict(), "| several states", int(P.multi_state.sum()), "| several districts", int(P.multi_district.sum()),
          "| scattered", int(P.scattered.sum()), "| label repaired", int(P.label_repaired.sum()), "| median radius km", P.approx_radius_km.median())
    Pi = P.set_index("pincode")

    F = load_facilities()
    F["lat"], F["lon"] = F.latitude_n, F.longitude_n
    F["ll_ok"] = F.lat.between(BOX["la0"], BOX["la1"]) & F.lon.between(BOX["lo0"], BOX["lo1"])
    norm = make_state_normaliser(d, F)
    ns = F.address_stateOrRegion.map(norm)
    F["st_state"], F["st_src"] = ns.map(lambda x: x[0]), ns.map(lambda x: x[1])
    print("stated state:", F.address_stateOrRegion.nunique(), "spellings ->", F.st_state.nunique(), "states | how resolved:", F.st_src.value_counts().to_dict())

    # postcode -> PIN
    z = F.address_zipOrPostcode.fillna("").astype(str).str.replace(r"\D", "", regex=True)
    F["pc"] = z.where(z.str.fullmatch(r"[1-9]\d{5}"))
    F["pc_status"] = np.where(F.pc.isna(), "no_postcode", np.where(F.pc.isin(Pi.index), "found", "not_in_directory"))
    look = F.pc.where(F.pc_status == "found")
    for a, b in (("pc_lat", "lat"), ("pc_lon", "lon"), ("pc_rad", "approx_radius_km"), ("pc_state", "state"), ("pc_district", "district"), ("pc_src", "coord_source"),
                 ("pin_multi_state", "multi_state"), ("pin_scattered", "scattered")):
        F[a] = look.map(Pi[b])
    # postcode not in the directory: use the PINs sharing the first 4 (then 3) digits
    ok_pin = P[P.coord_source.isin(["pin_median", "pin_single"])]
    for n in (4, 3):
        need = (F.pc_status == "not_in_directory") & F.pc_lat.isna()
        if not need.any(): break
        g = ok_pin.groupby(ok_pin.pincode.str[:n])
        cen = g[["lat", "lon"]].median(); stt = g.state.agg(lambda s: s.value_counts().index[0]); dis = g.district.agg(lambda s: s.value_counts().index[0])
        k = F.pc[need].str[:n]; hit = k.isin(cen.index); ii = k[hit].index
        F.loc[ii, "pc_lat"] = cen.lat.reindex(k[hit]).values; F.loc[ii, "pc_lon"] = cen.lon.reindex(k[hit]).values
        F.loc[ii, "pc_state"] = stt.reindex(k[hit]).values; F.loc[ii, "pc_district"] = dis.reindex(k[hit]).values
        F.loc[ii, "pc_rad"] = 25.0 if n == 4 else 60.0; F.loc[ii, "pc_src"] = f"unknown_pin_prefix{n}"
    F["pin_multi_state"] = F.pin_multi_state.fillna(0).astype(int); F["pin_scattered"] = F.pin_scattered.fillna(0).astype(int)
    print("postcode:", F.pc_status.value_counts().to_dict(), "| PIN centre source:", F.pc_src.value_counts(dropna=False).to_dict())

    # coordinates -> nearest post offices
    c = d[d.clean & (d.statename != "") & (d.district != "")]
    tree = BallTree(np.radians(c[["la", "lo"]].values), metric="haversine")
    cst, cdi = c.statename.to_numpy(dtype=object), c.district.to_numpy(dtype=object)

    def knn(la, lo):
        dist, idx = tree.query(np.radians(np.c_[la, lo]), k=K_STATE)
        s = [pd.Series(cst[i]).value_counts() for i in idx]; di = [pd.Series(cdi[i]).value_counts().index[0] for i in idx]
        return [x.index[0] for x in s], di, [x.iloc[0] / K_STATE for x in s], dist[:, 0] * R_EARTH
    m = F.ll_ok.values
    gs, gd, gshare, nn = knn(F.lat[m].values, F.lon[m].values)
    F.loc[m, "geo_state"] = gs; F.loc[m, "geo_district"] = gd; F.loc[m, "geo_state_share"] = gshare; F.loc[m, "nn_km"] = nn
    F["ll_usable"] = F.ll_ok & (F.nn_km <= 50)             # further than 50 km from every post office = at sea or abroad

    # distance from coordinates to the PIN: centre, and nearest post office of that PIN
    F["d_coord_pin_km"] = np.where(F.ll_usable & F.pc_lat.notna(), hav(F.lat, F.lon, F.pc_lat, F.pc_lon), np.nan)
    # generous on purpose: ANY post office recorded under that PIN counts, including the ones not trusted for the centre
    near = np.full(len(F), np.nan)
    for i, (ok, pc, la, lo) in enumerate(zip(F.ll_usable, F.pc, F.lat, F.lon)):
        if ok and pc in pin_pts: near[i] = hav(pin_pts[pc][0], pin_pts[pc][1], la, lo).min()
    F["d_coord_pin_nearest_km"] = np.fmin(near, F.d_coord_pin_km)

    # city
    F["city_key"] = F.address_city.map(nplace)
    gaz = build_gazetteer(d, F); cons = facility_consensus(F)
    cons_any = {}
    for (k, st_), v in cons.items():
        if k not in cons_any or v[5] > cons_any[k][5]: cons_any[k] = v
    names_by_state = {}
    for k, v in gaz.items():
        for x in v:
            if x[4] in ("office", "district") and len(k) >= 6: names_by_state.setdefault(x[3], set()).add(k)
    for (k, st_), v in cons.items():
        if st_: names_by_state.setdefault(st_, set()).add(k)
    names_by_state = {k: sorted(v) for k, v in names_by_state.items()}
    res = []
    for key, st_, lok, la, lo, pla, plo in zip(F.city_key, F.st_state, F.ll_usable, F.lat, F.lon, F.pc_lat, F.pc_lon):
        cand = []
        s = st_ if isinstance(st_, str) else ""
        if (key, s) in cons: cand.append(cons[(key, s)][:5])
        elif not s and key in cons_any: cand.append(cons_any[key][:5])      # stated state unreadable: use the largest group of rows naming this city
        g = [x for x in gaz.get(key, []) if (not s) or x[3] == s]
        exact = [x for x in g if x[4] in ("office", "district")]
        cand += exact if exact else g
        if not cand and len(key) >= 3:
            # retry: drop a trailing "east / west / cantt / junction ..." word, then allow a one-or-two letter spelling difference (Hissar / Hisar)
            k2 = nplace(TAIL_WORDS.sub("", key))
            if k2 != key and len(k2) >= 4:
                if (k2, s) in cons: cand.append(cons[(k2, s)][:5])
                cand += [x for x in gaz.get(k2, []) if ((not s) or x[3] == s) and x[4] in ("office", "district")]
            if not cand and s and len(key) >= 6:
                m = difflib.get_close_matches(key, names_by_state.get(s, []), n=1, cutoff=0.88)
                if m:
                    if (m[0], s) in cons: cand.append(cons[(m[0], s)][:5])
                    cand += [x for x in gaz.get(m[0], []) if x[3] == s and x[4] in ("office", "district")]
            cand = [(x[0], x[1], x[2], x[3], x[4] + "_approx") for x in cand]
        if not cand and len(key) >= 3:
            res.append((np.nan, np.nan, np.nan, "not_found", 0)); continue
        if len(key) < 3:
            res.append((np.nan, np.nan, np.nan, "no_city", 0)); continue
        a = np.array([(x[0], x[1], x[2]) for x in cand])
        cost = np.zeros(len(a))
        if lok: cost += np.maximum(hav(a[:, 0], a[:, 1], la, lo) - a[:, 2], 0)
        if pd.notna(pla): cost += np.maximum(hav(a[:, 0], a[:, 1], pla, plo) - a[:, 2], 0)
        j = int(np.argmin(cost))                             # benefit of the doubt: the same-named place that fits the other signals best
        res.append((a[j, 0], a[j, 1], a[j, 2], cand[j][4], len(cand)))
    F[["city_lat", "city_lon", "city_rad", "city_src", "city_n_cand"]] = pd.DataFrame(res, index=F.index)
    print("city located by:", F.city_src.value_counts().to_dict())
    F["d_coord_city_km"] = np.where(F.ll_usable & F.city_lat.notna(), hav(F.lat, F.lon, F.city_lat, F.city_lon), np.nan)
    F["d_pin_city_km"] = np.where(F.pc_lat.notna() & F.city_lat.notna(), hav(F.pc_lat, F.pc_lon, F.city_lat, F.city_lon), np.nan)

    # pairwise agreement
    has_L, has_P, has_C = F.ll_usable, F.pc_lat.notna(), F.city_lat.notna()
    same_d_LP = (F.geo_district == F.pc_district) & F.geo_district.notna()
    LP = (F.d_coord_pin_nearest_km <= AGREE_LP_NEAR) | (F.d_coord_pin_km <= F.pc_rad + AGREE_LP_CENTRE) | (same_d_LP & (F.d_coord_pin_km <= 40))
    ck = F.city_key
    LC = (F.d_coord_city_km <= F.city_rad + AGREE_CITY) | ((F.geo_district.fillna("").map(nplace) == ck) & has_L & (ck != ""))
    PC = (F.d_pin_city_km <= F.city_rad + F.pc_rad.fillna(0) + AGREE_CITY) | ((F.pc_district.fillna("").map(nplace) == ck) & has_P & (ck != ""))
    LP, LC, PC = LP & has_L & has_P, LC & has_L & has_C, PC & has_P & has_C
    # a place found only through a post-office name can confirm a location but cannot contradict one:
    # many villages and neighbourhoods share a name inside one state ("Aundh" is a suburb of Pune and a village in Satara)
    weak_city = has_C & ~F.city_src.isin(["facility_consensus", "district"]) & ~LC & ~PC
    F["city_unverifiable"] = weak_city.astype(int)
    has_C = has_C & ~weak_city
    F["agree_coord_pin"], F["agree_coord_city"], F["agree_pin_city"] = LP.astype(int), LC.astype(int), PC.astype(int)
    nsig = has_L.astype(int) + has_P.astype(int) + has_C.astype(int)
    npair = LP.astype(int) + LC.astype(int) + PC.astype(int)
    cls = np.full(len(F), "H_cannot_tell", dtype=object)
    three = (nsig == 3).values
    cls[three & (npair >= 2).values] = "A_all_agree"
    cls[three & (npair == 1).values & PC.values] = "B_coordinates_differ"
    cls[three & (npair == 1).values & LC.values] = "C_postcode_differs"
    cls[three & (npair == 1).values & LP.values] = "D_city_differs"
    cls[three & (npair == 0).values] = "E_all_differ"
    two = (nsig == 2).values
    cls[two & (npair == 1).values] = "F_two_agree_third_missing"
    cls[two & (npair == 0).values] = "G_two_differ_third_missing"
    F["loc_class"] = cls; F["n_signals"] = nsig

    # states named by the three signals
    def nstates(r):
        s = {x for x in (r.st_state, r.pc_state, r.geo_state if r.ll_usable else None) if isinstance(x, str) and x}
        return len(s)
    F["n_states"] = F.apply(nstates, axis=1)

    # best coordinates for distance ranking
    best_src = np.where(np.isin(cls, ["A_all_agree", "C_postcode_differs", "D_city_differs"]), "coordinates", "")
    best_src = np.where(cls == "B_coordinates_differ", "postcode", best_src)
    best_src = np.where((cls == "F_two_agree_third_missing") & has_L.values, "coordinates", best_src)
    best_src = np.where((cls == "F_two_agree_third_missing") & ~has_L.values, "postcode", best_src)
    # nothing agrees: prefer the signal backed by the stated state, in the order postcode, coordinates, city
    st = F.st_state.fillna("?")
    p_ok, l_ok = (has_P & (F.pc_state == st)).values, (has_L & (F.geo_state == st)).values
    unresolved = np.isin(cls, ["E_all_differ", "G_two_differ_third_missing", "H_cannot_tell"])
    pick = np.where(p_ok, "postcode", np.where(l_ok, "coordinates", np.where(has_C.values, "city", np.where(has_P.values, "postcode", np.where(has_L.values, "coordinates", "none")))))
    best_src = np.where(unresolved, pick, best_src)
    F["best_src"] = best_src
    F["best_lat"] = np.select([best_src == "coordinates", best_src == "postcode", best_src == "city"], [F.lat, F.pc_lat, F.city_lat], np.nan)
    F["best_lon"] = np.select([best_src == "coordinates", best_src == "postcode", best_src == "city"], [F.lon, F.pc_lon, F.city_lon], np.nan)
    F["best_radius_km"] = np.select([best_src == "coordinates", best_src == "postcode", best_src == "city"], [1.0, F.pc_rad, F.city_rad], np.nan)
    hb = F.best_lat.notna().values
    bs, bd, _, _ = knn(F.best_lat[hb].values, F.best_lon[hb].values)
    F.loc[hb, "best_state"] = bs; F.loc[hb, "best_district"] = bd
    usep = (best_src == "postcode") & F.pc_state.notna().values
    F.loc[usep, "best_state"] = F.pc_state[usep]; F.loc[usep, "best_district"] = F.pc_district[usep]

    base = pd.Series(cls).map({"A_all_agree": 0.95, "F_two_agree_third_missing": 0.85, "D_city_differs": 0.80, "C_postcode_differs": 0.75, "B_coordinates_differ": 0.60,
                               "G_two_differ_third_missing": 0.30, "E_all_differ": 0.15, "H_cannot_tell": 0.40}).values.astype(float)
    base = np.where((cls == "H_cannot_tell") & (best_src == "none"), 0.0, base)
    pen = 0.10 * ((best_src == "postcode") & ((F.pin_multi_state == 1) | (F.pin_scattered == 1) | ~F.pc_src.isin(["pin_median", "pin_single"]).values)) + 0.05 * (F.n_states.values >= 2)
    F["location_confidence"] = np.clip(base - pen, 0, 1).round(2)

    # feature columns for the yardstick (all numeric)
    F["geo_disagree"] = np.isin(cls, ["B_coordinates_differ", "C_postcode_differs", "D_city_differs", "E_all_differ", "G_two_differ_third_missing"]).astype(int)
    F["coord_differs"] = (cls == "B_coordinates_differ").astype(int); F["postcode_differs"] = (cls == "C_postcode_differs").astype(int)
    F["city_differs"] = (cls == "D_city_differs").astype(int); F["all_differ"] = np.isin(cls, ["E_all_differ", "G_two_differ_third_missing"]).astype(int)
    F["cannot_tell"] = (cls == "H_cannot_tell").astype(int)
    F["one_differs"] = np.isin(cls, ["B_coordinates_differ", "C_postcode_differs", "D_city_differs"]).astype(int)      # two signals agree, one is the odd one out
    F["three_places"] = (cls == "E_all_differ").astype(int)                                                           # all three located, no two agree
    min_pair = F[["d_coord_pin_nearest_km", "d_coord_city_km", "d_pin_city_km"]].min(axis=1)
    F["three_places_far"] = ((cls == "E_all_differ") & (min_pair > FAR_KM)).astype(int)                                # ... and every pair is more than 100 km apart
    F["n_pairs_differ"] = ((has_L & has_P & ~LP).astype(int) + (has_L & has_C & ~LC).astype(int) + (has_P & has_C & ~PC).astype(int))
    F["state_mismatch"] = (F.n_states >= 2).astype(int)
    F["coord_pin_far"] = (F.d_coord_pin_nearest_km > FAR_KM).astype(int)
    F["log_d_coord_pin"] = np.log1p(F.d_coord_pin_nearest_km.fillna(0))
    F["max_pair_km"] = F[["d_coord_pin_nearest_km", "d_coord_city_km", "d_pin_city_km"]].max(axis=1)
    F["log_max_pair_km"] = np.log1p(F.max_pair_km.fillna(0))
    F["any_pair_far"] = (F.max_pair_km > FAR_KM).astype(int)

    F = F.rename(columns={"unique_id": "uid"})
    # location.csv: every numeric column other than best_lat / best_lon / best_radius_km is a candidate feature for analysis/eval_feature.py.
    # Text columns explain the class. Intermediate numbers (PIN centre, city centre ...) are left out so the yardstick is not flooded.
    out = F[["uid", "best_lat", "best_lon", "best_state", "best_district", "loc_class", "d_coord_pin_km", "location_confidence",
             "geo_disagree", "one_differs", "all_differ", "three_places", "three_places_far", "coord_differs", "postcode_differs", "city_differs", "cannot_tell",
             "city_unverifiable", "n_pairs_differ", "n_states", "state_mismatch",
             "d_coord_pin_nearest_km", "log_d_coord_pin", "coord_pin_far", "log_max_pair_km", "any_pair_far", "pin_multi_state", "pin_scattered",
             "best_radius_km", "best_src", "st_state", "st_src", "pc_status", "pc_src", "pc_state", "pc_district", "geo_state", "geo_district", "city_src"]]
    out = out.round({"best_lat": 6, "best_lon": 6, "d_coord_pin_km": 2, "d_coord_pin_nearest_km": 2, "log_d_coord_pin": 3, "log_max_pair_km": 3, "best_radius_km": 1})
    if write:
        P.to_csv(os.path.join(OUT, "pin_lookup.csv"), index=False)
        out.to_csv(os.path.join(OUT, "location.csv"), index=False)
    print("\nfacilities:", len(out), "| class:", out.loc_class.value_counts().to_dict())
    print("signals usable: coordinates", int(has_L.sum()), "| postcode", int(has_P.sum()), "| city", int(has_C.sum()))
    print("states named by the signals:", out.n_states.value_counts().sort_index().to_dict(), "| best source:", out.best_src.value_counts().to_dict())
    print("coordinates vs postcode: within 10 km of PIN centre", int((F.d_coord_pin_km <= 10).sum()), "| within 10 km of a post office of that PIN", int((F.d_coord_pin_nearest_km <= 10).sum()),
          "| agree by the full rule", int(LP.sum()), "| more than 100 km apart", int(F.coord_pin_far.sum()))
    print("location confidence:", out.location_confidence.describe().round(2).to_dict())
    return P, F, out


if __name__ == "__main__":
    main()
