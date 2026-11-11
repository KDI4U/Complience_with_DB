import os
import re
import sys
import csv
import time
import zipfile
import logging
from datetime import datetime
from pathlib import Path
import psycopg2
from dotenv import load_dotenv
import ollama
from openpyxl import load_workbook
from playwright.sync_api import sync_playwright

# Configure Windows console encoding safely
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ============================================================
# PATHS & CONFIGURATION
# ============================================================
if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent

ENV_FILE = PROJECT_FOLDER / ".env"
load_dotenv(ENV_FILE)

# Set Playwright bundled browser path if present
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    bundled_browser = PROJECT_FOLDER / "ms-playwright"
    if bundled_browser.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browser)

DATA_FOLDER = PROJECT_FOLDER / "data"
CAPTCHA_FOLDER = DATA_FOLDER / "captcha_images"
PF_DOWNLOADS_FOLDER = DATA_FOLDER / "pf_downloads"
DATE_FOLDER_NAME = datetime.now().strftime("%d%m%Y")
TARGET_DOWNLOAD_DIR = PF_DOWNLOADS_FOLDER / DATE_FOLDER_NAME

EXCEL_FILE = DATA_FOLDER / "users.xlsx"
if not EXCEL_FILE.exists():
    _fallback_excel = PROJECT_FOLDER / "users.xlsx"
    if _fallback_excel.exists():
        EXCEL_FILE = _fallback_excel

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT", "5432"),
    "dbname": os.getenv("DB_NAME", "UrmilaHRMS_TEMP_NEW"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
}

OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:4b")
MAX_RETRIES_PER_USER = 3
LOGIN_URL = "https://unifiedportal-emp.epfindia.gov.in/epfo/"

# Create required directories
CAPTCHA_FOLDER.mkdir(parents=True, exist_ok=True)
TARGET_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("epfo_portal")
if not logger.hasHandlers():
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S"))
    logger.addHandler(ch)
    logger.setLevel(logging.INFO)


# ============================================================
# DATABASE LOGGING FUNCTIONS FOR "Compliance"."PortalDownloadLog"
# ============================================================

def log_download_start(credential_id):
    """Inserts/registers a download session in Compliance.PortalDownloadLog with IN_PROGRESS status."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT "Id" FROM "Compliance"."PortalDownloadLog"
            WHERE "PortalLoginCredentialId" = %s AND "RunDate" = CURRENT_DATE AND "DownloadStatus" = 'IN_PROGRESS'
            ORDER BY "Id" DESC LIMIT 1;
        """, (credential_id,))
        row = cur.fetchone()
        if row:
            log_id = row[0]
            cur.execute("""
                UPDATE "Compliance"."PortalDownloadLog"
                SET "StartedAt" = CURRENT_TIMESTAMP
                WHERE "Id" = %s;
            """, (log_id,))
        else:
            cur.execute("""
                INSERT INTO "Compliance"."PortalDownloadLog"
                ("PortalLoginCredentialId", "DownloadStatus", "StartedAt", "RunDate", "RunSlot")
                VALUES (%s, 'IN_PROGRESS', CURRENT_TIMESTAMP, CURRENT_DATE, 1)
                RETURNING "Id";
            """, (credential_id,))
            log_id = cur.fetchone()[0]

        conn.commit()
        cur.close()
        conn.close()
        return log_id
    except Exception as e:
        logger.warning(f"Could not log start in PortalDownloadLog for Credential {credential_id}: {e}")
        return None


