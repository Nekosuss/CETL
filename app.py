"""
CETL Tool - a small online Cleansing, Extraction & Transformation tool.

Flow:
  /            upload a CSV (or use the bundled sample) -> run the ETL pipeline
  /results     shows raw vs. cleaned data + the cleansing/transformation log
  /database    browse the resulting SQLite database (raw_data & cleaned_data)
"""

import os
import sqlite3

import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash

from etl import run_pipeline, DB_PATH


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SAMPLE_FILE = os.path.join(BASE_DIR, "data", "sample_raw.csv")

app = Flask(__name__)
app.secret_key = "cetl-demo-secret"

os.makedirs(UPLOAD_DIR, exist_ok=True)

LAST_RUN = {}


@app.route("/", methods=["GET", "POST"])
def index():

    if request.method == "POST":

        use_sample = request.form.get("use_sample") == "on"

        # --------------------------------
        # Choose input CSV
        # --------------------------------
        if use_sample:
            source_path = SAMPLE_FILE

        else:
            file = request.files.get("csv_file")

            if not file or file.filename == "":
                flash("Please choose a CSV file, or check 'use sample data'.")
                return redirect(url_for("index"))

            if not file.filename.lower().endswith(".csv"):
                flash("Only .csv files are supported.")
                return redirect(url_for("index"))

            source_path = os.path.join(
                UPLOAD_DIR,
                file.filename
            )

            file.save(source_path)

        # --------------------------------
        # Run ETL pipeline
        # --------------------------------
        try:

            result = run_pipeline(
                source_path,
                db_path=os.path.join(BASE_DIR, DB_PATH)
            )

            LAST_RUN["raw_df"] = result["raw_df"]
            LAST_RUN["clean_df"] = result["clean_df"]
            LAST_RUN["cleanse_log"] = result["cleanse_log"]
            LAST_RUN["transform_log"] = result["transform_log"]
            LAST_RUN["source_name"] = os.path.basename(source_path)

            return redirect(url_for("results"))

        except Exception as e:

            # Show the actual error on the webpage instead of
            # crashing with a huge Flask traceback.
            flash(f"ETL pipeline failed: {type(e).__name__}: {e}")

            return redirect(url_for("index"))

    return render_template("index.html")


@app.route("/results")
def results():

    if "raw_df" not in LAST_RUN:
        flash("Run the ETL pipeline first.")
        return redirect(url_for("index"))

    raw_df = LAST_RUN["raw_df"]
    clean_df = LAST_RUN["clean_df"]

    return render_template(
        "result.html",

        source_name=LAST_RUN["source_name"],

        raw_columns=list(raw_df.columns),
        raw_rows=raw_df.fillna("").values.tolist(),
        raw_count=len(raw_df),

        clean_columns=list(clean_df.columns),
        clean_rows=clean_df.fillna("").values.tolist(),
        clean_count=len(clean_df),

        cleanse_log=LAST_RUN["cleanse_log"],
        transform_log=LAST_RUN["transform_log"],
    )


@app.route("/database")
def database():

    db_path = os.path.join(BASE_DIR, DB_PATH)

    if not os.path.exists(db_path):
        flash("No database yet — run the ETL pipeline first.")
        return redirect(url_for("index"))

    conn = sqlite3.connect(db_path)

    tables = {}

    for table_name in ("raw_data", "cleaned_data"):

        try:

            df = pd.read_sql_query(
                f"SELECT * FROM {table_name}",
                conn
            )

            tables[table_name] = {
                "columns": list(df.columns),
                "rows": df.fillna("").values.tolist(),
                "count": len(df),
            }

        except Exception:

            tables[table_name] = {
                "columns": [],
                "rows": [],
                "count": 0,
            }

    conn.close()

    return render_template(
        "database.html",
        db_path=db_path,
        tables=tables
    )


if __name__ == "__main__":
    app.run(
        debug=True,
        port=5000
    )