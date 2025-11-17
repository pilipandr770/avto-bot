from dotenv import load_dotenv
import os, psycopg2

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_SCHEMA = os.environ.get('DB_SCHEMA') or 'public'
REVISION = os.environ.get('ALEMBIC_REVISION') or 'a1b2c3d4e5f6'

if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
# create alembic_version table if not exists
cur.execute(f"CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.alembic_version (version_num VARCHAR(32) NOT NULL);")
# ensure only one row
cur.execute(f"DELETE FROM {DB_SCHEMA}.alembic_version;")
cur.execute(f"INSERT INTO {DB_SCHEMA}.alembic_version (version_num) VALUES (%s);", (REVISION,))
conn.commit()
print(f'Inserted alembic version {REVISION} into schema {DB_SCHEMA}.alembic_version')
cur.close()
conn.close()
