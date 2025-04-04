import re
import customtkinter as ctk
from tkinter import messagebox
import threading
from queue import Queue
import time
import os
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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
        clean = re.sub(r'[^\d,\.]', '', price_str)
        clean = clean.replace(',', '.')
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

def login(driver, log_queue):
    try:
        login_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Sign in')]")
        if not login_buttons:
            log_queue.put("Giriş butonu bulunamadı, zaten giriş yapılmış olabilir.")
            return True

        log_queue.put("Giriş yapılıyor...")
        login_buttons[0].click()
        max_wait = 120
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                header = driver.find_element(By.XPATH,
                    "//div[contains(@class, 'header') and contains(text(), 'Revolutionize Your CS2 Trading Experience with CSFloat')]"
                )
                if header.is_displayed():
                    log_queue.put("Giriş başarılı!")
                    return True
            except Exception:
                pass
            time.sleep(1)
        log_queue.put("Giriş işlemi zaman aşımına uğradı.")
        return False
    except Exception as e:
        log_queue.put(f"Giriş kontrolünde hata: {e}")
        return False

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

    service = Service("chromedriver.exe")
    options = Options()
    options.add_argument("--log-level=3")
    options.add_argument("--start-maximized")
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    options.add_argument("--profile-directory=Default")
    driver = webdriver.Chrome(service=service, options=options)
    
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
            EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Search for items...']"))
        )
        search_box.clear()
        search_box.send_keys(name)
        search_box.send_keys(Keys.RETURN)
        time.sleep(2)

        for condition, limit_price in condition_list:
            log_queue.put(f"{name} | {condition}: Filtre butonuna tıklanıyor...")
            try:
                filter_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, f"//div[@mattooltip='{condition}']"))
                )
                filter_button.click()
                time.sleep(1) 
            except Exception as e:
                log_queue.put(f"{name} | {condition}: Filtre butonu bulunamadı! Hata: {e}")
                continue

            log_queue.put(f"{name} | {condition}: Arama sonuçları yükleniyor, sayfa sonuna kaydırılıyor...")
            scroll_until_end(driver)
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)

            log_queue.put(f"{name} | {condition}: Arama tamamlandı. Sonuçlar toplanıyor...")
            items = driver.find_elements(By.CSS_SELECTOR, "item-card")
            total_items = len(items)
            log_queue.put(f"{name} | {condition}: Toplam {total_items} item kartı bulundu.")
            
            filtered_items = []
            for item in items:
                try:
                    item_name = safe_get_text(item, ".item-name")
                    item_condition = safe_get_text(item, ".subtext")
                    price = get_price(item)
                    if "No Bids" in price:
                        continue
                    if name.lower() in item_name.lower() and condition.lower() in item_condition.lower():
                        listing_id, item_url = get_listing_id(driver, item, log_queue)
                        filtered_items.append({
                            "ListingID": listing_id,
                            "URL": item_url,
                            "Name": item_name,
                            "Condition": item_condition,
                            "Price": price
                        })
                except Exception as e:
                    log_queue.put(f"Ürün işlenirken hata: {str(e)}")
                    continue
            log_queue.put(f"{name} | {condition}: {len(filtered_items)} eşleşen ilan bulundu.")
            
            if filtered_items:
                cheapest_item = None
                cheapest_price = float('inf')
                for item in filtered_items:
                    price_val = parse_price(item["Price"])
                    if price_val < cheapest_price:
                        cheapest_price = price_val
                        cheapest_item = item

                result_note = ""
                if cheapest_price == limit_price:
                    result_note = f"Ürün {cheapest_price} TL'den, kullanıcının belirttiği limit fiyat olan {limit_price} TL'den alınacak."
                elif cheapest_price < limit_price:
                    result_note = f"Ürün {cheapest_price} TL'den, kullanıcının limit fiyatından düşük olduğu için alınacak."
                else:
                    result_note = f"Ürün fiyatı {cheapest_price} TL, limit fiyat {limit_price} TL'nin üzerinde; satın alma yapılmayacak."
                
                record = {
                    "ListingID": cheapest_item["ListingID"],
                    "URL": cheapest_item["URL"],
                    "Name": cheapest_item["Name"],
                    "Condition": cheapest_item["Condition"],
                    "Price": cheapest_item["Price"],
                    "LimitPrice": limit_price,
                    "Note": result_note
                }

                
                key = f"{name}_{condition}"
                if key in CHEAPEST_ITEMS:
                    prev_price = parse_price(CHEAPEST_ITEMS[key]["Price"])
                    if cheapest_price < prev_price:
                        CHEAPEST_ITEMS[key] = record
                        log_queue.put(f"{name} | {condition}: Daha ucuz bir ilan bulundu! Eski fiyat: {prev_price}, Yeni fiyat: {cheapest_price}")
                    else:
                        log_queue.put(f"{name} | {condition}: Bulunan en ucuz ilan {cheapest_price}, önceki ile aynı veya daha pahalı.")
                else:
                    CHEAPEST_ITEMS[key] = record
                    log_queue.put(f"{name} | {condition}: İlk en ucuz ilan kaydedildi, fiyat: {cheapest_price}")

                filename = sanitize_filename(f"cheapest_{name}_{condition}.json")
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(record, f, ensure_ascii=False, indent=4)
            else:
                log_queue.put(f"{name} | {condition}: Hiç ilan bulunamadı.")
    
    driver.quit()
    log_queue.put("Tüm aramalar tamamlandı.")
    log_queue.put("ENABLE_START_BUTTON")
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CSFloat Arama Uygulaması")
        self.geometry("650x700")
        self.queue = Queue()
        self.timer_running = False 

        self.entry = ctk.CTkEntry(self, placeholder_text="Ürün adı girin", width=350)
        self.entry.pack(pady=10)
        
        self.condition_options = ["Factory New", "Minimal Wear", "Field-Tested", "Well-Worn", "Battle-Scarred"]
        self.condition_var = ctk.StringVar(value=self.condition_options[0])
        self.condition_menu = ctk.CTkOptionMenu(self, values=self.condition_options, variable=self.condition_var, width=350)
        self.condition_menu.pack(pady=10)

        self.limit_entry = ctk.CTkEntry(self, placeholder_text="Limit Fiyatı girin", width=350)
        self.limit_entry.pack(pady=10)
        self.add_button = ctk.CTkButton(self, text="Ekle", command=self.add_item)
        self.add_button.pack(pady=5)
        
        self.listbox = ctk.CTkTextbox(self, width=350, height=150)
        self.listbox.pack(pady=10)
        self.listbox.bind("<ButtonRelease-1>", self.on_select)
        self.button_frame = ctk.CTkFrame(self)
        self.button_frame.pack(pady=10)
        
        self.remove_button = ctk.CTkButton(self.button_frame, text="Sil", command=self.remove_item, fg_color="red")
        self.remove_button.pack(side="left", padx=10)
        self.start_button = ctk.CTkButton(self.button_frame, text="Aramaya Başla", command=self.start_search)
        self.start_button.pack(side="right", padx=10)
        
        self.timer_frame = ctk.CTkFrame(self)
        self.timer_frame.pack(pady=10)
        
        self.hour_entry = ctk.CTkEntry(self.timer_frame, placeholder_text="Saat", width=80)
        self.hour_entry.grid(row=0, column=0, padx=5)
        self.minute_entry = ctk.CTkEntry(self.timer_frame, placeholder_text="Dakika", width=80)
        self.minute_entry.grid(row=0, column=1, padx=5)
        
        self.start_timer_button = ctk.CTkButton(self.timer_frame, text="Timer Başlat", command=self.start_timer)
        self.start_timer_button.grid(row=0, column=2, padx=5)
        self.stop_timer_button = ctk.CTkButton(self.timer_frame, text="Timer Durdur", command=self.stop_timer)
        self.stop_timer_button.grid(row=0, column=3, padx=5)
        
        self.log_text = ctk.CTkTextbox(self, width=600, height=200)
        self.log_text.pack(pady=10)
        
        self.after(100, self.process_queue)
        self.selected_index = None

    def add_item(self):
        name = self.entry.get().strip()
        condition = self.condition_var.get().strip()
        limit_price = self.limit_entry.get().strip()
        if name and condition and limit_price:
            self.listbox.insert("end", f"{name} | {condition} | {limit_price}\n")
            self.entry.delete(0, "end")
            self.limit_entry.delete(0, "end")
        else:
            messagebox.showwarning("Uyarı", "Lütfen tüm alanları doldurun.")
    
    def remove_item(self):
        if self.selected_index is not None:
            text = self.listbox.get("1.0", "end").strip().split("\n")
            del text[self.selected_index]
            self.listbox.delete("1.0", "end")
            for line in text:
                self.listbox.insert("end", line + "\n")
            self.selected_index = None
    
    def on_select(self, event):
        try:
            index = self.listbox.index("@%d,%d" % (event.x, event.y)).split(".")[0]
            self.selected_index = int(index) - 1
        except Exception:
            pass
    
    def start_search(self):
        items = self.listbox.get("1.0", "end").strip().split("\n")
        if not items or items == [""]:
            messagebox.showwarning("Uyarı", "Lütfen ürün ekleyin.")
            return
        
        self.start_button.configure(state="disabled")
        self.log("Arama başlatılıyor...")
        threading.Thread(target=self.run_searches, args=(items,), daemon=True).start()
    
    def run_searches(self, items):
        threading.Thread(target=search_items, args=(items, self.queue), daemon=True).start()
    
    def start_timer(self):
        try:
            hours = int(self.hour_entry.get()) if self.hour_entry.get() else 0
            minutes = int(self.minute_entry.get()) if self.minute_entry.get() else 0
            interval = hours * 3600 + minutes * 60
            if interval <= 0:
                messagebox.showwarning("Uyarı", "Lütfen geçerli bir zaman aralığı girin.")
                return
            self.timer_running = True
            threading.Thread(target=self.run_timer, args=(interval,), daemon=True).start()
            self.log(f"Timer başlatıldı, aralık: {interval} saniye.")
        except Exception as e:
            messagebox.showerror("Hata", str(e))
    
    def stop_timer(self):
        self.timer_running = False
        self.log("Timer durduruldu.")
    
    def run_timer(self, interval):
        while self.timer_running:
            items = self.listbox.get("1.0", "end").strip().split("\n")
            if items and items != [""]:
                self.log("Timer tetikleniyor, arama yapılıyor...")
                search_items(items, self.queue)
            else:
                self.log("Timer: Ürün listesi boş, arama yapılmadı.")
            elapsed = 0
            while elapsed < interval and self.timer_running:
                time.sleep(1)
                elapsed += 1
    
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.queue.put(f"[{timestamp}] {message}")
    
    def process_queue(self):
        while not self.queue.empty():
            message = self.queue.get()
            if message == "ENABLE_START_BUTTON":
                self.start_button.configure(state="normal")
            else:
                self.log_text.insert("end", message + "\n")
                self.log_text.yview("end")
        self.after(100, self.process_queue)

if __name__ == "__main__":
    app = App()
    app.mainloop()