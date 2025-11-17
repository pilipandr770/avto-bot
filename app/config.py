import os
from dotenv import load_dotenv
from pathlib import Path

base = Path(__file__).resolve().parent.parent
load_dotenv(base / '.env')


class Config:
    FLASK_ENV = os.environ.get('FLASK_ENV', 'production')
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DB_SCHEMA = os.environ.get('DB_SCHEMA', 'avto_bot')
    MASTER_SECRET_KEY = os.environ.get('MASTER_SECRET_KEY')
    # APScheduler config
    SCHEDULER_API_ENABLED = True
    # Add other configs as needed
