"""
Core ETL engine:
Extraction -> Cleansing -> Transformation -> Loading

Designed for the Messy Employee Dataset.
"""

import re
import sqlite3
from datetime import datetime

import pandas as pd


DB_PATH = "cetl.db"


# ---------------------------------------------------------
# EMAIL VALIDATION
# ---------------------------------------------------------

EMAIL_RE = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)


# ---------------------------------------------------------
# EXTRACTION
# ---------------------------------------------------------

def extract(file_path: str) -> pd.DataFrame:
    """
    Read the CSV exactly as provided.
    """

    df = pd.read_csv(
        file_path,
        dtype=str,
        keep_default_na=False
    )

    # Convert empty strings / whitespace-only strings to NA
    df = df.replace(
        r"^\s*$",
        pd.NA,
        regex=True
    )

    return df


# ---------------------------------------------------------
# DATE PARSING
# ---------------------------------------------------------

def _parse_date(value):

    if pd.isna(value):
        return None

    value = str(value).strip()

    formats = [
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%d-%m-%Y",
    ]

    for fmt in formats:

        try:
            return datetime.strptime(
                value,
                fmt
            ).strftime("%Y-%m-%d")

        except ValueError:
            continue

    return None


# ---------------------------------------------------------
# PHONE NORMALIZATION
# ---------------------------------------------------------

def _normalize_phone(value):

    if pd.isna(value):
        return None

    digits = re.sub(
        r"\D",
        "",
        str(value)
    )

    # Keep last 10 digits if country code is present
    if len(digits) > 10:
        digits = digits[-10:]

    if len(digits) != 10:
        return None

    return (
        f"({digits[0:3]}) "
        f"{digits[3:6]}-"
        f"{digits[6:10]}"
    )


# ---------------------------------------------------------
# CLEANSING
# ---------------------------------------------------------

