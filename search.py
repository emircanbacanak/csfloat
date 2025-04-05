import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.action_chains import ActionChains
from app import CHEAPEST_ITEMS, get_listing_id, get_price, parse_price, safe_get_text, sanitize_filename
from login import login

PROFILE_PATH = os.path.join(os.getcwd(), "chrome_profile")
if not os.path.exists(PROFILE_PATH):
    os.makedirs(PROFILE_PATH)

def complete_purchase(driver, log_queue):
    try:
        # 1. Adım: Sepet butonuna tıkla ve popup'ın açılmasını bekle
        cart_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.hoverable-btn")))
        cart_button.click()
        log_queue.put("Sepet butonuna tıklandı, popup bekleniyor...")
        
        # 2. Adım: Popup'ın tamamen yüklenmesi için bekleyelim
        time.sleep(3)  # Popup'ın animasyonu için ekstra bekleme
        
        # 3. Adım: Tüm sayfayı tarayarak "I agree" kutucuğunu bulmaya çalışalım
        try:
            # Önce tüm checkbox'ları bulalım
            checkboxes = driver.find_elements(By.TAG_NAME, "mat-checkbox")
            log_queue.put(f"Bulunan checkbox sayısı: {len(checkboxes)}")
            
            # "I agree" text'ini içeren checkbox'ı bulmaya çalışalım
            target_checkbox = None
            for checkbox in checkboxes:
                try:
                    if "I agree" in checkbox.text:
                        target_checkbox = checkbox
                        break
                except:
                    continue
            
            if target_checkbox:
                # JavaScript ile tıklama yapalım
                driver.execute_script("arguments[0].click();", target_checkbox)
                log_queue.put("'I agree' kutucuğu JavaScript ile tıklandı")
                
                # Kontrol edelim
                checkbox_input = target_checkbox.find_element(By.TAG_NAME, "input")
                if checkbox_input.is_selected():
                    log_queue.put("'I agree' kutucuğu başarıyla işaretlendi")
                else:
                    # Alternatif tıklama yöntemi
                    target_checkbox.click()
                    log_queue.put("'I agree' kutucuğu normal click ile tıklandı")
            else:
                log_queue.put("'I agree' text'li checkbox bulunamadı")
                return False
            
            time.sleep(1)
            
            # 4. Adım: Buy Now butonunu bul ve tıkla
            buttons = driver.find_elements(By.TAG_NAME, "button")
            buy_now_button = None
            for button in buttons:
                if "Buy Now" in button.text:
                    buy_now_button = button
                    break
            
            if buy_now_button:
                driver.execute_script("arguments[0].scrollIntoView();", buy_now_button)
                buy_now_button.click()
                log_queue.put("Buy Now butonuna tıklandı")
                
                # Satın alma işleminin tamamlanmasını bekle
                log_queue.put("Satın alma işlemi tamamlanıyor, 60 saniye bekleniyor...")
                time.sleep(60)
                return True
            else:
                log_queue.put("Buy Now butonu bulunamadı")
                return False
                
        except Exception as e:
            log_queue.put(f"Popup işlemleri sırasında hata: {str(e)}")
            return False
            
    except Exception as e:
        log_queue.put(f"Satın alma işlemi sırasında beklenmeyen hata: {str(e)}")
        return False
