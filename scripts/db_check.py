from dotenv import load_dotenv
import os, psycopg2

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()
cur.execute("SELECT current_schema(), current_setting('search_path')")
print('current_schema, search_path:', cur.fetchone())
cur.execute("SELECT n.nspname as schemaname, c.relname as tablename FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relkind='r' AND c.relname='users';")
rows = cur.fetchall()
print('\nAll places a table named users exists:')
for r in rows:
    print('-', f"{r[0]}.{r[1]}")
cur.execute("SELECT EXISTS(SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.relname='users' AND n.nspname='avto_bot')")
print('\navto_bot.users exists?:', cur.fetchone()[0])
cur.close()
conn.close()
