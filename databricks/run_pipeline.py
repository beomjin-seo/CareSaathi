# Databricks notebook source
# MAGIC %md
# MAGIC # Sahi Ilaj: run the pipeline on Databricks Free Edition
# MAGIC
# MAGIC This notebook reads the three tables of the Marketplace listing **Virtue Foundation Dataset (DAIS 2026)**, runs the scoring pipeline in this repository, saves the results as Delta tables, and rebuilds the app page.
# MAGIC
# MAGIC Before running: get the listing from the Marketplace so that the catalog below exists, and attach serverless compute. Run all cells; it takes about 8 minutes.

# COMMAND ----------

import os, sys, shutil, subprocess
import pandas as pd
from pyspark.sql import functions as F, types as T

SOURCE = "databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset"   # read-only shared catalog
TARGET = "workspace.default"                                                          # where result tables are written
REPO = os.path.dirname(os.getcwd())      # this notebook lives in <repo>/databricks
WORK = "/tmp/sahi_ilaj"                  # scratch copy on the driver; the shared catalog cannot be written to

assert os.path.exists(os.path.join(REPO, "pipeline", "claims.py")), f"Set REPO to the repository folder (now: {REPO})"
shutil.rmtree(WORK, ignore_errors=True)
for d in ["pipeline", "analysis", "app"]:
    shutil.copytree(os.path.join(REPO, d), os.path.join(WORK, d), ignore=shutil.ignore_patterns("__pycache__", "*.pkl", "index.html", "sahi-ilaj.html"))
print("working copy:", WORK)

# COMMAND ----------

# MAGIC %md ## 1. Export the source tables in the shape the pipeline expects
# MAGIC List-valued columns are kept as JSON text, exactly as they appear in the source.

# COMMAND ----------

def as_text(df):
    cols = []
    for f in df.schema.fields:
        c = F.col(f"`{f.name}`")
        nested = isinstance(f.dataType, (T.ArrayType, T.StructType, T.MapType))
        cols.append((F.to_json(c) if nested else c.cast("string")).alias(f.name))
    return df.select(cols)

fac = as_text(spark.table(f"{SOURCE}.facilities")).toPandas()
fac.to_csv(f"{WORK}/facilities.csv", index=False)
pin = as_text(spark.table(f"{SOURCE}.india_post_pincode_directory")).toPandas()
half = len(pin) // 2
pin.iloc[:half].to_csv(f"{WORK}/indiaPincodeDirectory1.csv", index=False)
pin.iloc[half:].to_csv(f"{WORK}/indiaPincodeDirectory2.csv", index=False)
nfhs = as_text(spark.table(f"{SOURCE}.nfhs_5_district_health_indicators")).toPandas()
nfhs.to_csv(f"{WORK}/nfhs_5_district_health_indicators.csv", index=False)
print("facilities", fac.shape, "| PIN rows", len(pin), "| NFHS districts", len(nfhs))

# COMMAND ----------

# MAGIC %md ## 2. Run the pipeline
# MAGIC Each step is a plain Python script in `pipeline/`; the printed lines are its own checks.

# COMMAND ----------

STEPS = [
    ("pipeline/location.py",         "Where each facility really is: coordinates, postcode and city compared"),
    ("pipeline/claims.py",           "Sentences about each service; evidence tier per (facility, service)"),
    ("pipeline/feat_attribution.py", "Far-away towns named in the text"),
    ("pipeline/feat_sources.py",     "Whose websites each row was built from"),
    ("pipeline/trust.py",            "Fit the multipliers on labelled claims; score every claim"),
    ("pipeline/export_app.py",       "Pack the data the app needs"),
]
for script, what in STEPS:
    print(f"\n=== {script}: {what}")
    r = subprocess.run([sys.executable, script], cwd=WORK, capture_output=True, text=True)
    print("\n".join(l for l in r.stdout.splitlines() if "Warning" not in l)[-2500:])
    if r.returncode != 0:
        print(r.stderr[-3000:]); raise RuntimeError(f"{script} failed")
r = subprocess.run([sys.executable, "build.py"], cwd=f"{WORK}/app", capture_output=True, text=True); print(r.stdout, r.stderr[-500:])

# COMMAND ----------

# MAGIC %md ## 3. Save results as Delta tables

# COMMAND ----------

for name, path in [("sahi_trust", "pipeline/out/trust.csv"), ("sahi_claims", "pipeline/out/claims.csv"), ("sahi_location", "pipeline/out/location.csv")]:
    pdf = pd.read_csv(f"{WORK}/{path}", low_memory=False)
    spark.createDataFrame(pdf.astype(object).where(pdf.notna(), None).astype(str).replace({"None": None})).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{TARGET}.{name}")
    print(f"{TARGET}.{name}: {len(pdf):,} rows")

# COMMAND ----------

# MAGIC %md ## 4. Put the rebuilt app page back in the repository folder

# COMMAND ----------

for f in ["index.html", "data.json"]:
    shutil.copy(f"{WORK}/app/{f}", os.path.join(REPO, "app", f))
    print("updated", os.path.join(REPO, "app", f), round(os.path.getsize(os.path.join(REPO, "app", f)) / 1e6, 1), "MB")

# COMMAND ----------

# MAGIC %md ## 5. Look at the answer for one question
# MAGIC Dialysis claims in Patna, highest trust first, with the sentence each score rests on.

# COMMAND ----------

display(spark.sql(f"""
  SELECT name, address_city, round(cast(trust AS double), 1) AS trust, band, tier, coreq_found, coreq_total, quote_field, quote, reasons
  FROM {TARGET}.sahi_trust
  WHERE service = 'dialysis' AND lower(address_city) = 'patna'
  ORDER BY cast(trust AS double) DESC LIMIT 10
"""))
