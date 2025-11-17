import sys
import os
from dotenv import load_dotenv

# ensure project root is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app

load_dotenv('.env.local')
app = create_app()

with app.app_context():
    client = app.test_client()

    # Register
    reg_data = {'email': 'testuser@example.com', 'password': 'secret123'}
    resp = client.post('/register', data=reg_data, follow_redirects=False)
    print('Register status:', resp.status_code)
    if resp.status_code in (301, 302):
        print('Register redirected to:', resp.headers.get('Location'))
    else:
        print('Register response length:', len(resp.get_data(as_text=True)))

    # Login
    login_data = {'email': 'testuser@example.com', 'password': 'secret123'}
    resp = client.post('/login', data=login_data, follow_redirects=False)
    print('Login status:', resp.status_code)
    print('Login Location:', resp.headers.get('Location'))

    # Check accessing dashboard (requires login)
    # Use follow_redirects to ensure we get final page
    resp = client.post('/login', data=login_data, follow_redirects=True)
    print('Login follow_redirects status:', resp.status_code)
    # After login, try dashboard
    dash = client.get('/')
    print('Dashboard GET status:', dash.status_code)
    print('Dashboard content snippet:', dash.get_data(as_text=True)[:200])

    # Check user exists in DB
    from app.extensions import db
    from app.models import User
    u = User.query.filter_by(email='testuser@example.com').first()
    print('User in DB:', bool(u), 'id=', getattr(u, 'id', None))
