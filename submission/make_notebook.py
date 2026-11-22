"""Build the single-file submission notebook (submission/CareSaathi.ipynb) from the repository.

The notebook is self-contained: every pipeline module is a readable code cell that writes its file, the small
data files the pipeline needs (labels, district table, public dialysis list, doctor list, icons) are one compressed
cell, and the last cells read the Marketplace tables on Databricks, run the pipeline and show the results.
Run from the project root: python submission/make_notebook.py
"""
import os, json, base64, gzip, glob, io, tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = lambda p: open(os.path.join(ROOT, p), encoding="utf-8").read()
cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n").splitlines(True)})

md("""
# CareSaathi: find the right care, with proof

**CMU Data Science Club × Databricks Datathon, Fall 2026.** *Saathi* means companion.

Code and history: https://github.com/beomjin-seo/caresaathi · The app runs on Databricks Apps (Free Edition).

## The problem
A family names a need (dialysis, a C-section tonight, bone surgery) and a place. Which nearby facility can really do it, why should they believe it, and what should they check before travelling? The facility table has 9,989 records written from websites, with no ground truth about which services are really delivered. So we do not predict. **We grade the evidence each record gives, and show it.**

## How CareSaathi decides (one score per facility and service)
1. **Read** every sentence about the service in the record (19 services, regex dictionary in `ontology.py`; the facility's own name never counts).
2. **Grade** it: a loose mention ×1, a named procedure ×4.8, equipment or a unit with detail ×9.1; the share of items the service needs (theatre, anaesthesia, blood for a C-section) found in the record, up to ×26; the facility's own website has a page for it ×2.9.
3. **One real place?** Coordinates, postcode and city all disagree ×0.13; the text names two or more towns over 60 km away ×0.19; the row was built from two or more other organisations' websites ×0.46.
4. **Score:** odds = 0.74 × evidence × one-real-place, trust = 100 × odds ÷ (1 + odds). Strong ≥ 90, some ≥ 70, weak below (left out).
5. **Rules outside the score:** a single-specialty facility (dental, eye, skin, physio, ayurveda or homeopathy) claiming care outside its field is left out with the reason; a service's must-have item (for example an operating theatre for a C-section) missing from the record caps the score just under "strong" and the card says to confirm it by phone.
6. **Rank:** emergency, nearest first (places within 3.6 km count as equally near, the measured error of map points; stronger evidence first among them); planned, highest trust first inside the smallest area that holds five places (scores within 2.1 points count as equal, the measured spread of the score over refits; nearer first among them).

## Where the numbers come from
The multipliers are logistic-regression coefficients fitted on 605 labelled claims: 387 labelled from facility names (a kidney centre claiming dialysis is likely real; a dental clinic claiming dialysis is likely false; names are never a feature) and 218 set by AI readers of the record. On claims held out from fitting (facilities kept whole across folds): AUC 0.88; likely real in 98% of "strong", 84% of "some", 44% of "weak". Weakest service: heart surgery (AUC 0.76). **Nobody visited or phoned these facilities**, so the score is a ranking index, not a probability, and every card ends with what to ask on the phone.

## What the app adds for people who cannot read well
Picture tiles, English and Hindi, read-aloud on every line with play and pause, free-text and voice input, the nearest place in an emergency with ambulance numbers (108, 102, 112), cost guidance (public facilities, Ayushman card), district context from NFHS-5, a health-worker list to print or read out, and "Who will treat you": doctors named on each hospital's own website, matched to the need (read on 22 Nov 2026, not verified, not scored).

## Known limits
The table is about 5% public facilities while most births in India happen in public ones. No text for a service does not mean the place lacks it. Labels are proxies, not site visits. Distances are straight lines. Full notes: `analysis/FINDINGS.md` in the repository.
""")
md("""
## How to run this notebook on Databricks Free Edition
1. Get the Marketplace listing **Virtue Foundation Dataset (DAIS 2026)** so the catalog `databricks_virtue_foundation_dataset_dais_2026` exists.
2. Import this notebook, attach serverless compute, **Run all** (about 8 minutes).
3. The cells write the pipeline to `/tmp/caresaathi`, read the three source tables, run every step, save Delta tables `workspace.default.caresaathi_*`, and build the app page `app/index.html`.
""")
code("""
import os, sys, json, base64, gzip, io, tarfile, subprocess, shutil
WORK = "/tmp/caresaathi"
shutil.rmtree(WORK, ignore_errors=True); os.makedirs(WORK)
def write(path, text):
    full = os.path.join(WORK, path); os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, "w", encoding="utf-8").write(text.lstrip("\\n"))
    print("wrote", path, len(text), "characters")
""")
MODS = [("pipeline/common.py", "Loading the facility table: keep facilities, drop duplicate ids, parse list columns."),
        ("pipeline/ontology.py", "The service dictionary: what counts as a loose mention, a procedure or a unit, false friends to mask, and the items each service needs."),
        ("pipeline/location.py", "Where each facility really is: map point, postcode and stated city compared; the majority wins."),
        ("pipeline/claims.py", "Evidence per (facility, service): every matching sentence, caution flags (negation, referral, future, biography, directory, news), tier, best quote, items found."),
        ("pipeline/feat_attribution.py", "Warning sign: the text names towns far from the facility."),
        ("pipeline/feat_sources.py", "Warning sign: the row was built from other organisations' websites; and whether the facility's own site has a page for the service."),
        ("pipeline/trust.py", "Labels, logistic-regression fit, grouped cross-validation, bootstrap ranges."),
        ("pipeline/musthave.py", "Must-have items per service, each kept only if a medical refutation check and a data check both passed."),
        ("pipeline/export_app.py", "Bands, rules outside the score, ladder quotes, doctors, district context: everything the app shows."),
        ("pipeline/scrape_doctors.py", "Optional, not run here (Free Edition blocks most outbound web traffic): how doctors were read from hospitals' own websites."),
        ("app/build.py", "Assembles the single-page app from the template, the data and the icons."),
        ("app/app.py", "The Databricks App: serves the page."),
        ("app/app.yaml", "Databricks App start command."),
        ("app/requirements.txt", "Databricks App dependencies."),
        ("app/template.html", "The app page (HTML, CSS, JavaScript): ranking, cards, explanations.")]
