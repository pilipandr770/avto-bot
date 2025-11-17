import traceback
from .extensions import scheduler, db
from .models import User, PostingLog
from .security import decrypt_secret
from .gmail_client import fetch_new_messages, mark_message_seen
from .openai_client import generate_listing_text
from .telegram_client import ensure_channel_id, send_car_post
from flask import current_app
from datetime import datetime


def process_user_inbox(user: User):
    settings = user.settings
    if not settings or not settings.auto_post_enabled:
        return

    master_key = current_app.config.get('MASTER_SECRET_KEY')
    gmail_pwd = decrypt_secret(settings.gmail_app_password_encrypted, master_key) if settings.gmail_app_password_encrypted else None
    openai_key = decrypt_secret(settings.openai_api_key_encrypted, master_key) if settings.openai_api_key_encrypted else None
    bot_token = decrypt_secret(settings.telegram_bot_token_encrypted, master_key) if settings.telegram_bot_token_encrypted else None

    # attach decrypted attrs for client use
    settings.gmail_app_password_decrypted = gmail_pwd

    if not (settings.gmail_address and gmail_pwd and openai_key and bot_token and settings.telegram_channel_username):
        return

    # ensure channel id
    try:
        cid = ensure_channel_id(settings, bot_token)
        if cid:
            db.session.add(settings)
            db.session.commit()
    except Exception:
        pass

    messages = fetch_new_messages(settings)
    for msg in messages:
        try:
            # crude parsing
            raw = {
                'title': msg.subject or 'Car listing',
                'price': None,
                'mileage': None,
                'year': None,
                'fuel': None,
                'gearbox': None,
                'description': msg.text_body or msg.html_body,
                'url': ''
            }

            text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
            photos = [a['content'] for a in msg.attachments] if msg.attachments else []
            ok, err = send_car_post(settings, bot_token, text, photos)

            log = PostingLog(user_id=user.id, gmail_message_id=msg.uid, subject=msg.subject, car_title=raw['title'], raw_price=str(raw.get('price')), final_price=str(settings.price_markup_eur or ''), sent_to_channel=bool(ok), sent_at=(datetime.utcnow() if ok else None), error=(err if not ok else None))
            db.session.add(log)
            db.session.commit()
            # mark seen
            mark_message_seen(settings, msg.uid)
        except Exception:
            traceback.print_exc()
            log = PostingLog(user_id=user.id, gmail_message_id=getattr(msg, 'uid', None), subject=getattr(msg, 'subject', None), error=traceback.format_exc())
            db.session.add(log)
            db.session.commit()


def process_user_inbox_once(user: User):
    """Process inbox for a user once regardless of their auto_post_enabled flag (used for manual checks)."""
    settings = user.settings
    master_key = current_app.config.get('MASTER_SECRET_KEY')
    gmail_pwd = decrypt_secret(settings.gmail_app_password_encrypted, master_key) if settings and settings.gmail_app_password_encrypted else None
    openai_key = decrypt_secret(settings.openai_api_key_encrypted, master_key) if settings and settings.openai_api_key_encrypted else None
    bot_token = decrypt_secret(settings.telegram_bot_token_encrypted, master_key) if settings and settings.telegram_bot_token_encrypted else None

    # attach decrypted attrs for client use
    if settings:
        settings.gmail_app_password_decrypted = gmail_pwd

    if not (settings and settings.gmail_address and gmail_pwd and openai_key and bot_token and settings.telegram_channel_username):
        return

    try:
        cid = ensure_channel_id(settings, bot_token)
        if cid:
            db.session.add(settings)
            db.session.commit()
    except Exception:
        pass

    messages = fetch_new_messages(settings)
    for msg in messages:
        try:
            raw = {
                'title': msg.subject or 'Car listing',
                'price': None,
                'mileage': None,
                'year': None,
                'fuel': None,
                'gearbox': None,
                'description': msg.text_body or msg.html_body,
                'url': ''
            }

            text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
            photos = [a['content'] for a in msg.attachments] if msg.attachments else []
            ok, err = send_car_post(settings, bot_token, text, photos)

            log = PostingLog(user_id=user.id, gmail_message_id=msg.uid, subject=msg.subject, car_title=raw['title'], raw_price=str(raw.get('price')), final_price=str(settings.price_markup_eur or ''), sent_to_channel=bool(ok), sent_at=(datetime.utcnow() if ok else None), error=(err if not ok else None))
            db.session.add(log)
            db.session.commit()
            # mark seen
            mark_message_seen(settings, msg.uid)
        except Exception:
            traceback.print_exc()
            log = PostingLog(user_id=user.id, gmail_message_id=getattr(msg, 'uid', None), subject=getattr(msg, 'subject', None), error=traceback.format_exc())
            db.session.add(log)
            db.session.commit()


def check_all_inboxes(app=None):
    # If called from scheduler, pass app to create app_context
    if app is not None:
        with app.app_context():
            users = User.query.all()
            for u in users:
                try:
                    process_user_inbox(u)
                except Exception:
                    pass
def check_inbox_for_user_id(user_id: int, app=None):
    """Run a one-off inbox processing for a single user id inside an app context (safe to call from scheduler). Uses the 'once' processor so manual checks run regardless of auto_post flag."""
    if app is not None:
        with app.app_context():
            u = User.query.get(user_id)
            if u:
                try:
                    process_user_inbox_once(u)
                except Exception:
                    pass
    else:
        from flask import current_app
        with current_app.app_context():
            u = User.query.get(user_id)
            if u:
                try:
                    process_user_inbox_once(u)
                except Exception:
                    pass