def log_download_success(log_id, filename):
    """Updates Compliance.PortalDownloadLog to SUCCESS with completed timestamp and filename."""
    if not log_id:
        return
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE "Compliance"."PortalDownloadLog"
            SET "DownloadStatus" = 'SUCCESS',
                "CompletedAt" = CURRENT_TIMESTAMP,
                "FileName" = %s,
                "ErrorMessage" = NULL
            WHERE "Id" = %s;
        """, (filename, log_id))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Updated PortalDownloadLog (ID={log_id}) -> SUCCESS ({filename})")
    except Exception as e:
        logger.warning(f"Could not update PortalDownloadLog for success (log ID={log_id}): {e}")


def log_download_failure(log_id, error_message):
    """Updates Compliance.PortalDownloadLog to FAILED with error message."""
    if not log_id:
        return
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            UPDATE "Compliance"."PortalDownloadLog"
            SET "DownloadStatus" = 'FAILED',
                "CompletedAt" = CURRENT_TIMESTAMP,
                "ErrorMessage" = %s
            WHERE "Id" = %s;
        """, (str(error_message)[:1000], log_id))
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Updated PortalDownloadLog (ID={log_id}) -> FAILED ({str(error_message)[:80]})")
    except Exception as e:
        logger.warning(f"Could not update PortalDownloadLog for failure (log ID={log_id}): {e}")


# ============================================================
# DATA CLEANING & CAPTCHA HELPERS
# ============================================================

def clean_excel_val(val):
    if val is None:
        return ""
    if isinstance(val, float):
        return f"{int(val)}"
    if isinstance(val, int):
        return str(val)

    val_str = str(val).strip()
    if val_str.endswith(".0"):
        val_str = val_str[:-2]
    if re.search(r"^\d+\.?\d*[eE]\+\d+$", val_str):
        try:
            return f"{int(float(val_str))}"
        except Exception:
            pass
    return val_str


def clean_employee_name(name):
    """
    Removes title prefixes (Mr., Ms., Mrs., Shri., Smt., Miss., Dr.),
    removes extra whitespace, BUT strictly keeps 'Md', 'Md.', or 'MD' intact.
    """
    if not name:
        return ""
    cleaned = str(name).strip()
    pattern = r"^(?:Mr\.|Mr|Ms\.|Ms|Mrs\.|Mrs|Shri\.|Shri|Smt\.|Smt|Miss\.|Miss|Dr\.|Dr|Master\.|Master)\s+"
    cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def fix_captcha_pattern(raw_text):
    """
    Cleans and formats CAPTCHA:
    - 1st & 2nd characters: 2 UPPERCASE letters (e.g. AB)
    - 3rd & 4th characters: 2 LOWERCASE letters (e.g. cd)
    - 5th character: 1 NUMERIC DIGIT (e.g. 1)
    """
    if not raw_text:
        return ""

    cleaned = re.sub(r"[^a-zA-Z0-9]", "", raw_text)
    if len(cleaned) < 5:
        return cleaned

    chars = list(cleaned[:5])

    letter_to_digit = {
        "O": "0", "o": "0", "Q": "0",
        "I": "1", "l": "1", "i": "1", "t": "1", "J": "1",
        "Z": "2", "z": "2",
        "E": "3", "e": "3",
        "A": "4", "a": "4",
        "S": "5", "s": "5",
        "G": "6", "b": "6",
        "T": "7", "j": "7",
        "B": "8",
        "g": "9", "q": "9"
    }

    digit_to_letter = {
        "0": "O", "1": "L", "2": "Z", "3": "E", "4": "A",
        "5": "S", "6": "G", "7": "T", "8": "B", "9": "G"
    }

    for i in (0, 1):
        if chars[i].isdigit():
            chars[i] = digit_to_letter.get(chars[i], "A").upper()
        else:
            chars[i] = chars[i].upper()

    for i in (2, 3):
        if chars[i].isdigit():
            chars[i] = digit_to_letter.get(chars[i], "a").lower()
        else:
            chars[i] = chars[i].lower()

    if not chars[4].isdigit():
        chars[4] = letter_to_digit.get(chars[4], "1")

    return "".join(chars)