for path, what in MODS:
    src = R(path)
    assert "'''" not in src, path
    md(f"### `{path}`\n{what}")
    code(f"write({path!r}, r'''\n{src}''')")
buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as tf:
    for p in (["analysis/labels/labels_likely_false_A.csv", "analysis/labels/labels_likely_false_B.csv", "analysis/labels/labels_likely_real.csv",
               "analysis/labels/labels_general.csv", "analysis/out_nfhs_district.csv", "pipeline/external/pmndp_centres.csv", "pipeline/external/doctors_web.json"]
              + sorted(os.path.relpath(f, ROOT) for f in glob.glob(os.path.join(ROOT, "app/icons/*.svg")))):
        tf.add(os.path.join(ROOT, p), arcname=p)
blob = base64.b64encode(buf.getvalue()).decode()
md("### Small data files\nLabels (`analysis/labels/`), the district table, the public dialysis-centre list, the doctor list read from hospital websites, and the icons, packed as one compressed archive.")
code("DATA = '" + blob + "'\ntarfile.open(fileobj=io.BytesIO(base64.b64decode(DATA)), mode='r:gz').extractall(WORK)\nprint(sorted(os.listdir(WORK)))")
run = R("databricks/run_pipeline.py")
part = run[run.index("def as_text(df):"):run.index("# COMMAND ----------\n\n# MAGIC %md ## 2.")]
md("## 1. Read the three Marketplace tables\nList-valued columns are kept as JSON text, exactly as in the source.")
code('from pyspark.sql import functions as F, types as T\nimport pandas as pd\nSOURCE = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset"\nTARGET = "workspace.default"\n\n' + part.strip())
md("## 2. Run the pipeline\nEach step prints its own checks (claim counts, fitted multipliers with 90% bootstrap ranges, held-out AUC, band shares).")
step = run[run.index("STEPS = ["):run.index("# COMMAND ----------\n\n# MAGIC %md ## 3.")]
code(step.strip())
md("## 3. Save results as Delta tables")
code('for name, path in [("caresaathi_trust", "pipeline/out/trust.csv"), ("caresaathi_claims", "pipeline/out/claims.csv"), ("caresaathi_location", "pipeline/out/location.csv")]:\n'
     '    pdf = pd.read_csv(f"{WORK}/{path}", low_memory=False)\n'
     '    spark.createDataFrame(pdf.astype(object).where(pdf.notna(), None).astype(str).replace({"None": None})).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{TARGET}.{name}")\n'
     '    print(f"{TARGET}.{name}: {len(pdf):,} rows")')
md("## 4. One answer: dialysis in Patna\nHighest trust first, with the sentence each score rests on.")
code('display(spark.sql(f"""\n  SELECT name, address_city, round(cast(trust AS double), 1) AS trust, tier, coreq_found, coreq_total, quote_field, quote\n  FROM {TARGET}.caresaathi_trust\n  WHERE service = \'dialysis\' AND lower(address_city) = \'patna\'\n  ORDER BY cast(trust AS double) DESC LIMIT 10\n"""))')
md("## 5. Serve it\nThe rebuilt page is `/tmp/caresaathi/app/index.html`. To publish it, copy `app.py`, `app.yaml`, `requirements.txt` and `index.html` into a workspace folder and deploy that folder as a Databricks App.")
nb = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
out = os.path.join(ROOT, "submission", "CareSaathi.ipynb")
json.dump(nb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("wrote", out, round(os.path.getsize(out) / 1e6, 2), "MB,", len(cells), "cells")
