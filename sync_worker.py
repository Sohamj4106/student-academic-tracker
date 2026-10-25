"""Optional background worker: copies current PostgreSQL tables to Google Sheets.
Run after completing Google service-account setup and installing triggers from database.sql.
"""
import os
import time
import pandas as pd
import psycopg2
import gspread
from dotenv import load_dotenv

load_dotenv()

TABLES = [
    "students", "academic_records", "semesters", "subjects", "student_marks",
    "gap_years", "seminars", "activities"
]

def connect_db():
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "student_academic_tracker"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )

def sync_all():
    credentials_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "service_account.json")
    spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "")
    if not spreadsheet_id or spreadsheet_id == "PASTE_SPREADSHEET_ID_HERE":
        raise RuntimeError("Set GOOGLE_SPREADSHEET_ID in .env first.")
    gc = gspread.service_account(filename=credentials_file)
    spreadsheet = gc.open_by_key(spreadsheet_id)

    with connect_db() as conn:
        for table in TABLES:
            df = pd.read_sql_query(f"SELECT * FROM {table} ORDER BY 1", conn)
            values = [df.columns.tolist()]
            if not df.empty:
                clean = df.astype(object).where(pd.notna(df), "")
                rows = clean.values.tolist()
                for row in rows:
                 values.append([
                     item.isoformat() if hasattr(item, "isoformat") else item
                     for item in row
                     ])
            try:
                ws = spreadsheet.worksheet(table)
                ws.clear()
            except gspread.WorksheetNotFound:
                ws = spreadsheet.add_worksheet(title=table, rows=max(len(values), 100), cols=max(len(values[0]), 10))
            ws.update(values=values, range_name="A1", value_input_option="USER_ENTERED")

def main():
    print("Google Sheets sync worker started. Press Ctrl+C to stop.")
    while True:
        try:
            with connect_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM sync_log WHERE sync_status='Pending'")
                    pending = cur.fetchone()[0]
            if pending:
                print(f"{pending} pending change(s); syncing tables...")
                sync_all()
                with connect_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE sync_log SET sync_status='Success' WHERE sync_status='Pending'")
                    conn.commit()
                print("Sync completed.")
        except Exception as e:
            print("Sync failed:", e)
            try:
                with connect_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""UPDATE sync_log SET sync_status='Failed', error_message=%s
                                       WHERE sync_status='Pending'""", (str(e)[:2000],))
                    conn.commit()
            except Exception:
                pass
        time.sleep(10)

if __name__ == "__main__":
    main()
