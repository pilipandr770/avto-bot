import os
from dotenv import load_dotenv
from pathlib import Path

base = Path(__file__).resolve().parent.parent
# Load default .env and optional .env.local for local overrides
load_dotenv(base / '.env')
load_dotenv(base / '.env.local', override=True)


class Config:
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_SCHEMA = os.environ.get('DB_SCHEMA', 'avto_bot')
    MASTER_SECRET_KEY = os.environ.get('MASTER_SECRET_KEY')
    # Ensure connections set the search_path so tables are created and queried in the schema
    if SQLALCHEMY_DATABASE_URI and DB_SCHEMA:
        # psycopg2 'options' parameter accepts -c statements; set search_path on connect
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'options': f"-c search_path={DB_SCHEMA},public"}
        }
    # APScheduler config
    SCHEDULER_API_ENABLED = True
    # Add other configs as needed
