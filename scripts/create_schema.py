import os
import psycopg2
from dotenv import load_dotenv

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_SCHEMA = os.environ.get('DB_SCHEMA') or 'public'

if not DATABASE_URL:
    print('DATABASE_URL not set in .env.local')
    raise SystemExit(1)

print(f'Connecting to DB: {DATABASE_URL}')
print(f'Target schema: {DB_SCHEMA}')
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
try:
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {DB_SCHEMA}")
    conn.commit()
    print(f'Schema "{DB_SCHEMA}" created or already exists.')
except Exception as e:
    print('Error creating schema:', e)
    conn.rollback()
finally:
    cur.close()
    conn.close()
