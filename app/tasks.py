import traceback
from .extensions import scheduler, db
from .models import User, PostingLog
from .security import decrypt_secret
from .gmail_client import fetch_new_messages, mark_message_seen
from .openai_client import generate_listing_text
from .telegram_client import ensure_channel_id, send_car_post
from .utils.mobile_parser import parse_mobile_de
from flask import current_app
from datetime import datetime
import re
import requests
from bs4 import BeautifulSoup
import time
import json
import codecs


def extract_urls(text):
    """Extract URLs from text and HTML."""
    urls = set()
    # Regex for plain text URLs
    url_pattern = r'https?://[^\s<>"\']+'
    urls.update(re.findall(url_pattern, text))

    # Parse HTML for href attributes
    try:
        soup = BeautifulSoup(text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.startswith('http'):
                urls.add(href)
    except:
        pass

    return list(urls)


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
            body = (msg.text_body or '') + '\n' + (msg.html_body or '')

            # Filter only mobile.de-related messages
            if 'mobile.de' not in (msg.from_addr or '').lower() and 'mobile.de' not in body.lower():
                # Skip non-mobile.de messages
                mark_message_seen(settings, msg.uid)
                continue

            # Filter only mobile.de-related messages/URLs
            urls = extract_urls(body)
            mobile_urls = list(set([u for u in urls if 'mobile.de' in u and ('/auto-inserat/' in u or 'click.news.mobile.de' in u) and not any(ext in u.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp'])]))

            if not mobile_urls:
                # Fallback to old parsing if no URLs
                raw = {
                    'title': msg.subject or 'Car listing',
                    'price': None,
                    'mileage': None,
                    'year': None,
                    'fuel': None,
                    'gearbox': None,
                    'description': body,
                    'url': ''
                }
                photos = [a['content'] for a in msg.attachments if a.get('filename') and a['filename'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))][:10] if msg.attachments else []
                text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
                ok, err = send_car_post(settings, bot_token, text, photos)
                log = PostingLog(user_id=user.id, gmail_message_id=msg.uid, subject=msg.subject, car_title=raw['title'], raw_price=str(raw.get('price')), final_price=str(settings.price_markup_eur or ''), sent_to_channel=bool(ok), sent_at=(datetime.utcnow() if ok else None), error=(err if not ok else None))
                db.session.add(log)
                db.session.commit()
            else:
                # Process each mobile.de URL separately
                for url in mobile_urls:
                    listing = parse_mobile_de(url)
                    if not listing or not listing.get('photos'):
                        continue
                    if listing:
                        raw = {
                            'title': listing['title'],
                            'price': listing.get('price'),
                            'mileage': listing.get('mileage'),
                            'year': listing.get('year'),
                            'fuel': listing.get('fuel'),
                            'gearbox': listing.get('gearbox'),
                            'description': listing['description'],
                            'url': url,
                            'specs': listing.get('specs') or {}
                        }
                        photos = listing['photos']
                        text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
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


def process_user_inbox_once(user: User, messages=None):
    """Process inbox for a user once regardless of their auto_post_enabled flag (used for manual checks)."""
    settings = user.settings
    master_key = current_app.config.get('MASTER_SECRET_KEY')
    gmail_pwd = settings.gmail_app_password_decrypted if hasattr(settings, 'gmail_app_password_decrypted') and settings.gmail_app_password_decrypted else decrypt_secret(settings.gmail_app_password_encrypted, master_key) if settings and settings.gmail_app_password_encrypted else None
    openai_key = settings.openai_api_key_decrypted if hasattr(settings, 'openai_api_key_decrypted') and settings.openai_api_key_decrypted else decrypt_secret(settings.openai_api_key_encrypted, master_key) if settings and settings.openai_api_key_encrypted else None
    bot_token = settings.telegram_bot_token_decrypted if hasattr(settings, 'telegram_bot_token_decrypted') and settings.telegram_bot_token_decrypted else decrypt_secret(settings.telegram_bot_token_encrypted, master_key) if settings and settings.telegram_bot_token_encrypted else None

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

    if messages is None:
        messages = fetch_new_messages(settings)
    print(f"DEBUG: Processing {len(messages)} messages")
    for msg in messages:
        try:
            print(f"DEBUG: Processing message UID {msg.uid}, Subject: {msg.subject}")
            body = (msg.text_body or '') + '\n' + (msg.html_body or '')

            # Filter only mobile.de-related messages
            if 'mobile.de' not in (msg.from_addr or '').lower() and 'mobile.de' not in body.lower():
                # Skip non-mobile.de messages
                print(f"DEBUG: Skipping non-mobile.de message {msg.uid}")
                mark_message_seen(settings, msg.uid)
                continue

            # Filter only mobile.de-related messages/URLs
            urls = extract_urls(body)
            mobile_urls = list(set([u for u in urls if 'mobile.de' in u and ('/auto-inserat/' in u or 'click.news.mobile.de' in u) and not any(ext in u.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp'])]))
            print(f"DEBUG: Found {len(mobile_urls)} mobile.de URLs in message {msg.uid}")

            if not mobile_urls:
                # Fallback to old parsing if no URLs
                print(f"DEBUG: No URLs found, using fallback parsing for {msg.uid}")
                raw = {
                    'title': msg.subject or 'Car listing',
                    'price': None,
                    'mileage': None,
                    'year': None,
                    'fuel': None,
                    'gearbox': None,
                    'description': body,
                    'url': ''
                }
                photos = [a['content'] for a in msg.attachments if a.get('filename') and a['filename'].lower().endswith(('.jpg', '.jpeg', '.png', '.gif'))][:10] if msg.attachments else []
                text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
                ok, err = send_car_post(settings, bot_token, text, photos)
                print(f"DEBUG: Sent fallback post for {msg.uid}, success: {ok}, error: {err}")
                log = PostingLog(user_id=user.id, gmail_message_id=msg.uid, subject=msg.subject, car_title=raw['title'], raw_price=str(raw.get('price')), final_price=str(settings.price_markup_eur or ''), sent_to_channel=bool(ok), sent_at=(datetime.utcnow() if ok else None), error=(err if not ok else None))
                db.session.add(log)
                db.session.commit()
                time.sleep(1)  # Rate limit prevention
            else:
                # Process each mobile.de URL separately
                for url in mobile_urls:
                    print(f"DEBUG: Parsing URL {url} from message {msg.uid}")
                    listing = parse_mobile_de(url)
                    if not listing or not listing.get('photos'):
                        print(f"DEBUG: Skipping URL {url}, no photos or failed parsing")
                        continue
                    if listing:
                        print(f"DEBUG: Parsed listing: {listing['title']}")
                        raw = {
                            'title': listing['title'],
                            'price': listing.get('price'),
                            'mileage': listing.get('mileage'),
                            'year': listing.get('year'),
                            'fuel': listing.get('fuel'),
                            'gearbox': listing.get('gearbox'),
                            'description': listing['description'],
                            'url': url,
                            'specs': listing.get('specs') or {}
                        }
                        photos = listing['photos']
                        text = generate_listing_text(raw, settings.language or 'uk', settings.price_markup_eur or 0, openai_key)
                        ok, err = send_car_post(settings, bot_token, text, photos)
                        print(f"DEBUG: Sent post for {url}, success: {ok}, error: {err}")
                        log = PostingLog(user_id=user.id, gmail_message_id=msg.uid, subject=msg.subject, car_title=raw['title'], raw_price=str(raw.get('price')), final_price=str(settings.price_markup_eur or ''), sent_to_channel=bool(ok), sent_at=(datetime.utcnow() if ok else None), error=(err if not ok else None))
                        db.session.add(log)
                        db.session.commit()
                        time.sleep(1)  # Rate limit prevention
                    else:
                        print(f"DEBUG: Failed to parse listing from {url}")
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

