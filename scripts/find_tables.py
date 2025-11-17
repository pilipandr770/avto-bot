import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set in .env.local')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT schemaname, tablename FROM pg_catalog.pg_tables WHERE tablename IN ('users','user_settings','posting_logs','alembic_version') ORDER BY schemaname, tablename;")
rows = cur.fetchall()
if not rows:
    print('No matching tables found in any schema')
else:
    print('Found tables:')
    for s,t in rows:
        print(f'- {s}.{t}')

cur.close()
conn.close()
