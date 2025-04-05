import time
from selenium.webdriver.common.by import By

def login(driver, log_queue):
    try:
        login_buttons = driver.find_elements(By.XPATH, "//button[contains(., 'Sign in')]")
        if not login_buttons:
            log_queue.put("Giriş yapılmış gibi görünüyor")
            return True

        log_queue.put("Giriş yapılıyor...")
        login_buttons[0].click()
        
        max_wait = 120
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                header = driver.find_element(By.XPATH,
                    "//div[contains(@class, 'header') and contains(text(), 'Revolutionize Your CS2 Trading Experience with CSFloat')]")
                if header.is_displayed():
                    log_queue.put("Giriş başarılı!")
                    return True
            except Exception:
                pass
            time.sleep(1)
        
        log_queue.put("Giriş zaman aşımı")
        return False
    except Exception as e:
        log_queue.put(f"Giriş hatası: {str(e)}")
        return False