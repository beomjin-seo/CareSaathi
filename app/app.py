"""Databricks App: serves the single-page finder. All scoring is precomputed by the pipeline; the page only filters and ranks."""
import os
from flask import Flask, send_from_directory
HERE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(HERE, "index.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", os.environ.get("PORT", 8000))))
