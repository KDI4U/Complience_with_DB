import os
import sys
import logging
from pathlib import Path
import psycopg2
from openpyxl import load_workbook, Workbook
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    PROJECT_FOLDER = Path(sys.executable).resolve().parent
else:
    PROJECT_FOLDER = Path(__file__).resolve().parent

ENV_FILE = PROJECT_FOLDER / ".env"
load_dotenv(ENV_FILE)

DATA_FOLDER = PROJECT_FOLDER / "data"
EXCEL_FILE = DATA_FOLDER / "users.xlsx"
FALLBACK_EXCEL = PROJECT_FOLDER / "users.xlsx"

logger = logging.getLogger("user_manager")


def get_db_config():
    load_dotenv(ENV_FILE, override=True)
    return {
        "host": os.getenv("DB_HOST"),
        "port": os.getenv("DB_PORT", "5432"),
        "dbname": os.getenv("DB_NAME", "UrmilaHRMS_TEMP_NEW"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }


def test_db_connection():
    config = get_db_config()
    if not config.get("host") or not config.get("user"):
        return False, "Database host or user missing in .env"
    try:
        conn = psycopg2.connect(connect_timeout=3, **config)
        conn.close()
        return True, f"Connected successfully to {config['host']}:{config['port']}/{config['dbname']}"
    except Exception as exc:
        return False, str(exc)


def get_excel_path():
    DATA_FOLDER.mkdir(parents=True, exist_ok=True)
    if EXCEL_FILE.exists():
        return EXCEL_FILE
    if FALLBACK_EXCEL.exists():
        return FALLBACK_EXCEL
    return EXCEL_FILE


def load_all_users():
    """
    Returns list of dicts:
    [{'id': ..., 'loginid': '...', 'password': '...', 'status': 'PF', 'source': 'DB' or 'EXCEL'}]
    """
    users = []
    db_ok, _ = test_db_connection()
    if db_ok:
        try:
            config = get_db_config()
            conn = psycopg2.connect(**config)
            cur = conn.cursor()
            cur.execute("""
                SELECT "Id", "LoginId", "Password", "Status"
                FROM "Compliance"."PortalLoginCredentials"
                WHERE LOWER("Status") IN ('pf', 'epfo')
                ORDER BY "Id";
            """)
            for row_id, loginid, password, status in cur.fetchall():
                users.append({
                    "id": row_id,
                    "loginid": str(loginid).strip() if loginid else "",
                    "password": str(password).strip() if password else "",
                    "status": str(status).strip() if status else "PF",
                    "source": "DATABASE"
                })
            cur.close()
            conn.close()
            return users
        except Exception as e:
            logger.warning(f"Failed to fetch users from DB: {e}")

    # Fallback to Excel
    excel_path = get_excel_path()
    if excel_path.exists():
        try:
            wb = load_workbook(excel_path, data_only=True)
            ws = wb.active
            for row in range(2, ws.max_row + 1):
                raw_u = ws.cell(row, 1).value
                raw_p = ws.cell(row, 2).value
                if raw_u and raw_p:
                    users.append({
                        "id": row,
                        "loginid": str(raw_u).strip(),
                        "password": str(raw_p).strip(),
                        "status": "PF",
                        "source": "EXCEL"
                    })
        except Exception as e:
            logger.error(f"Failed reading Excel users: {e}")

    return users


def add_user(loginid, password, status="PF"):
    loginid = str(loginid).strip()
    password = str(password).strip()
    status = str(status).strip().upper()

    if not loginid or not password:
        return False, "Login ID and Password cannot be empty."

    db_saved = False
    excel_saved = False
    msg_parts = []

    # 1. Try saving to DB
    db_ok, _ = test_db_connection()
    if db_ok:
        try:
            config = get_db_config()
            conn = psycopg2.connect(**config)
            cur = conn.cursor()
            # Check if exists
            cur.execute("""
                SELECT "Id" FROM "Compliance"."PortalLoginCredentials"
                WHERE "LoginId" = %s AND LOWER("Status") IN ('pf', 'epfo');
            """, (loginid,))
            existing = cur.fetchone()
            if existing:
                cur.execute("""
                    UPDATE "Compliance"."PortalLoginCredentials"
                    SET "Password" = %s, "Status" = %s
                    WHERE "Id" = %s;
                """, (password, status, existing[0]))
            else:
                cur.execute("""
                    INSERT INTO "Compliance"."PortalLoginCredentials"
                    ("LoginId", "Password", "Status")
                    VALUES (%s, %s, %s);
                """, (loginid, password, status))
            conn.commit()
            cur.close()
            conn.close()
            db_saved = True
            msg_parts.append("Saved to Database")
        except Exception as exc:
            msg_parts.append(f"DB Error: {exc}")

    # 2. Save / Sync to Excel
    try:
        excel_path = get_excel_path()
        if not excel_path.exists():
            wb = Workbook()
            ws = wb.active
            ws.append(["loginid", "password", "response"])
        else:
            wb = load_workbook(excel_path)
            ws = wb.active

        found_row = None
        for row in range(2, ws.max_row + 1):
            if str(ws.cell(row, 1).value or "").strip() == loginid:
                found_row = row
                break

        if found_row:
            ws.cell(found_row, 2, value=password)
        else:
            ws.append([loginid, password, None])

        wb.save(excel_path)
        # Also copy to fallback if different
        if excel_path != FALLBACK_EXCEL and FALLBACK_EXCEL.parent.exists():
            try:
                wb.save(FALLBACK_EXCEL)
            except Exception:
                pass

        excel_saved = True
        msg_parts.append("Saved to users.xlsx")
    except Exception as exc:
        msg_parts.append(f"Excel Error: {exc}")

    if db_saved or excel_saved:
        return True, " & ".join(msg_parts)
    return False, "Failed to save: " + " | ".join(msg_parts)


def update_user_password(loginid, new_password):
    return add_user(loginid, new_password)


def delete_user(loginid):
    loginid = str(loginid).strip()
    db_ok, _ = test_db_connection()
    deleted_db = False
    deleted_excel = False

    if db_ok:
        try:
            config = get_db_config()
            conn = psycopg2.connect(**config)
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM "Compliance"."PortalLoginCredentials"
                WHERE "LoginId" = %s AND LOWER("Status") IN ('pf', 'epfo');
            """, (loginid,))
            conn.commit()
            cur.close()
            conn.close()
            deleted_db = True
        except Exception as exc:
            logger.error(f"Error deleting user from DB: {exc}")

    # Remove from Excel
    excel_path = get_excel_path()
    if excel_path.exists():
        try:
            wb = load_workbook(excel_path)
            ws = wb.active
            for row in range(2, ws.max_row + 1):
                if str(ws.cell(row, 1).value or "").strip() == loginid:
                    ws.delete_rows(row, 1)
                    wb.save(excel_path)
                    deleted_excel = True
                    break
        except Exception as exc:
            logger.error(f"Error removing user from Excel: {exc}")

    if deleted_db or deleted_excel:
        return True, f"User {loginid} removed successfully."
    return False, f"User {loginid} not found."

