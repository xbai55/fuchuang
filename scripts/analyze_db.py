import sqlite3, os

dbs = ["backend/fraud_detection.db"]
schemas = {}
for path in dbs:
    print(f"\n=== {path} ({os.path.getsize(path)} bytes) ===")
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [r[0] for r in cur.fetchall()]
    print("Tables:", tables)
    schemas[path] = {}
    for t in tables:
        cur.execute(f"SELECT COUNT(*) FROM [{t}]")
        count = cur.fetchone()[0]
        cur.execute(f"PRAGMA table_info([{t}])")
        cols = [(r[1], r[2]) for r in cur.fetchall()]
        schemas[path][t] = cols
        print(f"  {t}: {count} rows")
        for col in cols:
            print(f"    {col[0]} ({col[1]})")
    conn.close()

# Compare schemas
print("\n\n=== SCHEMA DIFF ===")
all_tables = set()
for s in schemas.values():
    all_tables.update(s.keys())

for t in sorted(all_tables):
    in_files = [p for p in dbs if t in schemas[p]]
    if len(in_files) < 2:
        print(f"[{t}] only in: {in_files}")
    else:
        s0 = schemas[dbs[0]].get(t, [])
        s1 = schemas[dbs[1]].get(t, [])
        if s0 != s1:
            print(f"[{t}] SCHEMA MISMATCH")
            print(f"  {dbs[0]}: {s0}")
            print(f"  {dbs[1]}: {s1}")
        else:
            print(f"[{t}] schemas identical")
