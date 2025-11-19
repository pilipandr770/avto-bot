import openai


def generate_listing_text(raw_data: dict, language: str, markup_eur: int, openai_api_key: str) -> str:
    """Generate a Telegram-ready listing text.

    raw_data keys (may be None):
      - title, price, mileage, year, fuel, gearbox, description, url, specs(dict)

    language: output language for the post (e.g. 'uk', 'ru', 'de').
    markup_eur: margin in EUR that should be added to the base price.
    """
    openai.api_key = openai_api_key

    base_price = raw_data.get('price') or ''
    try:
        price_num = int(''.join(ch for ch in str(base_price) if ch.isdigit()))
    except Exception:
        price_num = 0

    try:
        markup_value = int(markup_eur or 0)
    except Exception:
        markup_value = 0

    final_price = price_num + markup_value

    specs = raw_data.get('specs') or {}

    # Build a compact textual representation of key specs for the model
    if isinstance(specs, dict) and specs:
        specs_lines = []
        # Put the most important/typical fields first if present
        preferred_keys = [
            'Пробег', 'Первая регистрация', 'Объем двигателя', 'Мощность',
            'Топливо', 'Трансмиссия', 'Категория', 'Цвет', 'Кузов',
        ]
        used = set()
        for k in preferred_keys:
            if k in specs and specs[k]:
                specs_lines.append(f"{k}: {specs[k]}")
                used.add(k)
        # Add remaining specs
        for k, v in specs.items():
            if k in used or not v:
                continue
            specs_lines.append(f"{k}: {v}")
        specs_text = "\n".join(specs_lines)
    else:
        specs_text = "(no extra specs)"

    # System message to clearly instruct the model
    system_msg = (
        "You are an experienced automotive copywriter. "
        "You create engaging but concise car sale posts for a Telegram channel. "
        "Always write in the requested language."
    )

    # User message with detailed instructions and structured data
    user_msg = (
        f"Write a short Telegram post in language: {language}.\n"
        "Goal: create an attractive car sale listing for a Telegram channel.\n\n"
        "Requirements for the output:\n"
        "- Start with a catchy, short title (one line).\n"
        "- Then add a short bullet list with key specs (max 6 bullets).\n"
        "- Explicitly show the final sale price with euro symbol (e.g. '9 900 €').\n"
        "- Mention that the price already includes our margin.\n"
        "- Use friendly, trustworthy tone; avoid excessive emojis (0-2 max).\n"
        "- Do NOT use markdown other than simple bullet points and line breaks.\n"
        "- At the end of the post, add the link to the listing on a separate line.\n\n"
        "Source data for this car (you MUST rely on it, do not invent data):\n"
        f"Title: {raw_data.get('title')}\n"
        f"Base price from source (may be empty): {base_price}\n"
        f"Mileage (km): {raw_data.get('mileage')}\n"
        f"Year: {raw_data.get('year')}\n"
        f"Fuel: {raw_data.get('fuel')}\n"
        f"Gearbox: {raw_data.get('gearbox')}\n"
        f"Description from seller: {raw_data.get('description')}\n"
        f"URL: {raw_data.get('url')}\n"
        f"Our margin to add: {markup_value} EUR\n"
        f"Final sale price in EUR (already with margin): {final_price}\n\n"
        "Full technical specs (key = value, use only if helpful):\n"
        f"{specs_text}\n\n"
        "Now write the final post text in the requested language."
    )

    try:
        resp = openai.ChatCompletion.create(
            model='gpt-4o-mini' if hasattr(openai, 'ChatCompletion') else 'gpt-4',
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=500,
        )
        text = resp['choices'][0]['message']['content'].strip()
    except Exception:
        # fallback simple text in case OpenAI call fails
        price_str = f"{final_price} €" if final_price > 0 else ""
        text_lines = [
            str(raw_data.get('title') or '').strip(),
        ]
        if price_str:
            text_lines.append(f"Цена: {price_str}")
        if raw_data.get('url'):
            text_lines.append(str(raw_data.get('url')))
        text = "\n".join(line for line in text_lines if line)

    return text
