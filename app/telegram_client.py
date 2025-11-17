import requests
import json


def _telegram_api_call(token: str, method: str, **kwargs):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if 'data' in kwargs:
        response = requests.post(url, data=kwargs['data'], files=kwargs.get('files'))
    else:
        response = requests.get(url, params=kwargs)
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Telegram API error: {response.text}")


def ensure_channel_id(user_settings, bot_token: str):
    username = user_settings.telegram_channel_username
    if not username:
        return None
    try:
        result = _telegram_api_call(bot_token, 'getChat', chat_id=username)
        if result.get('ok'):
            chat = result['result']
            user_settings.telegram_channel_id = chat['id']
            return chat['id']
    except Exception:
        pass
    return None


def send_car_post(user_settings, bot_token: str, text: str, photos: list):
    chat_id = user_settings.telegram_channel_id or user_settings.telegram_channel_username
    if not chat_id:
        return False, "No chat ID or username"
    try:
        if photos:
            # For simplicity, send text only if photos, but actually send photo with caption
            # Assuming photos are URLs or bytes, but for now, send text
            # To send photo, need to upload file
            # For now, send message
            _telegram_api_call(bot_token, 'sendMessage', chat_id=chat_id, text=text)
        else:
            _telegram_api_call(bot_token, 'sendMessage', chat_id=chat_id, text=text)
        return True, None
    except Exception as e:
        return False, str(e)
