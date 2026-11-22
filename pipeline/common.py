"""Shared loading/cleaning helpers. Run scripts from the project root."""
import os, json, re
import numpy as np, pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pipeline", "out")
LIST_COLS = ["specialties", "procedure", "equipment", "capability", "source_types",
             "source_ids", "source_urls", "websites", "phone_numbers", "affiliationTypeIds"]
NULLS = {"", "null", "none", "nan", "[]", "n/a", "na"}


def jl(s):
    """Parse a JSON-list cell; anything else becomes an empty list."""
    if not isinstance(s, str):
        return []
    try:
        v = json.loads(s)
        return [x for x in v if isinstance(x, str) and x.strip().lower() not in NULLS] if isinstance(v, list) else []
    except Exception:
        return []


def clean_text(s):
    return "" if (not isinstance(s, str) or s.strip().lower() in NULLS) else s.strip()


def load_facilities():
    """10,088 raw rows -> rows where organization_type == 'facility', one per unique_id."""
    f = pd.read_csv(os.path.join(ROOT, "facilities.csv"), dtype=str, low_memory=False)
    f = f[f.organization_type == "facility"].drop_duplicates("unique_id").reset_index(drop=True)
    for c in LIST_COLS:
        f[c + "_l"] = f[c].map(jl)
    for c in ["latitude", "longitude", "numberDoctors", "capacity", "yearEstablished"]:
        f[c + "_n"] = pd.to_numeric(f[c], errors="coerce")
    for c in ["name", "description", "address_city", "address_stateOrRegion", "facilityTypeId", "operatorTypeId", "officialWebsite", "officialPhone"]:
        f[c] = f[c].map(clean_text)
    return f


def haversine(la1, lo1, la2, lo2):
    la1, lo1, la2, lo2 = map(np.radians, [la1, lo1, la2, lo2])
    h = np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * np.arcsin(np.sqrt(h))


def norm_name(s):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", str(s).lower())).strip()
