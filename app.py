import re
import json
from queue import Queue
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROFILE_PATH = os.path.join(os.getcwd(), "chrome_profile")
if not os.path.exists(PROFILE_PATH):
    os.makedirs(PROFILE_PATH)

PURCHASED_ITEMS_FILE = os.path.join(os.getcwd(), "purchased_items.json")
PURCHASED_ITEMS = {}
CHEAPEST_ITEMS = {}

def load_purchased_items():
    global PURCHASED_ITEMS
    try:
        if os.path.exists(PURCHASED_ITEMS_FILE):
            with open(PURCHASED_ITEMS_FILE, 'r', encoding='utf-8') as f:
                PURCHASED_ITEMS = json.load(f)
    except:
        pass

def save_purchased_item(item_data):
    try:
        PURCHASED_ITEMS[item_data['ListingID']] = item_data
        with open(PURCHASED_ITEMS_FILE, 'w', encoding='utf-8') as f:
            json.dump(PURCHASED_ITEMS, f, ensure_ascii=False, indent=4)
    except:
        pass

load_purchased_items()

def safe_get_text(parent, selector):
    try:
        element = parent.find_element(By.CSS_SELECTOR, selector)
        return element.text.strip()
    except:
        return "N/A"

def get_price(item):
    try:
        price = safe_get_text(item, ".price span.ng-star-inserted")
        if price == "N/A":
            price = safe_get_text(item, "div.price.ng-star-inserted")
        return price
    except:
        return "N/A"

def parse_price(price_str):
    try:
        clean = re.sub(r'[^\d.]', '', price_str)
        if not clean or clean == '.':
            return float('inf')
        return float(clean)
    except:
        return float('inf')

def scroll_until_end(driver, max_attempts=100, scroll_pause_time=2):
    try:
        last_item_count = 0
        no_new_item_count = 0  
        while no_new_item_count < 2 and max_attempts > 0:
            driver.execute_script("window.scrollBy(0, 2000);")
            time.sleep(scroll_pause_time)
            items = driver.find_elements(By.CSS_SELECTOR, "item-card")
            current_item_count = len(items)
            if current_item_count > last_item_count:
                no_new_item_count = 0 
            else:
                no_new_item_count += 1
            last_item_count = current_item_count
            max_attempts -= 1
    except:
        pass

def sanitize_filename(filename):
    try:
        return re.sub(r'[\\/:*?"<>|]', '_', filename)
    except:
        return "invalid_filename"

def get_listing_id(driver, item_element, log_queue):
    try:
        current_url_before = driver.current_url
        item_element.click()
        WebDriverWait(driver, 10).until(EC.url_changes(current_url_before))
        current_url = driver.current_url

        if "/item/" in current_url:
            listing_id = current_url.split("/")[-1]
            time.sleep(0.5)
            driver.back()
            time.sleep(0.5)
            WebDriverWait(driver, 10).until(EC.url_to_be(current_url_before))
            return listing_id, current_url
        return "N/A", "N/A"
    except:
        try:
            driver.back()
            WebDriverWait(driver, 5).until(EC.url_to_be(current_url_before))
        except:
            pass
        return "N/A", "N/A"