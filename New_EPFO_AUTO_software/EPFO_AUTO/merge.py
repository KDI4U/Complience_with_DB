import sys
import re
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd

# =========================================================
# PATH SETTINGS - FULL ABSOLUTE PATHS
# =========================================================
if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent
DATA_FOLDER = PROJECT_FOLDER / "data"
PF_DOWNLOADS_FOLDER = DATA_FOLDER / "pf_downloads"
MERGE_FOLDER = PROJECT_FOLDER / "Merge_data"
DB_FOLDER = DATA_FOLDER / "db"

MERGE_FOLDER.mkdir(parents=True, exist_ok=True)
DB_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_MERGE_XLSX = MERGE_FOLDER / "merge sheet.xlsx"
OUTPUT_MERGE_CSV = MERGE_FOLDER / "merge sheet.csv"
OUTPUT_DB_XLSX = DB_FOLDER / "All_Merge.xlsx"
OUTPUT_DB_CSV = DB_FOLDER / "All_Merge.csv"

logger = logging.getLogger("merge_data")
if not logger.hasHandlers():
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)

TARGET_HEADERS = [
    "UAN",
    "PF NO",
    "Employee Name",
    "Gender",
    "DoB",
    "DoJ",
    "Father's/Husband's Name",
    "NameRelation",
    "Marital Status",
    "Mobile",
    "Email ID",
    "EPFO Employer Code",
    "Nomination Filed",
    "Is AADHAAR Verified",
    "Face Auth Status",
]


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


def find_download_files():
    """Finds all CSV and Excel files in today's or recent download directories."""
    files = []
    today_str = datetime.now().strftime("%d%m%Y")
    today_dir = PF_DOWNLOADS_FOLDER / today_str

    search_dirs = []
    if today_dir.exists():
        search_dirs.append(today_dir)

    if PF_DOWNLOADS_FOLDER.exists():
        for d in sorted(PF_DOWNLOADS_FOLDER.iterdir(), reverse=True):
            if d.is_dir() and d not in search_dirs:
                search_dirs.append(d)

    for s_dir in search_dirs:
        for f in s_dir.glob("*.*"):
            if f.suffix.lower() in [".csv", ".xlsx", ".xls"]:
                if f.name.lower() not in ["all_merge.csv", "all_merge.xlsx", "merge sheet.csv", "merge sheet.xlsx"]:
                    files.append(f)
        if files:
            logger.info(f"Using download directory: {s_dir} (found {len(files)} files)")
            break

    return files


def read_data_file(file_path):
    suffix = file_path.suffix.lower()
    try:
        if suffix == ".csv":
            try:
                return pd.read_csv(file_path, dtype=str, encoding="utf-8")
            except UnicodeDecodeError:
                return pd.read_csv(file_path, dtype=str, encoding="cp1252")
        elif suffix in [".xlsx", ".xls"]:
            return pd.read_excel(file_path, dtype=str, engine="openpyxl" if suffix == ".xlsx" else None)
    except Exception as e:
        logger.error(f"Error reading file {file_path.name}: {e}")
        return None
    return None


