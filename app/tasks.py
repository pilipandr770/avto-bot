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
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import time
import json
import codecs


def extract_urls(text):
    """Extract URLs from text."""
    url_pattern = r'https?://[^\s]+'
    return re.findall(url_pattern, text)


def parse_listing_from_url(url):
    """Parse car listing from URL: extract title, description, photos, price, technical details."""
    try:
        # Set up Chrome options
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)

        time.sleep(5)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

        page_source = driver.page_source
        # TEMP: dump full HTML for debugging selectors (price/mileage, etc.)
        try:
            with open('debug_listing.html', 'w', encoding='utf-8') as f:
                f.write(page_source)
        except Exception as dump_err:
            print(f"Failed to write debug_listing.html: {dump_err}")

        soup = BeautifulSoup(page_source, 'html.parser')

        # Title and subtitle
        title_el = soup.select_one('[data-testid="main-cta-box"] h2')
        subtitle_el = soup.select_one('.MainCtaBox_subTitle__wYybO')
        if title_el:
            base_title = title_el.get_text(strip=True)
            subtitle = subtitle_el.get_text(strip=True) if subtitle_el else ''
            title = f"{base_title} {subtitle}".strip()
        else:
            title = soup.find('title').get_text(strip=True) if soup.find('title') else 'Car listing'

        # Price: universal search for text with '€', then HTML fallbacks
        price_text = None
        try:
            # First, try any element containing the currency sign
            price_elem = driver.find_element(By.XPATH, "//*[contains(text(), '€')]")
            price_text = price_elem.text.strip()
        except Exception:
            price_text = None

        # Fallbacks via parsed HTML if Selenium lookup fails
        if not price_text:
            price_el = soup.select_one('[data-testid="main-price-area"] .MainPriceArea_mainPrice__xCkfs')
            if price_el:
                price_text = price_el.get_text(strip=True)
        if not price_text:
            sticky_price_el = soup.select_one('[data-testid="sticky-cta-img"] p.typography_title__TamOM')
            if sticky_price_el:
                price_text = sticky_price_el.get_text(strip=True)
        if not price_text:
            cta_price_el = soup.select_one('.MainCtaBox_content__AXZbK .typography_headlineLarge__jywu0')
            if cta_price_el:
                price_text = cta_price_el.get_text(strip=True)

        # As a last resort, search raw HTML text for a pattern like "2999 €"
        if not price_text:
            m_raw = re.search(r"\d[\d\s]*€", page_source)
            if m_raw:
                price_text = m_raw.group(0).strip()

        price = None
        if price_text:
            m = re.search(r"(\d[\d\s]*)", price_text)
            if m:
                try:
                    price = int(m.group(1).replace(' ', ''))
                except ValueError:
                    price = None

        # Key features (mileage, fuel, gearbox, first registration)
        def get_key_feature_value(testid):
            container = soup.select_one(f'[data-testid="{testid}"] .KeyFeatures_value__8LVNc')
            return container.get_text(strip=True) if container else None

        mileage_text = get_key_feature_value('vip-key-features-list-item-mileage')
        fuel = get_key_feature_value('vip-key-features-list-item-fuel')
        gearbox = get_key_feature_value('vip-key-features-list-item-transmission')
        first_reg_text = get_key_feature_value('vip-key-features-list-item-firstRegistration')

        mileage = None
        if mileage_text:
            m = re.search(r"(\d[\d\s]*)", mileage_text)
            if m:
                try:
                    mileage = int(m.group(1).replace(' ', ''))
                except ValueError:
                    mileage = None

        # Technical data box: collect all specs and also fallback mileage/year
        specs = {}
        tech_box = soup.select_one('[data-testid="vip-technical-data-box"]')
        if tech_box:
            # Prefer structured dt/dd pairs when available
            dts = tech_box.select('dt')
            for dt in dts:
                key = dt.get_text(strip=True)
                dd = dt.find_next_sibling('dd')
                if not dd:
                    continue
                value = dd.get_text(" ", strip=True)
                if key and value:
                    specs[key] = value

            # Helper to get dd text by dt data-testid for known keys
            def get_tech_value(testid):
                dt = tech_box.select_one(f'dt[data-testid="{testid}"]')
                if dt:
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        return dd.get_text(strip=True)
                return None

            if mileage is None:
                mileage_text2 = get_tech_value('mileage-item')
                if mileage_text2:
                    m2 = re.search(r"(\d[\d\s]*)", mileage_text2)
                    if m2:
                        try:
                            mileage = int(m2.group(1).replace(' ', ''))
                        except ValueError:
                            mileage = None

            if not first_reg_text:
                first_reg_text = get_tech_value('firstRegistration-item')

        # If specs still empty, try heading-based Russian "Технические сведения" block
        if not specs:
            heading = soup.find('h3', string=lambda t: t and 'Технические сведения' in t)
            if heading:
                container = heading.find_next('div')
                if container:
                    lines = container.get_text("\n", strip=True).split("\n")
                    for line in lines:
                        if not line.strip():
                            continue
                        if ':' in line:
                            k, v = line.split(':', 1)
                            specs[k.strip()] = v.strip()
                        else:
                            parts = line.split()
                            if len(parts) > 1:
                                k = parts[0]
                                v = " ".join(parts[1:])
                                specs[k.strip()] = v.strip()

        # Fallback mileage from specs (e.g. 'Пробег': '171 278 км')
        if mileage is None and specs.get('Пробег'):
            m = re.search(r"(\d[\d\s]*)", specs['Пробег'])
            if m:
                try:
                    mileage = int(m.group(1).replace(' ', ''))
                except ValueError:
                    mileage = None

        year = None
        if first_reg_text:
            m = re.search(r"(\d{4})", first_reg_text)
            if m:
                try:
                    year = int(m.group(1))
                except ValueError:
                    year = None

        # Description
        desc_el = soup.select_one('[data-testid="vip-vehicle-description-text"]')
        description = desc_el.get_text("\n", strip=True) if desc_el else ''

        # Photos from gallery (download bytes) and also collect URLs
        photos = []
        photo_urls = []

        # Prefer gallery images by class, fallback to data-testid
        img_elements = soup.select('img.GalleryImage__image')
        if not img_elements:
            img_elements = soup.select('[data-testid^="image-"] img')

        for img in img_elements[:10]:
            src = img.get('src') or img.get('data-src') or ''
            if not src:
                continue
            photo_urls.append(src)
            try:
                resp = requests.get(src, timeout=10)
                if resp.status_code == 200 and 'image' in (resp.headers.get('content-type') or ''):
                    photos.append(resp.content)
            except Exception as e:
                print(f"Error downloading image {src}: {e}")

        driver.quit()

        return {
            'title': title,
            'description': description,
            'price': price,
            'mileage': mileage,
            'year': year,
            'fuel': fuel,
            'gearbox': gearbox,
            'photos': photos,
            'photo_urls': photo_urls,
            'specs': specs,
        }
    except Exception as e:
        # Soft mode: try to fall back to plain requests + BeautifulSoup
        print(f"Error parsing with Selenium for {url}: {e}")
        try:
            resp = requests.get(url, timeout=20, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })
            if resp.status_code != 200:
                return None

            html = resp.text
            soup = BeautifulSoup(html, 'html.parser')

            # Basic title / description
            title_el = soup.find('h1') or soup.find('h2') or soup.find('title')
            title = title_el.get_text(strip=True) if title_el else 'Car listing'

            desc_el = soup.select_one('[data-testid="vip-vehicle-description-text"]')
            description = desc_el.get_text("\n", strip=True) if desc_el else ''

            # Soft price: search for pattern like "2999 €" in text
            price = None
            m_raw = re.search(r"\d[\d\s]*€", html)
            if m_raw:
                price_text = m_raw.group(0)
                m_num = re.search(r"(\d[\d\s]*)", price_text)
                if m_num:
                    try:
                        price = int(m_num.group(1).replace(' ', ''))
                    except ValueError:
                        price = None

            # Minimal specs via technical data box, if present
            specs = {}
            tech_box = soup.select_one('[data-testid="vip-technical-data-box"]')
            if tech_box:
                dts = tech_box.select('dt')
                for dt in dts:
                    key = dt.get_text(strip=True)
                    dd = dt.find_next_sibling('dd')
                    if not dd:
                        continue
                    value = dd.get_text(" ", strip=True)
                    if key and value:
                        specs[key] = value

            mileage = None
            if specs.get('Пробег'):
                m = re.search(r"(\d[\d\s]*)", specs['Пробег'])
                if m:
                    try:
                        mileage = int(m.group(1).replace(' ', ''))
                    except ValueError:
                        mileage = None

            year = None
            if specs.get('Первая регистрация'):
                m = re.search(r"(\d{4})", specs['Первая регистрация'])
                if m:
                    try:
                        year = int(m.group(1))
                    except ValueError:
                        year = None

            # In soft mode we skip image downloads to avoid extra load
            photos = []
            photo_urls = []

            return {
                'title': title,
                'description': description,
                'price': price,
                'mileage': mileage,
                'year': year,
                'fuel': None,
                'gearbox': None,
                'photos': photos,
                'photo_urls': photo_urls,
                'specs': specs,
            }
        except Exception as e2:
            print(f"Soft fallback also failed for {url}: {e2}")
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

            # Filter only mobile.de-related messages/URLs
            urls = extract_urls(body)
            mobile_urls = [u for u in urls if 'mobile.de' in u]

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
                    listing = parse_listing_from_url(url)
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