def get_captcha_from_ollama(image_path):
    try:
        prompt_content = (
            "Read the CAPTCHA text from the image. The CAPTCHA strictly contains 5 characters in total with this exact structure:\n"
            "1. First 2 characters are UPPERCASE letters (e.g. AB)\n"
            "2. Next 2 characters are LOWERCASE letters (e.g. cd)\n"
            "3. The 5th character is 1 NUMERIC DIGIT (e.g. 1)\n"
            "Example pattern: ABcd1\n"
            "Respond ONLY with these 5 characters. Do NOT add any extra words, spaces, explanations, or punctuation."
        )

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{
                "role": "user",
                "content": prompt_content,
                "images": [str(image_path)]
            }]
        )

        raw_text = response["message"]["content"].strip()
        fixed_captcha = fix_captcha_pattern(raw_text)
        logger.debug(f"Ollama CAPTCHA raw: '{raw_text}', cleaned: '{fixed_captcha}'")
        return fixed_captcha

    except Exception as e:
        logger.error(f"Ollama CAPTCHA Reading Error: {e}")
        return ""


def dismiss_all_popups(page):
    """Guarantees all open alert modals and dialogs are closed."""
    page.wait_for_timeout(1000)
    try:
        modal_btns = page.locator("#btnCloseModal, .modal.show button, .modal button.btn-danger, .modal .btn-close").all()
        for btn in modal_btns:
            if btn.is_visible():
                try:
                    btn.click(force=True, timeout=2000)
                except Exception:
                    pass
    except Exception:
        pass

    try:
        page.evaluate("""
            () => {
                const btns = document.querySelectorAll('#btnCloseModal, .modal button, .btn-close, button.btn-danger, [data-bs-dismiss="modal"]');
                btns.forEach(b => {
                    if (b.offsetWidth > 0 && b.offsetHeight > 0) {
                        b.click();
                    }
                });
                document.querySelectorAll('.modal, .modal-backdrop').forEach(el => {
                    el.style.display = 'none';
                    el.classList.remove('show');
                    if (el.classList.contains('modal-backdrop')) {
                        el.remove();
                    }
                });
                document.body.classList.remove('modal-open');
            }
        """)
    except Exception:
        pass

    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    page.wait_for_timeout(1000)


