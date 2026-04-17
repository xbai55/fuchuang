import sqlite3, os, shutil

src = "fraud_detection.db"
dst = "backend/fraud_detection.db"

# Backup
shutil.copy2(dst, dst + ".bak")
print(f"Backed up {dst} -> {dst}.bak")

src_conn = sqlite3.connect(src)
dst_conn = sqlite3.connect(dst)

# Get fraud_cases DDL from src
src_cur = src_conn.cursor()
src_cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='fraud_cases'")
ddl = src_cur.fetchone()[0]

# Create table in dst
dst_cur = dst_conn.cursor()
dst_cur.execute(ddl)
print("Created fraud_cases table in backend/fraud_detection.db")

# Copy rows
src_cur.execute("SELECT * FROM fraud_cases")
rows = src_cur.fetchall()
if rows:
    placeholders = ",".join(["?"] * len(rows[0]))
    dst_cur.executemany(f"INSERT INTO fraud_cases VALUES ({placeholders})", rows)
    print(f"Copied {len(rows)} rows to fraud_cases")
else:
    print("No rows to copy")

dst_conn.commit()
src_conn.close()
dst_conn.close()

# Verify
conn = sqlite3.connect(dst)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
tables = [r[0] for r in cur.fetchall()]
cur.execute("SELECT COUNT(*) FROM fraud_cases")
count = cur.fetchone()[0]
conn.close()
print(f"backend/fraud_detection.db tables: {tables}")
print(f"fraud_cases rows: {count}")

# Remove root db
os.remove(src)
print(f"Deleted {src}")
print("Merge complete.")
