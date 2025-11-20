#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.utils.mobile_parser import parse_mobile_de

# Test with a sample mobile.de URL (replace with real one if available)
test_url = "https://www.mobile.de/ru/транспортные-средства/подробности.html?id=441737077&utm_content=teaser_ad_img_1&utm_source=mde_crm&utm_medium=email&utm_campaign=core_savedsearch_sfmc_v04__c-em-zz-z-c-a-a&acq_channel=email-link-svs-sf-v4&referer=email&trafficSource=sfmc&channel=email&placement=email-link-svs-sf-v4&ref=essCrmEmail"

print("Testing parse_mobile_de with:", test_url)
result = parse_mobile_de(test_url)
print("Result keys:", list(result.keys()))
for key, value in result.items():
    if key != 'photos':
        print(f"{key}: {value}")
    else:
        print(f"{key}: {len(value)} photos extracted")
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