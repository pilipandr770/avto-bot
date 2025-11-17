from dotenv import load_dotenv
import os, sys
load_dotenv('.env.local')
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from app import create_app
from app.models import PostingLog

app = create_app()
with app.app_context():
    rows = PostingLog.query.order_by(PostingLog.created_at.desc()).limit(10).all()
    if not rows:
        print('No posting logs found')
    for p in rows:
        print(f'id={p.id} user_id={p.user_id} gmail_msg={p.gmail_message_id} sent={p.sent_to_channel} sent_at={p.sent_at} error={p.error}')