def merge_epfo_files():
    logger.info("Starting EPFO Downloaded Files Merge...")

    files = find_download_files()
    if not files:
        # Check if All_Merge.csv already exists in DB folder
        if OUTPUT_DB_CSV.exists() and OUTPUT_DB_CSV.stat().st_size > 0:
            logger.info(f"No individual download files found, but existing merged file found: {OUTPUT_DB_CSV.name}")
            df_existing = read_data_file(OUTPUT_DB_CSV)
            if df_existing is not None and not df_existing.empty:
                # Copy to merge sheet outputs
                df_existing.to_excel(OUTPUT_MERGE_XLSX, index=False, engine="openpyxl")
                df_existing.to_csv(OUTPUT_MERGE_CSV, index=False, encoding="utf-8")
                logger.info(f"Synchronized {len(df_existing):,} rows to {OUTPUT_MERGE_XLSX.name} and {OUTPUT_MERGE_CSV.name}")
                return True
        raise FileNotFoundError(f"No downloaded files found to merge in {PF_DOWNLOADS_FOLDER}")

    logger.info(f"Found {len(files)} files to merge.")
    merged_rows = []

    for f in files:
        df = read_data_file(f)
        if df is None or df.empty:
            continue

        # Column mapping
        col_map = {re.sub(r"[^a-zA-Z0-9]", "", str(c)).lower(): c for c in df.columns}

        def get_v(row, *aliases):
            for a in aliases:
                norm_a = re.sub(r"[^a-zA-Z0-9]", "", a).lower()
                if norm_a in col_map:
                    v = row.get(col_map[norm_a])
                    if v is not None and not pd.isna(v):
                        return str(v).strip()
            return ""

        for _, row in df.iterrows():
            uan = re.sub(r"\D", "", get_v(row, "UAN", "uan"))
            pf = get_v(row, "PF NO", "PFNo", "PF_NO", "Member ID", "MemberID")
            emp_name = clean_employee_name(get_v(row, "Employee Name", "EmployeeName", "Name"))
            gender = get_v(row, "Gender", "gender").upper()
            dob = get_v(row, "DoB", "Date of Birth", "DOB", "DateOfBirth")
            doj = get_v(row, "DoJ", "Date of Joining", "DOJ", "DateOfJoining")
            father = clean_employee_name(
                get_v(row, "Father's/Husband's Name", "FatherHusbandName", "Father's Name", "FatherName")
            )
            rel = get_v(row, "NameRelation", "Relation").upper()
            marital = get_v(row, "Marital Status", "MaritalStatus").upper()
            mobile = get_v(row, "Mobile", "MobileNo")
            email = get_v(row, "Email ID", "EmailId", "Email")
            code = get_v(row, "EPFO Employer Code", "EPFOEmployerCode", "Est ID")
            if not code:
                # Infer from filename or PF
                match = re.search(r"([A-Z]{5}\d{7})", f.stem)
                code = match.group(1) if match else f.stem[:15]

            nom = get_v(row, "Nomination Filed", "NominationFiled").upper()
            aadhaar = get_v(row, "Is AADHAAR Verified", "IsAadhaarVerified").upper()
            face = get_v(row, "Face Auth Status", "FaceAuthStatus").upper()

            merged_rows.append({
                "UAN": uan,
                "PF NO": pf,
                "Employee Name": emp_name,
                "Gender": gender,
                "DoB": dob,
                "DoJ": doj,
                "Father's/Husband's Name": father,
                "NameRelation": rel,
                "Marital Status": marital,
                "Mobile": mobile,
                "Email ID": email,
                "EPFO Employer Code": code,
                "Nomination Filed": nom,
                "Is AADHAAR Verified": aadhaar,
                "Face Auth Status": face,
            })

    if not merged_rows:
        logger.warning("No records extracted from files.")
        return False

    final_df = pd.DataFrame(merged_rows)
    logger.info(f"Total merged records: {len(final_df):,}")

    # Save to Merge_data folder
    final_df.to_excel(OUTPUT_MERGE_XLSX, index=False, engine="openpyxl")
    final_df.to_csv(OUTPUT_MERGE_CSV, index=False, encoding="utf-8")
    logger.info(f"Saved: {OUTPUT_MERGE_XLSX.name} and {OUTPUT_MERGE_CSV.name} in {MERGE_FOLDER}")

    # Also save to data/db folder for full compatibility
    final_df.to_excel(OUTPUT_DB_XLSX, index=False, engine="openpyxl")
    final_df.to_csv(OUTPUT_DB_CSV, index=False, encoding="utf-8")
    logger.info(f"Saved: {OUTPUT_DB_XLSX.name} and {OUTPUT_DB_CSV.name} in {DB_FOLDER}")

    return True


if __name__ == "__main__":
    try:
        merge_epfo_files()
    except Exception as exc:
        logger.error(f"Merge failed: {exc}")
        sys.exit(1)