def cleanse(df: pd.DataFrame):

    """
    Clean the messy employee dataset.

    Returns:
        clean_df
        cleanse_log
    """

    log = []

    df = df.copy()

    start_rows = len(df)

    # -----------------------------------------------------
    # 1. TRIM WHITESPACE
    # -----------------------------------------------------

    text_cols = list(df.columns)

    for col in text_cols:

        df[col] = df[col].apply(
            lambda v:
                v.strip()
                if isinstance(v, str)
                else v
        )

    log.append(
        f"Trimmed leading/trailing whitespace "
        f"on {len(text_cols)} columns."
    )

    # -----------------------------------------------------
    # 2. NORMALIZE COLUMN NAMES
    # -----------------------------------------------------

    df.columns = [
        c.strip().replace(" ", "_")
        for c in df.columns
    ]

    # -----------------------------------------------------
    # 3. STANDARDIZE NAMES
    # -----------------------------------------------------

    for col in ("First_Name", "Last_Name"):

        if col in df.columns:

            df[col] = df[col].apply(
                lambda v:
                    v.title()
                    if isinstance(v, str)
                    else v
            )

    log.append(
        "Standardized First_Name and Last_Name capitalization."
    )

    # -----------------------------------------------------
    # 4. SPLIT DEPARTMENT_REGION
    # -----------------------------------------------------

    if "Department_Region" in df.columns:

        split_values = (
            df["Department_Region"]
            .astype("string")
            .str.split("-", n=1, expand=True)
        )

        df["Department"] = split_values[0].str.strip()

        if split_values.shape[1] > 1:
            df["Region"] = split_values[1].str.strip()
        else:
            df["Region"] = pd.NA

        log.append(
            "Split Department_Region into Department and Region."
        )

    # -----------------------------------------------------
    # 5. EMAIL VALIDATION
    # -----------------------------------------------------

    if "Email" in df.columns:

        before_invalid = df["Email"].apply(
            lambda v:
                isinstance(v, str)
                and not EMAIL_RE.match(v)
        ).sum()

        df["Email"] = df["Email"].apply(
            lambda v:
                v.lower().strip()
                if isinstance(v, str)
                and EMAIL_RE.match(v)
                else pd.NA
        )

        if before_invalid:

            log.append(
                f"Flagged {before_invalid} malformed "
                f"email address(es) as missing."
            )

    # -----------------------------------------------------
    # 6. PHONE NORMALIZATION
    # -----------------------------------------------------

    if "Phone" in df.columns:

        bad_phones = df["Phone"].apply(
            lambda v:
                _normalize_phone(v) is None
                and not pd.isna(v)
        ).sum()

        df["Phone"] = df["Phone"].apply(
            _normalize_phone
        )

        if bad_phones:

            log.append(
                f"Reformatted phone numbers; "
                f"{bad_phones} unusable number(s) cleared."
            )

    # -----------------------------------------------------
    # 7. AGE
    # -----------------------------------------------------

    if "Age" in df.columns:

        df["Age"] = pd.to_numeric(
            df["Age"],
            errors="coerce"
        )

        invalid_age_mask = (
            df["Age"].notna()
            &
            (
                (df["Age"] < 0)
                |
                (df["Age"] > 120)
            )
        )

        invalid_age_count = invalid_age_mask.sum()

        df.loc[
            invalid_age_mask,
            "Age"
        ] = pd.NA

        if invalid_age_count:

            log.append(
                f"Cleared {invalid_age_count} "
                f"out-of-range Age value(s)."
            )

        median_age = df["Age"].median()

        missing_age = df["Age"].isna().sum()

        if pd.notna(median_age):

            df["Age"] = df["Age"].fillna(
                median_age
            )

            df["Age"] = df["Age"].round().astype(int)

        if missing_age:

            log.append(
                f"Imputed {missing_age} missing Age "
                f"value(s) with the column median "
                f"({median_age:.0f})."
            )

    # -----------------------------------------------------
    # 8. JOIN DATE
    # -----------------------------------------------------

    if "Join_Date" in df.columns:

        invalid_dates = df["Join_Date"].apply(
            lambda v:
                _parse_date(v) is None
                and not pd.isna(v)
        ).sum()

        df["Join_Date"] = df["Join_Date"].apply(
            _parse_date
        )

        if invalid_dates:

            log.append(
                f"Standardized Join_Date to YYYY-MM-DD; "
                f"{invalid_dates} unparseable date(s) cleared."
            )

    # -----------------------------------------------------
    # 9. SALARY
    # -----------------------------------------------------

    if "Salary" in df.columns:

        df["Salary"] = pd.to_numeric(
            df["Salary"],
            errors="coerce"
        )

        missing_salary = df["Salary"].isna().sum()

        mean_salary = df["Salary"].mean()

        if pd.notna(mean_salary):

            df["Salary"] = df["Salary"].fillna(
                round(mean_salary, 2)
            )

        if missing_salary:

            log.append(
                f"Imputed {missing_salary} missing Salary "
                f"value(s) with the column mean "
                f"({mean_salary:.2f})."
            )

    # -----------------------------------------------------
    # 10. REMOVE DUPLICATES
    # -----------------------------------------------------

    if "Employee_ID" in df.columns:

        dup_mask = df.duplicated(
            subset=["Employee_ID"],
            keep="first"
        )

        dup_count = dup_mask.sum()

        df = df[
            ~dup_mask
        ].reset_index(drop=True)

        if dup_count:

            log.append(
                f"Removed {dup_count} duplicate "
                f"employee record(s)."
            )

    else:

        duplicate_count = df.duplicated().sum()

        df = df.drop_duplicates().reset_index(
            drop=True
        )

        if duplicate_count:

            log.append(
                f"Removed {duplicate_count} "
                f"duplicate row(s)."
            )

    # -----------------------------------------------------
    # FINAL LOG
    # -----------------------------------------------------

    log.append(
        f"Row count: {start_rows} -> {len(df)} "
        f"after cleansing."
    )

    return df, log


# ---------------------------------------------------------
# TRANSFORMATION
# ---------------------------------------------------------

