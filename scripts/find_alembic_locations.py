from dotenv import load_dotenv
import os, psycopg2

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relname='alembic_version';")
rows = cur.fetchall()
print('alembic_version tables found in schemas:')
for r in rows:
    print('-', r[0])
cur.close()
conn.close()
