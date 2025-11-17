import sys, os
from dotenv import load_dotenv
load_dotenv('.env.local')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app

app = create_app()
with app.app_context():
    client = app.test_client()
    # login as existing test user created earlier
    login_data = {'email': 'testuser@example.com', 'password': 'secret123'}
    client.post('/login', data=login_data, follow_redirects=True)
    # Save telegram token
    resp = client.post('/settings/telegram', data={'bot_token': '123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11', 'channel_username': '@mychannel'}, follow_redirects=True)
    print('Telegram save status:', resp.status_code)
    # Save openai key
    resp = client.post('/settings/openai', data={'openai_api_key': 'sk-testkey-0123456789abcdef'}, follow_redirects=True)
    print('OpenAI save status:', resp.status_code)
    # Check DB
    from app.models import UserSettings, User
    from app.extensions import db
    user = User.query.filter_by(email='testuser@example.com').first()
    us = UserSettings.query.filter_by(user_id=user.id).first()
    print('User id:', user.id)
    print('UserSettings present for user:', bool(us))
    if us:
        print('telegram encrypted len:', len(us.telegram_bot_token_encrypted) if us.telegram_bot_token_encrypted else None)
        print('openai encrypted len:', len(us.openai_api_key_encrypted) if us.openai_api_key_encrypted else None)
