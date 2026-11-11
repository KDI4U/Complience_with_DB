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
DB_FOLDER = PROJECT_FOLDER / "data" / "db"

load_dotenv(ENV_FILE)

logger = logging.getLogger("insert_epfo_data")
if not logger.hasHandlers():
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "UrmilaHRMS_TEMP_NEW"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

INSERT_SQL = """
INSERT INTO "Compliance"."EPFOEmployeeDetails"
("UAN", "PFNo", "EmployeeName", "Gender", "DoB", "DoJ", "FatherHusbandName", "NameRelation", "MaritalStatus", "Mobile", "EmailId", "EPFOEmployerCode", "NominationFiled", "IsAadhaarVerified", "FaceAuthStatus", "IsActive", "CreatedDate")
VALUES %s
ON CONFLICT ("PFNo")
DO UPDATE SET
    "UAN" = EXCLUDED."UAN",
    "EmployeeName" = EXCLUDED."EmployeeName",
    "Gender" = EXCLUDED."Gender",
    "DoB" = EXCLUDED."DoB",
    "DoJ" = EXCLUDED."DoJ",
    "FatherHusbandName" = EXCLUDED."FatherHusbandName",
    "NameRelation" = EXCLUDED."NameRelation",
    "MaritalStatus" = EXCLUDED."MaritalStatus",
    "Mobile" = EXCLUDED."Mobile",
    "EmailId" = EXCLUDED."EmailId",
    "EPFOEmployerCode" = EXCLUDED."EPFOEmployerCode",
    "NominationFiled" = EXCLUDED."NominationFiled",
    "IsAadhaarVerified" = EXCLUDED."IsAadhaarVerified",
    "FaceAuthStatus" = EXCLUDED."FaceAuthStatus",
    "IsActive" = EXCLUDED."IsActive";
"""


def parse_date_value(val):
    """Parses date string or object into YYYY-MM-DD string."""
    if val is None or pd.isna(val):
        return None
    val_str = str(val).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null", "nat"]:
        return None

    # EPFO dates are typically '18-JUN-2000' or Indian formats
    for fmt in (
        "%d-%b-%Y", "%d-%B-%Y", "%d-%b-%y",
        "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y",
        "%Y-%m-%d", "%Y/%m/%d", "%d.%m.%y", "%d/%m/%y"
    ):
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


