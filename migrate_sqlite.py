"""Run locally once to copy licenses.db into PostgreSQL.
Usage: set DATABASE_URL, then: python migrate_sqlite.py
"""
import os, sqlite3, psycopg2
from app import DATABASE_URL

if not DATABASE_URL:
    raise SystemExit("Set DATABASE_URL first")

sqlite_path = os.environ.get("SQLITE_DB", "licenses.db")
s = sqlite3.connect(sqlite_path)
s.row_factory = sqlite3.Row
rows = s.execute("SELECT license_key,license_hash,customer,plan,expires,max_groups,active,hwid,activated_at,last_seen,created_at FROM licenses ORDER BY id").fetchall()
s.close()

p = psycopg2.connect(DATABASE_URL)
with p.cursor() as c:
    c.execute("""
    CREATE TABLE IF NOT EXISTS licenses (
      id BIGSERIAL PRIMARY KEY,
      license_key TEXT UNIQUE NOT NULL,
      license_hash TEXT UNIQUE NOT NULL,
      customer TEXT NOT NULL,
      plan TEXT NOT NULL,
      expires TEXT NOT NULL,
      max_groups TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1,
      hwid TEXT,
      activated_at TEXT,
      last_seen TEXT,
      created_at TEXT NOT NULL
    )
    """)
    for r in rows:
        c.execute("""
        INSERT INTO licenses
        (license_key,license_hash,customer,plan,expires,max_groups,active,hwid,activated_at,last_seen,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (license_hash) DO UPDATE SET
          customer=EXCLUDED.customer, plan=EXCLUDED.plan, expires=EXCLUDED.expires,
          max_groups=EXCLUDED.max_groups, active=EXCLUDED.active, hwid=EXCLUDED.hwid,
          activated_at=EXCLUDED.activated_at, last_seen=EXCLUDED.last_seen,
          created_at=EXCLUDED.created_at
        """, tuple(r))
p.commit(); p.close()
print(f"Migrated {len(rows)} license(s).")