def search_items(queries, log_queue):
    grouped_queries = {}
    for q in queries:
        if not q.strip():
            continue
        try:
            name, condition, limit_str = q.rsplit("|", 2)
            name = name.strip()
            condition = condition.strip()
            limit_price = parse_price(limit_str.strip())
        except Exception:
            log_queue.put(f"Hatalı format: {q}. Format 'Ürün Adı | Condition | Limit Fiyat' şeklinde olmalı.")
            continue
        
        if name in grouped_queries:
            grouped_queries[name].append((condition, limit_price))
        else:
            grouped_queries[name] = [(condition, limit_price)]
    
    if not grouped_queries:
        log_queue.put("Geçerli arama girdisi bulunamadı.")
        log_queue.put("ENABLE_START_BUTTON")
        return

    options = Options()
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    options.add_argument("--profile-directory=Default")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--remote-debugging-port=9222")
    
    driver = webdriver.Chrome(service=ChromeService(ChromeDriverManager().install()), options=options)
    log_queue.put("Tarayıcı başlatıldı.")
    
    driver.get("https://csfloat.com/search")
    
    if not login(driver, log_queue):
        log_queue.put("Giriş yapılamadı! İşlem durduruluyor.")
        driver.quit()
        log_queue.put("ENABLE_START_BUTTON")
        return

    for name, condition_list in grouped_queries.items():
        log_queue.put(f"{name}: Yeni sekmede arama başlatılıyor...")
        
        driver.execute_script("window.open('about:blank', '_blank');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get("https://csfloat.com/search")

        search_box = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search for items...']")))
        search_box.clear()
        search_box.send_keys(name)
        search_box.send_keys(Keys.RETURN)
        time.sleep(2)

        for condition, limit_price in condition_list:
            log_queue.put(f"{name} | {condition}: Filtreleme yapılıyor (Limit: {limit_price} TL)...")
            
            try:
                filter_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//div[@mattooltip='{condition}']")))
                filter_button.click()
                time.sleep(1)
                
                sort_menu = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//mat-select[@id='mat-select-2']")))
                sort_menu.click()
                time.sleep(1)
                
                lowest_price_option = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//mat-option[@value='lowest_price']//span[contains(text(), 'Lowest Price')]")))
                lowest_price_option.click()
                time.sleep(2)
                
                items = WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.CSS_SELECTOR, "item-card")))
                
                found_item = None
                for item in items:
                    try:
                        price = get_price(item)
                        if "No Bids" not in price:
                            item_name = safe_get_text(item, ".item-name")
                            item_condition = safe_get_text(item, ".subtext")
                            
                            if name.lower() in item_name.lower() and condition.lower() in item_condition.lower():
                                current_price = parse_price(price)
                                
                                if current_price <= limit_price:
                                    actions = ActionChains(driver)
                                    actions.move_to_element(item).perform()
                                    time.sleep(1)
                                    
                                    buttons_to_check = [
                                        ".//button[contains(@class, 'cart-btn') and contains(., 'Add to Cart')]",
                                        ".//button[contains(@class, 'mat-mdc-raised-button') and contains(@class, 'mat-primary')]"
                                    ]
                                    
                                    clicked = False
                                    for button_xpath in buttons_to_check:
                                        try:
                                            button = item.find_element(By.XPATH, button_xpath)
                                            if button.is_displayed():
                                                button.click()
                                                time.sleep(1)
                                                clicked = True
                                                break
                                        except Exception:
                                            continue
                                    
                                    if clicked:
                                        listing_id, item_url = get_listing_id(driver, item, log_queue)
                                        
                                        found_item = {
                                            "ListingID": listing_id,
                                            "URL": item_url,
                                            "Name": item_name,
                                            "Condition": item_condition,
                                            "Price": price,
                                            "AddableToCart": True
                                        }
                                        log_queue.put(f"{name} | {condition}: Sepete eklenebilir ürün bulundu ve sepete eklendi!")
                                        
                                        # Satın alma işlemini başlat
                                        if complete_purchase(driver, log_queue):
                                            log_queue.put(f"{name} | {condition}: Satın alma işlemi başarıyla tamamlandı!")
                                        else:
                                            log_queue.put(f"{name} | {condition}: Satın alma işlemi tamamlanamadı!")
                                        
                                        break
                                    
                    except Exception as e:
                        log_queue.put(f"{name} | {condition}: İşlem sırasında hata: {str(e)}")
                        continue
                
                if not found_item:
                    log_queue.put(f"{name} | {condition}: Uygun ilan bulunamadı (Fiyat ≤ {limit_price} ve sepete eklenebilir).")
                    continue
                
                cheapest_price = parse_price(found_item["Price"])
                if cheapest_price == limit_price:
                    result_note = f"Ürün {cheapest_price} TL'den, belirtilen limit fiyat olan {limit_price} TL'den alındı."
                elif cheapest_price < limit_price:
                    result_note = f"Ürün {cheapest_price} TL'den, limit fiyatından düşük olduğu için alındı."
                
                record = {
                    "ListingID": found_item["ListingID"],
                    "URL": found_item["URL"],
                    "Name": found_item["Name"],
                    "Condition": found_item["Condition"],
                    "Price": found_item["Price"],
                    "LimitPrice": limit_price,
                    "Note": result_note,
                    "AddableToCart": found_item["AddableToCart"],
                    "Purchased": True
                }

                key = f"{name}_{condition}"
                CHEAPEST_ITEMS[key] = record
                log_queue.put(f"{name} | {condition}: İşlem başarılı! Fiyat: {cheapest_price} TL")
                
                filename = sanitize_filename(f"cheapest_{name}_{condition}.json")
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=4)

            except Exception as e:
                log_queue.put(f"{name} | {condition}: İşlem sırasında hata oluştu: {str(e)}")
                continue
    
    time.sleep(5)
    driver.quit()
    log_queue.put("Tüm aramalar tamamlandı.")
    log_queue.put("ENABLE_START_BUTTON")