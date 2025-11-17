from datetime import datetime
import os
from .extensions import db
from flask_login import UserMixin

# Use DB_SCHEMA env var so SQLAlchemy binds models to the correct schema
DB_SCHEMA = os.environ.get('DB_SCHEMA', 'avto_bot')


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __table_args__ = {'schema': DB_SCHEMA}
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    settings = db.relationship('UserSettings', back_populates='user', uselist=False)
    logs = db.relationship('PostingLog', back_populates='user')


class UserSettings(db.Model):
    __tablename__ = 'user_settings'
    __table_args__ = {'schema': DB_SCHEMA}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    gmail_address = db.Column(db.String(255))
    gmail_app_password_encrypted = db.Column(db.Text)
    telegram_bot_token_encrypted = db.Column(db.Text)
    telegram_channel_username = db.Column(db.String(255))
    telegram_channel_id = db.Column(db.BigInteger, nullable=True)
    openai_api_key_encrypted = db.Column(db.Text)
    language = db.Column(db.String(8), default='uk')
    price_markup_eur = db.Column(db.Integer, default=0)
    auto_post_enabled = db.Column(db.Boolean, default=False)

    user = db.relationship('User', back_populates='settings')


class PostingLog(db.Model):
    __tablename__ = 'posting_logs'
    __table_args__ = {'schema': DB_SCHEMA}
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    gmail_message_id = db.Column(db.String(255))
    subject = db.Column(db.String(1024))
    car_title = db.Column(db.String(1024))
    raw_price = db.Column(db.String(64))
    final_price = db.Column(db.String(64))
    sent_to_channel = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, nullable=True)
    error = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', back_populates='logs')
