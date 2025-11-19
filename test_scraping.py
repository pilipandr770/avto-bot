#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.tasks import parse_listing_from_url

# Test with a sample mobile.de URL (replace with real one if available)
test_url = "https://www.mobile.de/ru/транспортные-средства/подробности.html?id=441737077&utm_content=teaser_ad_img_1&utm_source=mde_crm&utm_medium=email&utm_campaign=core_savedsearch_sfmc_v04__c-em-zz-z-c-a-a&acq_channel=email-link-svs-sf-v4&referer=email&trafficSource=sfmc&channel=email&placement=email-link-svs-sf-v4&ref=essCrmEmail"

print("Testing parse_listing_from_url with:", test_url)
result = parse_listing_from_url(test_url)
print("Result keys:", list(result.keys()))
for key, value in result.items():
    if key != 'photos':
        print(f"{key}: {value}")
    else:
        print(f"{key}: {len(value)} photos extracted")

# Debug: print some HTML
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
import time
from bs4 import BeautifulSoup

options = Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
options.add_argument('--window-size=1920,1080')
options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
driver.get(test_url)
time.sleep(5)
driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
time.sleep(2)
page_source = driver.page_source
soup = BeautifulSoup(page_source, 'html.parser')

print("Page source contains 'Пробег':", 'Пробег' in page_source)
print("Page source contains '116 000':", '116 000' in page_source)
print("Page source contains 'Бензин':", 'Бензин' in page_source)
print("Page source contains 'Механика':", 'Механика' in page_source)
print("Page source contains '06/2020':", '06/2020' in page_source)

texts_with_probeg = [t.strip() for t in soup.find_all(text=True) if 'Пробег' in t]
print("Texts with Пробег:", texts_with_probeg)

print("H1:", soup.find('h1').get_text() if soup.find('h1') else 'No h1')

strongs = soup.find_all('strong')
print("Strong texts:", [s.get_text().strip() for s in strongs[:10]])  # First 10

# Look for specific
mileage_strong = soup.find('strong', string=lambda t: t and 'Пробег' in t)
print("Mileage strong:", mileage_strong)
if mileage_strong:
    print("Parent:", mileage_strong.parent.get_text())

driver.quit()