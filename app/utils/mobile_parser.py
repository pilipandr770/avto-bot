# app/utils/mobile_parser.py

import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/123.0.0.0 Safari/537.36"
}


def parse_mobile_de(url: str):
    """
    Парсер сторінки оголошення mobile.de з Selenium.

    Робить:
    - завантажує сторінку в headless Chrome;
    - чекає на завантаження;
    - знаходить JSON у <script id="__NEXT_DATA__" type="application/json">;
    - дістає з нього:
        * title
        * price
        * mileage
        * year (firstRegistration)
        * fuel
        * gearbox
        * power_kw
        * technical specs (dict)
        * description
        * до 10 фото (bytes) для Telegram sendMediaGroup.

    Повертає dict або None, якщо не вдалось розпарсити.
    """

    print(f"DEBUG: parse_mobile_de() fetching {url}")
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    try:
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        driver.get(url)
        time.sleep(10)  # Wait for JS to load
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        page_source = driver.page_source
        driver.quit()
    except Exception as e:
        print("DEBUG: Selenium failed:", e)
        return None

    soup = BeautifulSoup(page_source, "html.parser")

    # ---- JSON із даними оголошення ----
    script_tag = soup.find("script", type="application/json")
    if not script_tag:
        print("DEBUG: application/json script not found")
        return None
    script_tag = soup.find("script", type="application/json")
    if not script_tag:
        print("DEBUG: application/json script not found")
        return None

    try:
        data = json.loads(script_tag.string)
    except Exception as e:
        print("DEBUG: JSON load error:", e)
        return None

    # шлях до adDetail у mobile.de (React/Next.js)
    try:
        listing = data["props"]["pageProps"]["adDetail"]
    except KeyError:
        print("DEBUG: adDetail not found in JSON")
        return None

    # ---- Фотографії ----
    photos: list[bytes] = []

    try:
        images = listing["vehicleImages"]["images"]
        for img in images[:10]:       # максимум 10 фото
            img_url = img.get("url")
            if not img_url:
                continue
            try:
                img_resp = requests.get(img_url, headers=HEADERS, timeout=20)
                if img_resp.status_code == 200:
                    photos.append(img_resp.content)
            except Exception as e:
                print("DEBUG: image download error:", e)
                continue
    except Exception as e:
        print("DEBUG: images parse error:", e)

    # ---- Основні дані ----
    basic = listing.get("basicData", {})

    title = basic.get("modelDescription") or ""
    price = listing.get("price", {}).get("consumerPrice", {}).get("amount")
    mileage = basic.get("mileage")
    first_reg = basic.get("firstRegistration")
    fuel = basic.get("fuelType")
    gearbox = basic.get("transmissionType")
    power_kw = basic.get("kw")

    technical = listing.get("technicalData", {})

    specs = {
        "year": first_reg,
        "mileage": mileage,
        "fuel": fuel,
        "gearbox": gearbox,
        "power_kw": power_kw,
        "doors": technical.get("numberOfDoors"),
        "consumption": technical.get("fuelConsumptionCombined"),
        "co2": technical.get("co2EmissionCombined"),
        "emission_class": technical.get("emissionClass"),
    }

    description = listing.get("description", "") or ""

    return {
        "title": title,
        "price": price,
        "year": first_reg,
        "mileage": mileage,
        "fuel": fuel,
        "gearbox": gearbox,
        "power_kw": power_kw,
        "description": description,
        "specs": specs,
        "photos": photos,
    }