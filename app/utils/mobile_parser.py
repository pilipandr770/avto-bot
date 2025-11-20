# app/utils/mobile_parser.py

import json
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36"
}


def parse_mobile_de(url: str):
    """
    Парсер сторінки оголошення mobile.de з HTML.

    Робить:
    - завантажує HTML сторінки оголошення;
    - витягує title, price, specs, description, photos з HTML;
    - повертає dict або None, якщо не вдалось розпарсити.
    """

    print(f"DEBUG: parse_mobile_de() fetching {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20, allow_redirects=True)
    except Exception as e:
        print("DEBUG: request failed:", e)
        return None

    final_url = resp.url
    print(f"DEBUG: final url {final_url}")

    if resp.status_code != 200:
        print("DEBUG: bad status code:", resp.status_code)
        return None

    if "/fahrzeuge/details.html" not in final_url:
        print(f"DEBUG: final url is not a details page, skipping: {final_url}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # ---- title ----
    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else ""

    # ---- price ----
    price_el = soup.find(attrs={"data-testid": "prime-price"}) or \
               soup.find(attrs={"data-testid": "price"})
    price = None
    if price_el:
        txt = price_el.get_text(strip=True)
        # залишаємо тільки цифри
        digits = "".join(ch for ch in txt if ch.isdigit())
        if digits:
            price = int(digits)

    # ---- technical data block ----
    specs = {}
    # приклад – береш конкретний селектор з твоєї сторінки:
    rows = soup.select("[data-testid='vdp-tech-data'] dl") or \
           soup.select("dl")  # TODO: замінити на реальний селектор
    for row in rows:
        dts = row.find_all("dt")
        dds = row.find_all("dd")
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True)
            v = dd.get_text(strip=True)
            specs[k] = v

    # З цих specs можна витягнути рік, пробіг, паливо, коробку – по ключам або regex
    year = None
    mileage = None
    fuel = None
    gearbox = None
    power_kw = None
    for k, v in specs.items():
        if "Erstzulassung" in k or "year" in k.lower():
            year = v
        elif "Kilometerstand" in k or "mileage" in k.lower():
            digits = "".join(ch for ch in v if ch.isdigit())
            if digits:
                mileage = int(digits)
        elif "Kraftstoffart" in k or "fuel" in k.lower():
            fuel = v
        elif "Getriebeart" in k or "gearbox" in k.lower():
            gearbox = v
        elif "Leistung" in k or "power" in k.lower():
            digits = "".join(ch for ch in v if ch.isdigit())
            if digits:
                power_kw = int(digits)

    description_el = soup.find(attrs={"data-testid": "description"}) or \
                     soup.find("section", attrs={"id": "description"})
    description = description_el.get_text("\n", strip=True) if description_el else ""

    # ---- photos ----
    photos = []
    img_tags = soup.select("[data-testid='image-gallery'] img") or \
               soup.select("img[src*='mobile.de']")
    for img in img_tags[:10]:
        img_url = img.get("src") or img.get("data-src")
        if not img_url or not img_url.startswith("http"):
            continue
        try:
            img_resp = requests.get(img_url, headers=HEADERS, timeout=20)
            if img_resp.status_code == 200:
                photos.append(img_resp.content)
        except Exception as e:
            print("DEBUG: image download error:", e)

    return {
        "title": title,
        "price": price,
        "year": year,
        "mileage": mileage,
        "fuel": fuel,
        "gearbox": gearbox,
        "power_kw": power_kw,
        "description": description,
        "specs": specs,
        "photos": photos,
    }