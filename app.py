import re
from queue import Queue
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROFILE_PATH = os.path.join(os.getcwd(), "chrome_profile")
if not os.path.exists(PROFILE_PATH):
    os.makedirs(PROFILE_PATH)

CHEAPEST_ITEMS = {}

def safe_get_text(parent, selector):
    try:
        element = parent.find_element(By.CSS_SELECTOR, selector)
        return element.text.strip()
    except Exception:
        return "N/A"

def get_price(item):
    price = safe_get_text(item, ".price span.ng-star-inserted")
    if price == "N/A":
        price = safe_get_text(item, "div.price.ng-star-inserted")
    return price

def parse_price(price_str):
    try:
        clean = re.sub(r'[^\d.]', '', price_str)
        if not clean or clean == '.':
            return float('inf')
        return float(clean)
    except Exception:
        return float('inf')

def scroll_until_end(driver, max_attempts=100, scroll_pause_time=2):
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

def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|]', '_', filename)

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

    except Exception as e:
        log_queue.put(f"Listing ID alınırken hata: {str(e)}")
        try:
            driver.back()
            WebDriverWait(driver, 5).until(EC.url_to_be(current_url_before))
        except:
            pass
    return "N/A", "N/A"