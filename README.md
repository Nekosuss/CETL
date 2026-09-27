# CETL — Cleansing, Extraction & Transformation Tool

A small online (browser-based) tool that demonstrates a full ETL pipeline:
upload a raw/messy CSV, and the tool **extracts**, **cleanses**, and
**transforms** it, then **loads** the result into a SQLite database — with
a before/after view of both the data and the database.

## Architecture

```
Browser (upload form) --> Flask app.py --> etl.py pipeline --> cetl.db (SQLite)
                                                 |
                                 extract -> cleanse -> transform -> load
```

- **Extraction** (`etl.extract`) — reads the source CSV as-is.
- **Cleansing** (`etl.cleanse`) — trims whitespace, standardizes casing,
  validates emails/phone numbers, coerces and bounds-checks Age, imputes
  missing numeric values, standardizes date formats, drops rows with an
  unrecoverable required field, and removes duplicate records. Every
  action is recorded in a log for the demo.
- **Transformation** (`etl.transform`) — derives new columns (`Full Name`,
  `Age Group`, `Email Domain`, `Purchase Tier`) and standardizes the
  output schema.
- **Load** (`etl.load`) — writes both the raw extract (`raw_data` table)
  and the cleaned/transformed result (`cleaned_data` table) into a SQLite
  database (`cetl.db`), so the before/after state can be inspected
  directly from the database.

## Running it

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000 in a browser.

1. **Home** — upload your own CSV, or tick "use bundled sample dataset"
   (`data/sample_raw.csv`, 12 intentionally messy customer records) and
   click "Run ETL Pipeline".
2. **Results** — see the cleansing/transformation log plus the raw data
   and cleaned data tables side by side.
3. **Database** — browse the actual SQLite tables (`raw_data` and
   `cleaned_data`) that were written to `cetl.db`, demonstrating the
   database state after cleaning.

## Sample dataset data-quality issues (by design)

- Leading/trailing whitespace, inconsistent name casing
- Exact duplicate record and a case-only duplicate
- Invalid email address (no domain) and blank emails
- Malformed / missing phone numbers
- Out-of-range ages (negative, > 120) and missing ages
- Missing purchase amounts
- Inconsistent date formats and one unparseable date

Each of these is fixed (or the row is intentionally dropped, when a
required field can't be recovered) by the cleansing stage, and the log
on the Results page explains exactly what was done.

## Project structure

```
app.py                 Flask web app (routes: /, /results, /database)
etl.py                 Extraction / cleansing / transformation / load logic
data/sample_raw.csv    Bundled messy sample dataset
templates/             HTML pages
static/style.css       Styling
cetl.db                SQLite database (created after first run)
```
