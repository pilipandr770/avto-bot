import imaplib
import email
from email import policy
from typing import List


class EmailMessageData:
    def __init__(self, uid, subject, text_body, html_body, attachments):
        self.uid = uid
        self.subject = subject
        self.text_body = text_body
        self.html_body = html_body
        self.attachments = attachments


def _connect_imap(address: str, password: str):
    mail = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    mail.login(address, password)
    return mail


def fetch_new_messages(user_settings) -> List[EmailMessageData]:
    address = user_settings.gmail_address
    password = user_settings.gmail_app_password_decrypted if hasattr(user_settings, 'gmail_app_password_decrypted') else None
    if not address or not password:
        return []

    mail = _connect_imap(address, password)
    mail.select('INBOX')
    typ, data = mail.search(None, 'UNSEEN')
    messages = []
    for num in data[0].split():
        typ, msg_data = mail.fetch(num, '(RFC822)')
        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw, policy=policy.default)
        subject = str(msg.get('subject', ''))
        text_body = ''
        html_body = ''
        attachments = []
        for part in msg.walk():
            ctype = part.get_content_type()
            if part.is_multipart():
                continue
            content_disposition = part.get_content_disposition()
            payload = part.get_payload(decode=True)
            if content_disposition == 'attachment' or (part.get_filename()):
                attachments.append({'filename': part.get_filename(), 'content': payload})
            elif ctype == 'text/plain':
                text_body += payload.decode(errors='ignore')
            elif ctype == 'text/html':
                html_body += payload.decode(errors='ignore')

        messages.append(EmailMessageData(uid=num.decode(), subject=subject, text_body=text_body, html_body=html_body, attachments=attachments))

    mail.close()
    mail.logout()
    return messages


def fetch_recent_mobilede_message(user_settings) -> List[EmailMessageData]:
    """Fetch recent messages that look like they are from mobile.de (for testing).

    This searches the last 20 messages in INBOX and returns those where
    either the From header contains 'mobile.de' or the body contains 'mobile.de'.
    """
    address = user_settings.gmail_address
    password = user_settings.gmail_app_password_decrypted if hasattr(user_settings, 'gmail_app_password_decrypted') else None
    if not address or not password:
        return []

    mail = _connect_imap(address, password)
    mail.select('INBOX')

    # Search all, then take the last 20 UIDs
    typ, data = mail.search(None, 'ALL')
    if typ != 'OK':
        mail.close()
        mail.logout()
        return []

    all_uids = data[0].split()
    if not all_uids:
        mail.close()
        mail.logout()
        return []

    sample_uids = all_uids[-20:]
    messages: List[EmailMessageData] = []

    for num in sample_uids:
        try:
            typ, msg_data = mail.fetch(num, '(RFC822)')
            if typ != 'OK':
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw, policy=policy.default)
            from_header = str(msg.get('from', '')).lower()
            subject = str(msg.get('subject', ''))
            text_body = ''
            html_body = ''
            attachments = []

            for part in msg.walk():
                ctype = part.get_content_type()
                if part.is_multipart():
                    continue
                content_disposition = part.get_content_disposition()
                payload = part.get_payload(decode=True)
                if content_disposition == 'attachment' or (part.get_filename()):
                    attachments.append({'filename': part.get_filename(), 'content': payload})
                elif ctype == 'text/plain':
                    if payload:
                        text_body += payload.decode(errors='ignore')
                elif ctype == 'text/html':
                    if payload:
                        html_body += payload.decode(errors='ignore')

            body_combined = (text_body or '') + '\n' + (html_body or '')
            if 'mobile.de' in from_header or 'mobile.de' in body_combined.lower():
                messages.append(EmailMessageData(uid=num.decode(), subject=subject, text_body=text_body, html_body=html_body, attachments=attachments))
        except Exception:
            continue

    mail.close()
    mail.logout()
    return messages


def mark_message_seen(user_settings, uid: str):
    address = user_settings.gmail_address
    password = user_settings.gmail_app_password_decrypted if hasattr(user_settings, 'gmail_app_password_decrypted') else None
    if not address or not password:
        return
    mail = _connect_imap(address, password)
    mail.select('INBOX')
    try:
        mail.store(uid, '+FLAGS', '\\Seen')
    except Exception:
        pass
    mail.close()
    mail.logout()
