import sqlite3
import os

db_path = "data/app.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE users ADD COLUMN noi_cong_tac VARCHAR(255)")
        conn.commit()
        print("Column noi_cong_tac added successfully.")
        
        # Thêm dữ liệu mẫu cho một số dược sĩ nếu cần
        cur.execute("UPDATE users SET noi_cong_tac = 'Bệnh viện Chợ Rẫy' WHERE vai_tro = 'pharmacist' AND noi_cong_tac IS NULL")
        conn.commit()
    except sqlite3.OperationalError as e:
        print("Error or column already exists:", e)
    conn.close()
else:
    print("DB file not found.")