def process_user_inbox_once(user: User):
    """Process inbox for a user once regardless of their auto_post_enabled flag (used for manual checks)."""
    print(f"DEBUG: Starting process_user_inbox_once for user {user.id}")
    settings = user.settings
    master_key = current_app.config.get('MASTER_SECRET_KEY')
    gmail_pwd = decrypt_secret(settings.gmail_app_password_encrypted, master_key) if settings and settings.gmail_app_password_encrypted else None
    openai_key = decrypt_secret(settings.openai_api_key_encrypted, master_key) if settings and settings.openai_api_key_encrypted else None
    bot_token = decrypt_secret(settings.telegram_bot_token_encrypted, master_key) if settings and settings.telegram_bot_token_encrypted else None

    # attach decrypted attrs for client use
    if settings:
        settings.gmail_app_password_decrypted = gmail_pwd

    if not (settings and settings.gmail_address and gmail_pwd and openai_key and bot_token and settings.telegram_channel_username):
        print("DEBUG: Missing settings or credentials")
        return

    try:
        cid = ensure_channel_id(settings, bot_token)
        if cid:
            db.session.add(settings)
            db.session.commit()
    except Exception:
        pass

    messages = fetch_new_messages(settings)
    print(f"DEBUG: Fetched {len(messages)} new messages")
    for msg in messages:
        try:
            print(f"DEBUG: Processing message UID {msg.uid}: {msg.subject}")
            body = msg.text_body or msg.html_body or ''

            # Filter only mobile.de-related messages/URLs
            urls = extract_urls(body)
            mobile_urls = [u for u in urls if 'mobile.de' in u]
            print(f"DEBUG: Found {len(mobile_urls)} mobile.de URLs in message {msg.uid}")

            if not mobile_urls:
                print(f"DEBUG: No mobile.de URLs, using fallback for message {msg.uid}")
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
                    listing = parse_listing_from_url(url)
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
    print(f"DEBUG: Finished process_user_inbox_once for user {user.id}")


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