def clean_employee_name(name):
    """
    Cleans employee/relation name:
    Removes title prefixes (Mr., Ms., Mrs., Shri., Smt., Miss., Dr.),
    removes extra whitespace, BUT strictly keeps 'Md', 'Md.', or 'MD' intact.
    """
    if not name or pd.isna(name):
        return ""
    val_str = str(name).strip()
    if not val_str or val_str.lower() in ["nan", "none", "null"]:
        return ""
    pattern = r"^(?:Mr\.|Mr|Ms\.|Ms|Mrs\.|Mrs|Shri\.|Shri|Smt\.|Smt|Miss\.|Miss|Dr\.|Dr|Master\.|Master)\s+"
    cleaned = re.sub(pattern, "", val_str, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


def parse_boolean_value(val):
    """Parses string/boolean value to Python boolean (True/False)."""
    if val is None or pd.isna(val):
        return False
    val_str = str(val).strip().upper()
    if val_str in ["YES", "TRUE", "Y", "1"]:
        return True
    return False


def clean_contact_field(val):
    """Cleans phone or email field: turns 'NOT AVAILABLE' or 'NAN' into empty string."""
    if val is None or pd.isna(val):
        return ""
    val_str = str(val).strip()
    if not val_str or val_str.upper() in ["NOT AVAILABLE", "NOT_AVAILABLE", "N/A", "NA", "NAN", "NONE", "NULL"]:
        return ""
    return val_str


def find_merged_file():
    """
    Locates the merged file:
    Checks Merge_data/ first, then data/db/.
    """
    candidates = [
        MERGE_FOLDER / "merge sheet.xlsx",
        MERGE_FOLDER / "merge sheet.csv",
        MERGE_FOLDER / "All_Merge.xlsx",
        MERGE_FOLDER / "All_Merge.csv",
        DB_FOLDER / "All_Merge.xlsx",
        DB_FOLDER / "All_Merge.csv",
        DB_FOLDER / "merge sheet.xlsx",
        DB_FOLDER / "merge sheet.csv",
    ]

    for path in candidates:
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def insert_merged_data_to_db():
    logger.info("Starting High-Speed EPFO Employee Details PostgreSQL DB Insert...")

    # Validate DB Config
    missing_env = [key for key, val in DB_CONFIG.items() if not val]
    if missing_env:
        raise ValueError(f"Missing database configuration in .env: {', '.join(missing_env)}")

    source_file = find_merged_file()
    if not source_file:
        raise FileNotFoundError(
            f"Merge data file nahi mila in {MERGE_FOLDER} or {DB_FOLDER}. "
            "Kripya pehle Step 3 (Merge) chalayein taaki merge file generate ho."
        )

    logger.info(f"Reading merged file: {source_file.name} ({source_file})...")
    if source_file.suffix.lower() == ".csv":
        df = pd.read_csv(source_file, dtype=str)
    else:
        df = pd.read_excel(source_file, dtype=str, engine="openpyxl")

    logger.info(f"Loaded {len(df):,} rows from merged file.")

    # Normalize column names for flexible matching
    col_map = {}
    for col in df.columns:
        norm = re.sub(r"[^a-zA-Z0-9]", "", str(col)).lower()
        col_map[norm] = col

    def get_val(row, *aliases):
        for alias in aliases:
            norm_alias = re.sub(r"[^a-zA-Z0-9]", "", alias).lower()
            if norm_alias in col_map:
                actual_col = col_map[norm_alias]
                val = row.get(actual_col)
                if val is not None and not pd.isna(val):
                    return val
        return ""

    # Prepare, validate and deduplicate records
    records_dict = {}  # keyed by PFNo to avoid duplicates within same batch
    skipped_count = 0
    now_utc = datetime.now(timezone.utc)

    for idx, row in df.iterrows():
        raw_uan = str(get_val(row, "UAN", "uan")).strip()
        raw_pf = str(get_val(row, "PF NO", "PFNo", "PF_NO", "Member ID", "MemberID")).strip()

        # UAN must be exactly 12 digits (DB constraint CK_EPFOEmployeeDetails_UAN)
        uan = re.sub(r"\D", "", raw_uan)
        pf = raw_pf.strip()

        if len(uan) != 12:
            logger.debug(f"Row {idx}: Invalid UAN '{raw_uan}' (requires 12 digits). Skipped.")
            skipped_count += 1
            continue

        if not pf:
            logger.debug(f"Row {idx}: Empty PFNo. Skipped.")
            skipped_count += 1
            continue

        emp_name = clean_employee_name(get_val(row, "Employee Name", "EmployeeName", "Name"))
        if not emp_name:
            emp_name = "UNKNOWN"

        raw_gender = str(get_val(row, "Gender", "gender")).strip().upper()
        if raw_gender.startswith("F"):
            gender = "FEMALE"
        elif raw_gender.startswith("M"):
            gender = "MALE"
        else:
            gender = raw_gender or "MALE"

        dob = parse_date_value(get_val(row, "DoB", "Date of Birth", "DOB", "DateOfBirth"))
        doj = parse_date_value(get_val(row, "DoJ", "Date of Joining", "DOJ", "DateOfJoining"))

        father_husband_name = clean_employee_name(
            get_val(row, "Father's/Husband's Name", "FatherHusbandName", "Father's Name", "FatherName")
        )
        name_relation = str(get_val(row, "NameRelation", "Relation")).strip().upper()
        marital_status = str(get_val(row, "Marital Status", "MaritalStatus")).strip().upper()

        mobile = clean_contact_field(get_val(row, "Mobile", "MobileNo", "Mobile Number"))
        email_id = clean_contact_field(get_val(row, "Email ID", "EmailId", "Email"))

        employer_code = str(
            get_val(row, "EPFO Employer Code", "EPFOEmployerCode", "Est ID", "Establishment ID")
        ).strip()
        if not employer_code:
            # Fallback: extract establishment code from PFNo if possible
            match = re.match(r"^([A-Z]{5}\d{7})", pf)
            employer_code = match.group(1) if match else pf[:15]

        nomination_filed = parse_boolean_value(get_val(row, "Nomination Filed", "NominationFiled"))
        is_aadhaar_verified = parse_boolean_value(get_val(row, "Is AADHAAR Verified", "IsAadhaarVerified"))
        face_auth_status = parse_boolean_value(get_val(row, "Face Auth Status", "FaceAuthStatus"))

        record_tuple = (
            uan,
            pf,
            emp_name,
            gender,
            dob,
            doj,
            father_husband_name,
            name_relation,
            marital_status,
            mobile,
            email_id,
            employer_code,
            nomination_filed,
            is_aadhaar_verified,
            face_auth_status,
            True,     # IsActive
            now_utc,  # CreatedDate
        )

        # In-memory deduplication by PFNo
        records_dict[pf] = record_tuple

    records = list(records_dict.values())
    logger.info(f"Validated {len(records):,} unique records ready for insert ({skipped_count:,} skipped).")

    if not records:
        logger.warning("No valid records found to insert.")
        return True

    # Connect to PostgreSQL and execute multi-row batch upsert
    logger.info(f"Connecting to PostgreSQL ({DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']})...")
    conn = psycopg2.connect(**DB_CONFIG)

    try:
        cur = conn.cursor()

        # Ensure index matching fn_sync_epfo_employee_to_master trigger ON CONFLICT exists
        try:
            cur.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS "UX_EPFOMaster_UAN_NotDeleted"
                ON public."EPFOMaster" USING btree ("UAN")
                WHERE ("IsDeleted" = false);
            ''')
            conn.commit()
        except Exception as idx_err:
            conn.rollback()
            logger.warning(f"Index prerequisite check notice: {idx_err}")

        logger.info(
            f"Executing high-speed execute_values into \"Compliance\".\"EPFOEmployeeDetails\" ({len(records):,} rows)..."
        )
        execute_values(cur, INSERT_SQL, records, page_size=2000)
        conn.commit()

        # Check total rows in target table
        cur.execute('SELECT COUNT(*) FROM "Compliance"."EPFOEmployeeDetails";')
        total_in_db = cur.fetchone()[0]
        cur.close()

        logger.info(f"Successfully inserted/updated {len(records):,} records into \"Compliance\".\"EPFOEmployeeDetails\".")
        logger.info(f"Total records in table \"Compliance\".\"EPFOEmployeeDetails\": {total_in_db:,}")
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

