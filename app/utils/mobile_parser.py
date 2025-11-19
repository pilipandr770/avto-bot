import json
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options


def parse_mobile_de(url: str):
    """Parse mobile.de listing via JSON (__NEXT_DATA__). Extracts:
    - title
    - price
    - mileage
    - year
    - fuel
    - gearbox
    - technical specs
    - description
    - up to 10 photos (bytes)
    """

    print("DEBUG: Fetching URL with Selenium:", url)
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')

    driver = webdriver.Chrome(options=options)
    driver.get(url)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()

    # load main React JSON
    script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    print("DEBUG: Script tag found:", script_tag is not None)
    if not script_tag:
        return None

    try:
        data = json.loads(script_tag.string)
        print("DEBUG: JSON loaded, keys:", list(data.keys()))
    except Exception as e:
        print("DEBUG: JSON load failed:", e)
        return None

    try:
        listing = data["props"]["pageProps"]["adDetail"]
    except KeyError:
        return None

    # Photos
    photos = []
    try:
        imgs = listing["vehicleImages"]["images"]
        for img in imgs[:10]:
            img_url = img.get("url")
            if img_url:
                img_bytes = requests.get(img_url, headers=headers).content
                photos.append(img_bytes)
    except:
        pass

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

    description = listing.get("description", "")

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
        "photos": photos
    }