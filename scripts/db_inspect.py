import os
from dotenv import load_dotenv
import psycopg2

try:
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env.local'))
    DATABASE_URL = os.environ.get('DATABASE_URL')
    DB_SCHEMA = os.environ.get('DB_SCHEMA', 'avto_bot')

    if not DATABASE_URL:
        print('DATABASE_URL not set in .env.local')
        raise SystemExit(1)

    print('Using DATABASE_URL:', DATABASE_URL)
    print('Checking schema:', DB_SCHEMA)

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    print('\nTables in public:')
    cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public';")
    for r in cur.fetchall():
        print(' -', r[0])

    print(f"\nTables in {DB_SCHEMA}:")
    cur.execute("SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname=%s;", (DB_SCHEMA,))
    rows = cur.fetchall()
    if not rows:
        print(' (none)')
    else:
        for r in rows:
            print(' -', r[0])

    cur.close()
    conn.close()
except Exception as e:
    import traceback
    print('Exception while inspecting DB:')
    traceback.print_exc()
    raise
