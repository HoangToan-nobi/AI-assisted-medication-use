import sqlite3

db_path = "data/app.db"

queries = [
    "ALTER TABLE patient_profiles ADD COLUMN gioi_tinh VARCHAR(20)",
    "ALTER TABLE patient_profiles ADD COLUMN can_nang FLOAT",
    "ALTER TABLE patient_profiles ADD COLUMN chieu_cao FLOAT",
    "ALTER TABLE patient_profiles ADD COLUMN di_ung_thuoc TEXT",
    "ALTER TABLE patient_profiles ADD COLUMN tinh_trang_khac TEXT"
]

def main():
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    for q in queries:
        try:
            cur.execute(q)
            print(f"Executed: {q}")
        except sqlite3.OperationalError as e:
            print(f"Skipped {q} ({e})")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    main()
