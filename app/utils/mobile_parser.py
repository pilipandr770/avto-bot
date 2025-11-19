import json
import requests
from bs4 import BeautifulSoup


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

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    resp = requests.get(url, headers=headers, timeout=20)
    if resp.status_code != 200:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # load main React JSON
    script_tag = soup.find("script", id="__NEXT_DATA__", type="application/json")
    if not script_tag:
        return None

    try:
        data = json.loads(script_tag.string)
    except:
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