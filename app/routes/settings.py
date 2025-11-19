from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import UserSettings, PostingLog
from ..security import encrypt_secret, decrypt_secret
from ..telegram_client import ensure_channel_id
from ..gmail_client import _connect_imap, fetch_recent_mobilede_message
from ..extensions import scheduler
import openai
import json
try:
    import requests
except Exception:
    requests = None
import urllib.request
import urllib.error

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/')
@login_required
def index():
    """Settings index listing all per-user settings pages."""
    return render_template('settings/index.html')


@bp.route('/gmail', methods=['GET', 'POST'])
@login_required
def gmail():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
        if request.form.get('clear') == 'gmail':
            s.gmail_address = None
            s.gmail_app_password_encrypted = None
            PostingLog.query.filter_by(user_id=current_user.id).delete()
            db.session.add(s)
            db.session.commit()
            flash('Gmail settings and posting history cleared')
            return redirect(url_for('settings.gmail'))
        s.gmail_address = request.form.get('gmail_address')
        pwd = request.form.get('gmail_app_password')
        if pwd:
            s.gmail_app_password_encrypted = encrypt_secret(pwd, current_app.config.get('MASTER_SECRET_KEY'))
        db.session.add(s)
        db.session.commit()
        # test IMAP
        try:
            pwd_dec = decrypt_secret(s.gmail_app_password_encrypted, current_app.config.get('MASTER_SECRET_KEY'))
            im = _connect_imap(s.gmail_address, pwd_dec)
            im.logout()
            flash('IMAP connection OK')
        except Exception as e:
            flash('IMAP test failed: ' + str(e))
        return redirect(url_for('settings.gmail'))
    return render_template('settings/gmail.html', settings=s)


@bp.route('/gmail/check', methods=['POST'])
@login_required
def gmail_check():
    """Schedule an immediate mailbox check for the current user."""
    from flask import current_app
    from datetime import datetime
    from ..tasks import check_inbox_for_user_id, process_user_inbox_once
    from ..models import PostingLog

    user_id = current_user.id
    try:
        # Run check synchronously now and report number of posting logs created
        from flask import current_app as _current_app
        with _current_app.app_context():
            before = PostingLog.query.filter_by(user_id=user_id).count()
            # run processing once for the user
            process_user_inbox_once(current_user)
            after = PostingLog.query.filter_by(user_id=user_id).count()
            added = after - before
        flash(f'Mailbox check completed — {added} new posting(s) created')
    except Exception as e:
        flash('Mailbox check failed: ' + str(e))
    return redirect(url_for('settings.gmail'))


@bp.route('/gmail/test_old', methods=['POST'])
@login_required
def gmail_test_old():
    """Temporarily test processing of an existing mobile.de message.

    This looks through recent messages for ones that look like they are from
    mobile.de, runs the usual inbox processing once for the current user,
    and reports how many new postings were created. Intended only for
    manual testing and can be removed later.
    """
    from ..tasks import process_user_inbox_once

    user_id = current_user.id
    try:
        # Ensure Gmail password is decrypted for client use, similar to task code
        s = current_user.settings
        if not s:
            flash('No settings found for current user')
            return redirect(url_for('settings.gmail'))

        print(f"DEBUG: Starting test_old for user {user_id}")
        # Decrypt password if needed
        from app.security import decrypt_secret
        master_key = current_app.config.get('MASTER_SECRET_KEY')
        if s.gmail_app_password_encrypted:
            s.gmail_app_password_decrypted = decrypt_secret(s.gmail_app_password_encrypted, master_key)
        else:
            s.gmail_app_password_decrypted = None

        # Try to fetch at least one mobile.de-like message to confirm there is something to test
        msgs = fetch_recent_mobilede_message(s)
        print(f"DEBUG: fetch_recent_mobilede_message returned {len(msgs)} messages")
        if not msgs:
            flash('No recent mobile.de-like messages found in your inbox')
            return redirect(url_for('settings.gmail'))

        # Reuse existing one-off processing which already uses parse_listing_from_url
        process_user_inbox_once(current_user)
        flash('Tested processing of existing mobile.de messages. Check your Telegram channel and posting log.')
    except Exception as e:
        print(f"DEBUG: Error in test_old: {e}")
        flash('Test of old mobile.de messages failed: ' + str(e))
    return redirect(url_for('settings.gmail'))


