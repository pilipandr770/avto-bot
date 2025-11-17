import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet(master_key: str | None):
    import base64
    import hashlib

    if not master_key:
        raise RuntimeError('MASTER_SECRET_KEY not configured')
    # Derive a 32-byte key from master_key and base64-encode it for Fernet
    digest = hashlib.sha256(master_key.encode()).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(plaintext: str, master_key: str):
    f = _get_fernet(master_key)
    token = f.encrypt(plaintext.encode())
    return token.decode()


def decrypt_secret(token: str, master_key: str):
    f = _get_fernet(master_key)
    try:
        return f.decrypt(token.encode()).decode()
    except InvalidToken:
        return None
