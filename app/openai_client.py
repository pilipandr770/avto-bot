import openai


def generate_listing_text(raw_data: dict, language: str, markup_eur: int, openai_api_key: str) -> str:
    # raw_data: {title, price, mileage, year, fuel, gearbox, description, url}
    openai.api_key = openai_api_key
    base_price = raw_data.get('price') or ''
    try:
        price_num = int(''.join(ch for ch in str(base_price) if ch.isdigit()))
    except Exception:
        price_num = 0
    final_price = price_num + int(markup_eur or 0)

    prompt = (
        f"You are a copywriter that writes short Telegram listing posts in {language}. "
        "Produce a short title, a bullet list of key specs, the price with euro symbol, and the link. "
        "Be friendly, concise and suited for a car sales channel. Do not add technical markdown other than simple bullets and emojis.\n\n"
    )
    prompt += f"Data:\nTitle: {raw_data.get('title')}\nPrice: {base_price}\nMileage: {raw_data.get('mileage')}\nYear: {raw_data.get('year')}\nFuel: {raw_data.get('fuel')}\nGearbox: {raw_data.get('gearbox')}\nDescription: {raw_data.get('description')}\nLink: {raw_data.get('url')}\nAdded markup: {markup_eur} EUR\nFinal price: {final_price} EUR\n\nCompose the listing text in {language}."

    try:
        resp = openai.ChatCompletion.create(
            model='gpt-4o-mini' if hasattr(openai, 'ChatCompletion') else 'gpt-4',
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
        )
        text = resp['choices'][0]['message']['content'].strip()
    except Exception:
        # fallback simple text
        text = f"{raw_data.get('title')}\nPrice: {final_price} €\n{raw_data.get('url')}"

    return text