@bp.route('/gmail/help')
@login_required
def gmail_help():
    """Show instructions to create a Gmail App Password and how to paste it back."""
    return render_template('settings/gmail_help.html')


@bp.route('/telegram', methods=['GET', 'POST'])
@login_required
def telegram():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
        if request.form.get('clear') == 'telegram':
            s.telegram_bot_token_encrypted = None
            s.telegram_channel_username = None
            s.telegram_channel_id = None
            db.session.add(s)
            db.session.commit()
            flash('Telegram settings cleared')
            return redirect(url_for('settings.telegram'))
        token = request.form.get('bot_token')
        channel = request.form.get('channel_username')
        if token:
            s.telegram_bot_token_encrypted = encrypt_secret(token, current_app.config.get('MASTER_SECRET_KEY'))
        s.telegram_channel_username = channel
        db.session.add(s)
        db.session.commit()
        # test bot
        try:
            token_dec = decrypt_secret(s.telegram_bot_token_encrypted, current_app.config.get('MASTER_SECRET_KEY'))
            cid = ensure_channel_id(s, token_dec)
            if cid:
                db.session.add(s)
                db.session.commit()
                flash('Telegram OK, channel id saved')
            else:
                flash('Could not resolve channel id; check username and bot permissions')
        except Exception as e:
            flash('Telegram test failed: ' + str(e))
        return redirect(url_for('settings.telegram'))
    # prepare masked token display
    masked = None
    try:
        if s and s.telegram_bot_token_encrypted:
            dec = decrypt_secret(s.telegram_bot_token_encrypted, current_app.config.get('MASTER_SECRET_KEY'))
            masked = '•' * (len(dec) - 4) + dec[-4:]
    except Exception:
        masked = None
    return render_template('settings/telegram.html', settings=s, masked_token=masked)


@bp.route('/openai', methods=['GET', 'POST'])
@login_required
def openai_settings():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
        if request.form.get('clear') == 'openai':
            s.openai_api_key_encrypted = None
            db.session.add(s)
            db.session.commit()
            flash('OpenAI settings cleared')
            return redirect(url_for('settings.openai_settings'))
        key = request.form.get('openai_api_key')
        if key:
            s.openai_api_key_encrypted = encrypt_secret(key, current_app.config.get('MASTER_SECRET_KEY'))
            db.session.add(s)
            db.session.commit()
            # test key by calling OpenAI REST API /models (works independent of client lib version)
            try:
                headers = {'Authorization': f'Bearer {key}'}
                url = 'https://api.openai.com/v1/models'
                ok = False
                msg = ''
                if requests:
                    r = requests.get(url, headers=headers, timeout=10)
                    ok = r.status_code == 200
                    msg = r.text
                else:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        data = resp.read()
                        ok = resp.getcode() == 200
                        msg = data.decode('utf-8')
                if ok:
                    flash('OpenAI key OK')
                else:
                    flash('OpenAI test failed: ' + (msg or 'unknown'))
            except urllib.error.HTTPError as e:
                try:
                    body = e.read().decode('utf-8')
                except Exception:
                    body = str(e)
                flash('OpenAI test failed: ' + body)
            except Exception as e:
                flash('OpenAI test failed: ' + str(e))
        return redirect(url_for('settings.openai_settings'))
    # masked key for display
    masked_key = None
    try:
        if s and s.openai_api_key_encrypted:
            dec = decrypt_secret(s.openai_api_key_encrypted, current_app.config.get('MASTER_SECRET_KEY'))
            masked_key = '•' * (len(dec) - 6) + dec[-6:]
    except Exception:
        masked_key = None
    return render_template('settings/openai.html', settings=s, masked_key=masked_key)


@bp.route('/posting', methods=['GET', 'POST'])
@login_required
def posting():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
        s.language = request.form.get('language')
        s.price_markup_eur = int(request.form.get('price_markup_eur') or 0)
        s.auto_post_enabled = bool(request.form.get('auto_post_enabled'))
        db.session.add(s)
        db.session.commit()
        flash('Posting settings saved')
        return redirect(url_for('settings.posting'))
    return render_template('settings/posting.html', settings=s)
