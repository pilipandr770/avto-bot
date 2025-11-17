from dotenv import load_dotenv
import os, psycopg2

load_dotenv('.env.local')
DATABASE_URL = os.environ.get('DATABASE_URL')
DB_SCHEMA = os.environ.get('DB_SCHEMA') or 'public'

if not DATABASE_URL:
    print('DATABASE_URL not set')
    raise SystemExit(1)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print('Creating tables in schema:', DB_SCHEMA)

# create tables with IF NOT EXISTS
cur.execute(f"CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.users (\n    id SERIAL PRIMARY KEY,\n    email VARCHAR(255) NOT NULL UNIQUE,\n    password_hash VARCHAR(255) NOT NULL\n);")
cur.execute(f"CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.posting_logs (\n    id SERIAL PRIMARY KEY,\n    user_id INTEGER REFERENCES {DB_SCHEMA}.users(id),\n    gmail_message_id VARCHAR(255),\n    subject VARCHAR(1024),\n    car_title VARCHAR(1024),\n    raw_price VARCHAR(64),\n    final_price VARCHAR(64),\n    sent_to_channel BOOLEAN,\n    sent_at TIMESTAMP,\n    error TEXT,\n    created_at TIMESTAMP\n);")
cur.execute(f"CREATE TABLE IF NOT EXISTS {DB_SCHEMA}.user_settings (\n    id SERIAL PRIMARY KEY,\n    user_id INTEGER REFERENCES {DB_SCHEMA}.users(id),\n    gmail_address VARCHAR(255),\n    gmail_app_password_encrypted TEXT,\n    telegram_bot_token_encrypted TEXT,\n    telegram_channel_username VARCHAR(255),\n    telegram_channel_id BIGINT,\n    openai_api_key_encrypted TEXT,\n    language VARCHAR(8),\n    price_markup_eur INTEGER,\n    auto_post_enabled BOOLEAN,\n    UNIQUE(user_id)\n);")

conn.commit()
print('Tables created (if not existed).')
cur.close()
conn.close()
