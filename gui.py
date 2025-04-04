import customtkinter as ctk
from tkinter import messagebox
import threading
from queue import Queue
import time
from app import search_items

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

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