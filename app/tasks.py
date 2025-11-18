import traceback
from .extensions import scheduler, db
from .models import User, PostingLog
from .security import decrypt_secret
from .gmail_client import fetch_new_messages, mark_message_seen
from .openai_client import generate_listing_text
from .telegram_client import ensure_channel_id, send_car_post
from flask import current_app
from datetime import datetime
import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time


def extract_urls(text):
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)


def parse_listing_from_url(url):
    """Parse car listing from URL: extract title, description, photos."""
    try:
        # Set up Chrome options
        options = Options()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        # Initialize the driver
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        
        # Wait for the page to load
        time.sleep(3)  # Adjust as needed
        
        # Get the page source
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # Extract title
        title = soup.find('title').get_text().strip() if soup.find('title') else 'Car listing'
        
        # Extract description
        description = ''
        desc_divs = soup.find_all(['div', 'p'], class_=lambda c: c and ('description' in c.lower() or 'text' in c.lower() or 'desc' in c.lower()))
        if desc_divs:
            description = ' '.join([d.get_text().strip() for d in desc_divs])
        else:
            # Fallback
            description = soup.get_text().strip()
        
        # Extract photos
        photos = []
        for img in soup.find_all('img'):
            src = img.get('src') or img.get('data-src') or img.get('data-lazy-src')
            print(f"Found img src: {src}")
            if src and src.startswith('https://img.classistatic.de/'):  # Specific to mobile.de images
                try:
                    img_response = requests.get(src, timeout=10)
                    print(f"Status code: {img_response.status_code}, Content-Type: {img_response.headers.get('content-type')}")
                    if img_response.status_code == 200 and 'image' in img_response.headers.get('content-type', ''):
                        photos.append(img_response.content)
                        print(f"Downloaded photo: {src}")
                except Exception as e:
                    print(f"Error downloading {src}: {e}")
                if len(photos) >= 10:
                    break
        
        driver.quit()
        
        return {
            'title': title,
            'description': description,
            'photos': photos
        }
    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return None


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
            body = msg.text_body or msg.html_body or ''
            urls = extract_urls(body)
            if not urls:
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
                # Process each URL
                for url in urls:
                    listing = parse_listing_from_url(url)
                    if listing:
                        raw = {
                            'title': listing['title'],
                            'price': None,
                            'mileage': None,
                            'year': None,
                            'fuel': None,
                            'gearbox': None,
                            'description': listing['description'],
                            'url': url
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
            body = msg.text_body or msg.html_body or ''
            urls = extract_urls(body)
            if not urls:
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
                # Process each URL
                for url in urls:
                    listing = parse_listing_from_url(url)
                    if listing:
                        raw = {
                            'title': listing['title'],
                            'price': None,
                            'mileage': None,
                            'year': None,
                            'fuel': None,
                            'gearbox': None,
                            'description': listing['description'],
                            'url': url
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

