from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from ..extensions import db
from ..models import UserSettings
from ..security import encrypt_secret, decrypt_secret
from ..telegram_client import ensure_channel_id
from ..gmail_client import _connect_imap
import openai

bp = Blueprint('settings', __name__, url_prefix='/settings')


@bp.route('/gmail', methods=['GET', 'POST'])
@login_required
def gmail():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
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


@bp.route('/telegram', methods=['GET', 'POST'])
@login_required
def telegram():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
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
    return render_template('settings/telegram.html', settings=s)


@bp.route('/openai', methods=['GET', 'POST'])
@login_required
def openai_settings():
    s = current_user.settings or UserSettings(user_id=current_user.id)
    if request.method == 'POST':
        key = request.form.get('openai_api_key')
        if key:
            s.openai_api_key_encrypted = encrypt_secret(key, current_app.config.get('MASTER_SECRET_KEY'))
            db.session.add(s)
            db.session.commit()
            # test small request
            try:
                openai.api_key = key
                _ = openai.Model.list() if hasattr(openai, 'Model') else True
                flash('OpenAI key OK')
            except Exception as e:
                flash('OpenAI test failed: ' + str(e))
        return redirect(url_for('settings.openai_settings'))
    return render_template('settings/openai.html', settings=s)


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