def extract_and_clean_downloaded_file(downloaded_file_path, userid, target_folder):
    """
    Unzips downloaded EPFO ZIP file, formats columns into standard headers,
    cleans Employee Name (keeps Md.), and saves as {userid}.csv
    """
    safe_userid = re.sub(r"[^\w\-]", "_", str(userid))
    target_csv_path = target_folder / f"{safe_userid}.csv"
    raw_content = ""

    if zipfile.is_zipfile(downloaded_file_path):
        try:
            with zipfile.ZipFile(downloaded_file_path, "r") as zip_ref:
                file_list = zip_ref.namelist()
                txt_csv_files = [f for f in file_list if f.endswith(".csv") or f.endswith(".txt") or "." not in f]
                target_inner_file = txt_csv_files[0] if txt_csv_files else file_list[0]
                with zip_ref.open(target_inner_file) as inner_file:
                    raw_content = inner_file.read().decode("utf-8-sig", errors="ignore")
            try:
                os.remove(downloaded_file_path)
            except Exception:
                pass
        except Exception as zip_err:
            logger.error(f"Error unzipping file: {zip_err}")
            return None
    else:
        try:
            with open(downloaded_file_path, "r", encoding="utf-8-sig", errors="ignore") as infile:
                raw_content = infile.read()
            try:
                os.remove(downloaded_file_path)
            except Exception:
                pass
        except Exception as read_err:
            logger.error(f"Error reading file: {read_err}")
            return None

    if not raw_content.strip():
        logger.warning(f"Downloaded file for {userid} is empty!")
        return None

    lines = [line for line in raw_content.splitlines() if line.strip()]
    if not lines:
        return None

    header_line = lines[0]
    delimiter = ","
    if "#~#" in header_line:
        delimiter = "#~#"
    elif "~!" in header_line:
        delimiter = "~!"
    elif "\t" in header_line:
        delimiter = "\t"
    elif "," in header_line:
        delimiter = ","

    reader = csv.DictReader(lines, delimiter=delimiter)
    target_headers = [
        "UAN", "PF NO", "Employee Name", "Gender", "DoB", "DoJ",
        "Father's/Husband's Name", "NameRelation", "Marital Status",
        "Mobile", "Email ID", "EPFO Employer Code",
        "Nomination Filed", "Is AADHAAR Verified", "Face Auth Status"
    ]

    rows = []
    for row in reader:
        cleaned_row = {str(k).strip(): str(v).strip() for k, v in row.items() if k is not None}
        pf_no = cleaned_row.get("Member ID", cleaned_row.get("MemberID", cleaned_row.get("PF NO", ""))).strip()
        employer_code = pf_no[:15] if len(pf_no) >= 15 else pf_no

        raw_emp_name = cleaned_row.get("Name", cleaned_row.get("Employee Name", "")).strip()
        cleaned_emp_name = clean_employee_name(raw_emp_name)

        raw_father_name = cleaned_row.get("Father's/Husband's Name", cleaned_row.get("Father/Husband Name", "")).strip()
        cleaned_father_name = clean_employee_name(raw_father_name)

        new_row = {
            "UAN": cleaned_row.get("UAN", "").strip(),
            "PF NO": pf_no,
            "Employee Name": cleaned_emp_name,
            "Gender": cleaned_row.get("Gender", "").strip(),
            "DoB": cleaned_row.get("DoB", "").strip(),
            "DoJ": cleaned_row.get("DoJ", "").strip(),
            "Father's/Husband's Name": cleaned_father_name,
            "NameRelation": cleaned_row.get("Relation", cleaned_row.get("NameRelation", "")).strip(),
            "Marital Status": cleaned_row.get("Marital Status", cleaned_row.get("MaritalStatus", "")).strip(),
            "Mobile": cleaned_row.get("Mobile", "").strip(),
            "Email ID": cleaned_row.get("Email ID", cleaned_row.get("EmailID", "")).strip(),
            "EPFO Employer Code": cleaned_row.get("EPFO Employer Code", cleaned_row.get("Est ID", employer_code)).strip(),
            "Nomination Filed": cleaned_row.get("Nomination Filed", "").strip(),
            "Is AADHAAR Verified": cleaned_row.get("Is AADHAAR Verified", "").strip(),
            "Face Auth Status": cleaned_row.get("Face Auth Status", "").strip(),
        }
        rows.append(new_row)

    with open(target_csv_path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=target_headers)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Extracted & formatted {len(rows):,} rows -> {target_csv_path.name}")
    return str(target_csv_path)


# ============================================================
# FETCH CREDENTIALS FROM DB OR EXCEL FALLBACK
# ============================================================

