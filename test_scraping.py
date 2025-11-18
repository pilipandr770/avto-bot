#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.tasks import parse_listing_from_url

# Test with a sample mobile.de URL (replace with real one if available)
test_url = "https://www.mobile.de/ru/транспортные-средства/подробности.html?id=441737077&utm_content=teaser_ad_img_1&utm_source=mde_crm&utm_medium=email&utm_campaign=core_savedsearch_sfmc_v04__c-em-zz-z-c-a-a&acq_channel=email-link-svs-sf-v4&referer=email&trafficSource=sfmc&channel=email&placement=email-link-svs-sf-v4&ref=essCrmEmail"

print("Testing parse_listing_from_url with:", test_url)
result = parse_listing_from_url(test_url)
print("Result:", result)