def transform(df: pd.DataFrame):

    """
    Transformation stage.

    Creates useful derived columns and
    standardizes the final schema.
    """

    df = df.copy()

    log = []

    # -----------------------------------------------------
    # FULL NAME
    # -----------------------------------------------------

    if (
        "First_Name" in df.columns
        and
        "Last_Name" in df.columns
    ):

        df["Full_Name"] = (
            df["First_Name"].fillna("")
            + " "
            + df["Last_Name"].fillna("")
        ).str.strip()

        log.append(
            "Derived Full_Name from First_Name + Last_Name."
        )

    # -----------------------------------------------------
    # AGE GROUP
    # -----------------------------------------------------

    if "Age" in df.columns:

        bins = [
            0,
            17,
            30,
            45,
            60,
            200
        ]

        labels = [
            "Under 18",
            "18-30",
            "31-45",
            "46-60",
            "60+"
        ]

        df["Age_Group"] = pd.cut(
            df["Age"],
            bins=bins,
            labels=labels,
            right=True
        ).astype(str)

        log.append(
            "Derived Age_Group from Age."
        )

    # -----------------------------------------------------
    # EMAIL DOMAIN
    # -----------------------------------------------------

    if "Email" in df.columns:

        df["Email_Domain"] = (
            df["Email"]
            .astype("string")
            .str.split("@")
            .str[-1]
        )

        log.append(
            "Derived Email_Domain from Email."
        )

    # -----------------------------------------------------
    # SALARY TIER
    # -----------------------------------------------------

    if "Salary" in df.columns:

        df["Salary_Tier"] = pd.cut(
            df["Salary"],
            bins=[
                -0.01,
                40000,
                80000,
                float("inf")
            ],
            labels=[
                "Low",
                "Medium",
                "High"
            ]
        ).astype(str)

        log.append(
            "Derived Salary_Tier from Salary."
        )

    # -----------------------------------------------------
    # STANDARDIZE COLUMN ORDER
    # -----------------------------------------------------

    preferred_order = [
        "Employee_ID",
        "Full_Name",
        "First_Name",
        "Last_Name",
        "Department",
        "Region",
        "Status",
        "Join_Date",
        "Age",
        "Age_Group",
        "Salary",
        "Salary_Tier",
        "Email",
        "Email_Domain",
        "Phone",
        "Performance_Score",
        "Remote_Work",
    ]

    ordered = [
        col
        for col in preferred_order
        if col in df.columns
    ]

    remaining = [
        col
        for col in df.columns
        if col not in ordered
    ]

    df = df[
        ordered + remaining
    ]

    log.append(
        "Reordered and standardized final column schema."
    )

    return df, log


# ---------------------------------------------------------
# LOAD
# ---------------------------------------------------------

def load(
    raw_df: pd.DataFrame,
    clean_df: pd.DataFrame,
    db_path: str = DB_PATH
):

    """
    Load raw and cleaned datasets into SQLite.
    """

    conn = sqlite3.connect(db_path)

    try:

        raw_df.to_sql(
            "raw_data",
            conn,
            if_exists="replace",
            index=False
        )

        clean_df.to_sql(
            "cleaned_data",
            conn,
            if_exists="replace",
            index=False
        )

        conn.commit()

    finally:

        conn.close()


# ---------------------------------------------------------
# COMPLETE PIPELINE
# ---------------------------------------------------------

def run_pipeline(
    file_path: str,
    db_path: str = DB_PATH
):

    """
    Runs:

        Extract
            ↓
        Cleanse
            ↓
        Transform
            ↓
        Load
    """

    raw_df = extract(file_path)

    clean_df, cleanse_log = cleanse(
        raw_df
    )

    final_df, transform_log = transform(
        clean_df
    )

    load(
        raw_df,
        final_df,
        db_path=db_path
    )

    return {
        "raw_df": raw_df,
        "clean_df": final_df,
        "cleanse_log": cleanse_log,
        "transform_log": transform_log,
    }