def read_users_from_db():
    missing_env = [k for k, v in DB_CONFIG.items() if not v]
    if missing_env:
        raise ValueError(f"Missing DB config in .env: {', '.join(missing_env)}")

    logger.info(
        f"Connecting to database to fetch EPFO credentials ({DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']})..."
    )
    conn = psycopg2.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT "Id", "LoginId", "Password", "Status"
            FROM "Compliance"."PortalLoginCredentials"
            WHERE LOWER("Status") IN ('pf', 'epfo')
            ORDER BY "Id";
        """)
        rows = cur.fetchall()
        cur.close()

        users = []
        for row_id, loginid_raw, password_raw, status in rows:
            loginid = clean_excel_val(loginid_raw)
            password = str(password_raw).strip() if password_raw else ""
            if not loginid:
                continue
            if not password:
                logger.warning(f"Credential ID {row_id} (LoginId: {loginid}) has empty password. Skipping.")
                continue
            users.append((row_id, loginid, password))

        logger.info(f"Loaded {len(users)} active EPFO/PF credentials from DB table 'Compliance'.'PortalLoginCredentials'.")
        return users
    finally:
        conn.close()


def read_users(prefer_db=True):
    if prefer_db:
        try:
            return read_users_from_db()
        except Exception as e:
            logger.warning(f"Database credential lookup failed ({e}). Falling back to users.xlsx...")

    if not EXCEL_FILE.exists():
        raise FileNotFoundError(f"Excel file not found: {EXCEL_FILE}")
    wb = load_workbook(EXCEL_FILE, data_only=True)
    ws = wb.active
    users = []
    for row in range(2, ws.max_row + 1):
        raw_loginid = ws.cell(row, 1).value
        raw_password = ws.cell(row, 2).value
        loginid = clean_excel_val(raw_loginid)
        password = clean_excel_val(raw_password)
        if loginid and password:
            users.append((row, loginid, password))
    return users


# ============================================================
# PROCESS SINGLE EPFO USER
# ============================================================

def process_single_user(page, userid, password):
    safe_userid = re.sub(r"[^\w\-]", "_", str(userid))

    # Auto accept browser dialogs
    try:
        page.on("dialog", lambda dialog: dialog.accept())
    except Exception:
        pass

    # 1. Open Site
    logger.info(f"User {userid}: Opening EPFO site: {LOGIN_URL}")
    page.goto(LOGIN_URL, wait_until="networkidle", timeout=45000)
    page.wait_for_timeout(2500)

    # 2. Initial Alert Dismissal
    dismiss_all_popups(page)

    # 3. Username
    username_elem = page.locator("#username1, input[type='text']").first
    username_elem.wait_for(state="visible", timeout=10000)
    username_elem.fill(userid)
    logger.info(f"User {userid}: Username filled.")
    page.wait_for_timeout(1500)

    # 4. Password
    password_elem = page.locator('[name="password"], input[type="password"]').first
    password_elem.wait_for(state="visible", timeout=10000)
    password_elem.fill(password)
    logger.info(f"User {userid}: Password filled.")
    page.wait_for_timeout(1500)

    dismiss_all_popups(page)

    # 5. CAPTCHA Field & Screenshot
    captcha_elem = page.locator("#captcha, input[placeholder*='captcha' i]").first
    captcha_elem.wait_for(state="visible", timeout=10000)
    captcha_elem.click()

    captcha_img = page.locator("div#ToggleCaptcha img, #ToggleCaptcha img, img.captcha-img, img[src*='captcha' i]").first
    captcha_img.wait_for(state="visible", timeout=10000)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path = CAPTCHA_FOLDER / f"captcha_{safe_userid}_{timestamp}.png"
    captcha_img.screenshot(path=str(image_path))

    # 6. CAPTCHA Auto Fill via Ollama
    captcha_text = get_captcha_from_ollama(image_path)
    captcha_elem.fill(captcha_text)
    logger.info(f"User {userid}: CAPTCHA auto filled: {captcha_text}")

    page.wait_for_timeout(3500)

    # 7. Sign In
    logger.info(f"User {userid}: Clicking Sign In...")
    try:
        signIn_btn = page.get_by_role("button", name="Sign In").first
        signIn_btn.click(force=True, timeout=5000)
    except Exception:
        signIn_btn = page.locator("button.btn-logging, button.btn-success, button[type='submit']").first
        signIn_btn.click(force=True)

    page.wait_for_timeout(8000)

    # Verify login success
    dashboards_elem = page.get_by_role("button", name="Dashboards").first
    try:
        is_logged_in = dashboards_elem.is_visible(timeout=6000)
    except Exception:
        is_logged_in = False

    if not is_logged_in:
        raise RuntimeError("Login failed (Invalid CAPTCHA or Password). Webpage remained on login screen.")

    logger.info(f"User {userid}: Login SUCCESSFUL!")
    dismiss_all_popups(page)
    page.wait_for_timeout(2000)

    # 8. Dashboard -> Active Member
    logger.info(f"User {userid}: Navigating to Dashboards -> ACTIVE MEMBER...")
    dashboards_elem.click(force=True)
    page.wait_for_timeout(3500)

    active_elem = page.get_by_role("link", name="ACTIVE MEMBER").first
    active_elem.wait_for(state="visible", timeout=10000)
    active_elem.click(force=True)
    page.wait_for_timeout(4500)

    # 9. Trigger Active Members Download
    logger.info(f"User {userid}: Triggering Active Members Download...")
    download_btn = page.locator('[title="Download all active members"], a[href*="activeMembersCsv"], a:has-text("Export")').first
    download_btn.wait_for(state="visible", timeout=10000)

    try:
        with page.expect_download(timeout=40000) as download_info:
            download_btn.click(force=True)
        download = download_info.value
    except Exception as d_err:
        logger.warning(f"Standard download click: {d_err}. Trying JS click...")
        with page.expect_download(timeout=40000) as download_info:
            download_btn.evaluate("el => el.click()")
        download = download_info.value

    temp_download_path = TARGET_DOWNLOAD_DIR / f"raw_{download.suggested_filename}"
    download.save_as(temp_download_path)
    logger.info(f"User {userid}: Downloaded raw file saved -> {temp_download_path.name}")

    # 10. Extract & clean into final CSV
    final_csv = extract_and_clean_downloaded_file(temp_download_path, userid, TARGET_DOWNLOAD_DIR)
    if not final_csv:
        raise RuntimeError("Failed to extract & format CSV file.")

    page.wait_for_timeout(2500)

    # 11. Logout
    try:
        logout_btn = page.locator("a[href*='logout'], //a[contains(text(),'Logout')]").first
        if logout_btn.is_visible(timeout=3000):
            logout_btn.click(force=True)
            logger.info(f"User {userid}: Logged out successfully.")
            page.wait_for_timeout(2500)
    except Exception:
        pass

    return Path(final_csv).name


# ============================================================
# MAIN ORCHESTRATOR FOR DOWNLOAD
# ============================================================

def run_portal_download(headless=False, auto_mode=True, concurrency=1):
    logger.info("Starting EPFO Portal Download Automation...")
    logger.info(f"Download Dir: {TARGET_DOWNLOAD_DIR}")
    logger.info(f"Browser Mode: {'HEADLESS' if headless else 'VISIBLE'}")

    CAPTCHA_FOLDER.mkdir(parents=True, exist_ok=True)
    TARGET_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    users = read_users(prefer_db=True)
    if not users:
        logger.warning("No valid credentials found.")
        return True

    total_users = len(users)
    logger.info(f"Total Users Found: {total_users}")

    success_count = 0
    failed_count = 0

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=["--start-maximized", "--disable-popup-blocking"]
        )
        context = browser.new_context(
            no_viewport=True,
            accept_downloads=True
        )
        page = context.new_page()

        for idx, (cred_id, userid, password) in enumerate(users, start=1):
            logger.info("=" * 60)
            logger.info(f"[{idx}/{total_users}] Processing User: {userid} (Cred ID: {cred_id})")
            logger.info("=" * 60)

            # Register in PortalDownloadLog
            log_id = log_download_start(cred_id)
            user_success = False

            for attempt in range(1, MAX_RETRIES_PER_USER + 1):
                if attempt > 1:
                    logger.info(f"Retry attempt {attempt}/{MAX_RETRIES_PER_USER} for User: {userid}")

                try:
                    downloaded_filename = process_single_user(page, userid, password)
                    log_download_success(log_id, downloaded_filename)
                    logger.info(f"User {userid} SUCCESS: {downloaded_filename}")
                    success_count += 1
                    user_success = True
                    break
                except Exception as err:
                    logger.error(f"Attempt {attempt} Error for User {userid}: {err}")
                    if attempt < MAX_RETRIES_PER_USER:
                        logger.info("Refreshing page & retrying in 3 seconds...")
                        try:
                            page.goto(LOGIN_URL, wait_until="networkidle", timeout=20000)
                        except Exception:
                            pass
                        page.wait_for_timeout(3000)
                    else:
                        log_download_failure(log_id, err)
                        logger.error(f"User {userid} FAILED after {MAX_RETRIES_PER_USER} attempts.")
                        failed_count += 1

            logger.info(f"Progress [{idx}/{total_users}] | Success: {success_count}, Failed: {failed_count}")

        browser.close()

    logger.info("=" * 60)
    logger.info(f"EPFO Portal Download Finished: {success_count} succeeded, {failed_count} failed out of {total_users} total.")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    try:
        run_portal_download(headless=False, auto_mode=True)
    except Exception as exc:
        logger.error(f"Download pipeline failed: {exc}")
        sys.exit(1)

