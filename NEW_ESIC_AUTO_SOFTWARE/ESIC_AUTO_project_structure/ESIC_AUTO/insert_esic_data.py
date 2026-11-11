import os
import sys
import re
import logging
from pathlib import Path
from datetime import datetime, timezone
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Configure Windows console encoding safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
# PATH SETTINGS - DYNAMIC ABSOLUTE PATHS
# ============================================================
if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent
ENV_FILE = PROJECT_FOLDER / ".env"
MERGE_FOLDER = PROJECT_FOLDER / "Merge_data"
MERGE_XLSX = MERGE_FOLDER / "merge sheet.xlsx"
MERGE_CSV = MERGE_FOLDER / "merge sheet.csv"

load_dotenv(ENV_FILE)

logger = logging.getLogger("insert_esic_data")
if not logger.hasHandlers():
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

INSERT_SQL = """
INSERT INTO "Compliance"."ESICEmployeeDetails"
("IPNumber", "ESICEmployerCode", "EmployeeName", "Gender", "DoB", "DoJ", "FatherHusbandName", "NameRelation", "MaritalStatus", "Mobile", "EmailId", "IsAadhaarVerified", "IsActive", "CreatedDate")
VALUES %s
ON CONFLICT ("ESICEmployerCode", "IPNumber")
DO UPDATE SET
    "EmployeeName" = EXCLUDED."EmployeeName",
    "Gender" = EXCLUDED."Gender",
    "DoB" = EXCLUDED."DoB",
    "DoJ" = EXCLUDED."DoJ",
    "IsActive" = EXCLUDED."IsActive";
"""


def parse_date_value(val):
    """Parses date string or object into YYYY-MM-DD string."""
    if val is None or pd.isna(val):
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null", "nat"]:
        return None

    # Common Indian date formats
    for fmt in ("%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%y", "%d/%m/%y"):
        try:
            return datetime.strptime(val_str, fmt).strftime("%Y-%m-%d")
        except Exception:
            pass

    try:
        dt = pd.to_datetime(val_str, dayfirst=True)
        if not pd.isna(dt):
            return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    return None


def clean_employee_name(val):
    """Removes honorific prefixes like 'Md.', 'md.', 'MD.' etc."""
    if val is None or pd.isna(val):
        return ""
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null"]:
        return ""
    cleaned = re.sub(r"(?i)\bmd\s*\.\s*", "", val_str)
    return " ".join(cleaned.split()).strip()


def normalize_gender(val):
    """Normalizes gender value to 'M' or 'F'."""
    if val is None or pd.isna(val):
        return "M"
    val_str = str(val).strip().upper()
    if val_str.startswith("F"):
        return "F"
    return "M"


def find_merged_file():
    """Locates the merged file strictly inside the Merge_data folder."""
    if MERGE_XLSX.exists() and MERGE_XLSX.stat().st_size > 0:
        return MERGE_XLSX
    if MERGE_CSV.exists() and MERGE_CSV.stat().st_size > 0:
        return MERGE_CSV
    return None


def insert_merged_data_to_db():
    logger.info("Starting High-Speed ESIC Employee Details PostgreSQL DB Insert...")

    # Validate DB Config
    missing_env = [key for key, val in DB_CONFIG.items() if not val]
    if missing_env:
        raise ValueError(f"Missing database configuration in .env: {', '.join(missing_env)}")

    # Locate merged input file strictly in Merge_data
    source_file = find_merged_file()
    if not source_file:
        raise FileNotFoundError(
            f"Merge data file nahi mila: {MERGE_XLSX}. "
            "Sirf 'Merge_data/merge sheet.xlsx' ka data insert hoga. "
            "Kripya pehle Step 3 (Merge) chalayein taaki 'Merge_data/merge sheet.xlsx' generate ho."
        )

    logger.info(f"Reading merged file directly from Merge_data: {source_file.name} ({source_file})...")
    if source_file.suffix.lower() == ".csv":
        df = pd.read_csv(source_file, dtype=str)
    else:
        df = pd.read_excel(source_file, dtype=str, engine="openpyxl")

    logger.info(f"Loaded {len(df):,} rows from merged file.")

    # Prepare and validate records
    records = []
    skipped_count = 0
    now_utc = datetime.now(timezone.utc)

    for idx, row in df.iterrows():
        raw_ip = str(row.get("IPNumber", "")).strip()
        raw_code = str(row.get("ESICEmployerCode", "")).strip()

        # Extract only digits
        ip = re.sub(r"\D", "", raw_ip)
        code = re.sub(r"\D", "", raw_code)

        name = clean_employee_name(row.get("EmployeeName", ""))
        gender = normalize_gender(row.get("Gender", "M"))
        dob = parse_date_value(row.get("DateofBirth", ""))
        doj = parse_date_value(row.get("DateofAppointment", ""))

        # Validation against DB Check constraints:
        # IPNumber: ^[0-9]{10}$
        # ESICEmployerCode: ^[0-9]{17}$
        if len(ip) != 10:
            logger.debug(f"Row {idx}: Invalid IPNumber '{raw_ip}' (requires 10 digits). Skipped.")
            skipped_count += 1
            continue

        if len(code) != 17:
            logger.debug(f"Row {idx}: Invalid ESICEmployerCode '{raw_code}' (requires 17 digits). Skipped.")
            skipped_count += 1
            continue

        if not dob:
            logger.warning(f"Row {idx} (IP: {ip}): Invalid or missing DateofBirth '{row.get('DateofBirth')}'. Skipped.")
            skipped_count += 1
            continue

        if not doj:
            logger.warning(f"Row {idx} (IP: {ip}): Invalid or missing DateofAppointment '{row.get('DateofAppointment')}'. Skipped.")
            skipped_count += 1
            continue

        records.append((
            ip,
            code,
            name,
            gender,
            dob,
            doj,
            "",       # FatherHusbandName
            "",       # NameRelation
            "",       # MaritalStatus
            "",       # Mobile
            "",       # EmailId
            False,    # IsAadhaarVerified
            True,     # IsActive
            now_utc,  # CreatedDate
        ))

    logger.info(f"Validated {len(records):,} records ready for insert ({skipped_count:,} skipped).")

    if not records:
        logger.warning("No valid records found to insert.")
        return True

    # Connect to PostgreSQL and execute multi-row batch upsert
    logger.info(f"Connecting to PostgreSQL ({DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']})...")
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()
        logger.info(f"Executing high-speed execute_values into \"Compliance\".\"ESICEmployeeDetails\" ({len(records):,} rows)...")
        execute_values(cur, INSERT_SQL, records, page_size=2000)
        conn.commit()

        # Check total rows in target table
        cur.execute('SELECT COUNT(*) FROM "Compliance"."ESICEmployeeDetails";')
        total_in_db = cur.fetchone()[0]
        cur.close()

        logger.info(f"Successfully inserted/updated {len(records):,} records into \"Compliance\".\"ESICEmployeeDetails\".")
        logger.info(f"Total records in table \"Compliance\".\"ESICEmployeeDetails\": {total_in_db:,}")
        return True
    except Exception as exc:
        conn.rollback()
        logger.error(f"Database insert failed: {exc}", exc_info=True)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        insert_merged_data_to_db()
    except Exception as e:
        logger.error(f"Process failed: {e}")
        sys.exit(1)
