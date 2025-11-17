from telegram import Bot, InputMediaPhoto


def ensure_channel_id(user_settings, bot_token: str):
    bot = Bot(token=bot_token)
    username = user_settings.telegram_channel_username
    if not username:
        return None
    try:
        chat = bot.get_chat(username)
        user_settings.telegram_channel_id = chat.id
        return chat.id
    except Exception:
        return None


def send_car_post(user_settings, bot_token: str, text: str, photos: list):
    bot = Bot(token=bot_token)
    chat_id = user_settings.telegram_channel_id or user_settings.telegram_channel_username
    try:
        if photos:
            # send first photo with caption
            first = photos[0]
            if isinstance(first, bytes):
                bot.send_photo(chat_id=chat_id, photo=first, caption=text)
            else:
                bot.send_photo(chat_id=chat_id, photo=first, caption=text)
        else:
            bot.send_message(chat_id=chat_id, text=text)
        return True, None
    except Exception as e:
        return False, str(e)
