# Sahi Ilaj: find the right care

Entry for the CMU Data Science Club x Databricks Datathon, Fall 2026.

A person picks a healthcare need, says whether it is an emergency, and gives a place in India (PIN code, town, or shared location). The app returns up to five facilities on a map, and for each one shows what the record confirms, what it does not, what it may cost, and how its trust score was calculated.

The source table (about 10,000 Indian facilities from the Virtue Foundation, extracted from web text) is treated as a set of claims, not facts. Every (facility, service) claim gets a trust score:

```
odds  = base x E x C          trust = 100 x odds / (1 + odds)
E  how specific the text is, and how many of the things the service needs appear in the record
C  whether the row is one real place (location fields agree, text does not name far-away towns,
   the row was not built from other organisations' websites)
```

The multipliers are fitted on 605 labelled claims, not chosen by hand. Emergency results are ordered by distance; planned-care results by trust inside the local area. Weak claims and single-specialty facilities claiming care outside their specialty are removed and shown with the reason.

Numbers, checks, limits and things that were tried and dropped are in [analysis/FINDINGS.md](analysis/FINDINGS.md).

## Layout

| Folder | Contents |
|---|---|
| `pipeline/` | Data steps, run in the order below |
| `analysis/` | Exploration scripts, reader labels (`labels/`), `FINDINGS.md` |
| `app/` | Single-page app (`index.html`), its template, icons, and a small Flask server for Databricks Apps |
| `research/` | Notes on earlier hackathons that used this dataset and on platform limits |

## Run the pipeline

Put the three Marketplace tables in the project root as `facilities.csv`, `indiaPincodeDirectory1.csv` + `indiaPincodeDirectory2.csv` (two halves of the PIN directory) and `nfhs_5_district_health_indicators.csv`. They are not stored in this repository. Two small inputs are included: the official list of public dialysis centres (`pipeline/external/pmndp_centres.csv`, from pmndp.mohfw.gov.in) and the district table used for the area notes (`analysis/out_nfhs_district.csv`).

```bash
pip install -r requirements.txt
python pipeline/location.py           # PIN lookup and where each facility really is
python pipeline/claims.py             # sentences about each service, evidence tier per claim (about 3 minutes)
python pipeline/feat_attribution.py   # far-away towns named in the text, phone area codes
python pipeline/feat_sources.py       # whose websites the row was built from
python pipeline/trust.py              # fit the multipliers, score every claim
python pipeline/export_app.py         # writes app/data.json
cd app && python build.py             # writes app/index.html
```

## Run the app

Open `app/index.html` in a browser, or `cd app && python app.py`. For Databricks Apps, deploy the `app/` folder (`app.yaml`, `app.py`, `requirements.txt`, `index.html`).

## Limits

- The table is about 5% public facilities, while most rural care in India is public.
- No text for a service does not mean a facility lacks it.
- Distances are straight lines.
- Labels come from facility names plus readers of the text; nobody visited a facility.
- The trust score is an index for ranking, not a probability. The app does not diagnose.

## Credits

Icons: [Health Icons](https://healthicons.org) (CC0). Map: Leaflet with OpenStreetMap tiles. District indicators: NFHS-5. Facility data: Virtue Foundation dataset on the Databricks Marketplace.
