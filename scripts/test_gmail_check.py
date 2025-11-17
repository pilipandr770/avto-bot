from dotenv import load_dotenv
import os, sys
load_dotenv('.env.local')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

app = create_app()
with app.test_client() as c:
    # login
    resp = c.post('/login', data={'email':'testuser@example.com','password':'secret123'}, follow_redirects=True)
    print('login status', resp.status_code)
    resp = c.post('/settings/gmail/check', follow_redirects=True)
    print('gmail check status', resp.status_code)
    print('response contains flash:', 'Mailbox check scheduled' in resp.get_data(as_text=True) or 'Failed to schedule' in resp.get_data(as_text=True))
