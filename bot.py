import os
import sys
import time
import threading
import queue
import builtins
import telebot
from pytubefix import YouTube
from pytubefix.helpers import safe_filename
from playwright.sync_api import sync_playwright

# 🔑 Aapki Details
TOKEN = "8096650971:AAGswGC1bgBuGi3XX7_oOZ6GhDiiqXE6jhM"
CHAT_ID = "7144917062"
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 🛑 THE INPUT HIJACKER (Bypassing EOF Error)
# ==========================================
auth_done = False

@bot.message_handler(commands=['done'])
def mark_done(message):
    global auth_done
    if str(message.chat.id) == str(CHAT_ID):
        auth_done = True
        bot.reply_to(message, "✅ **OK! Resuming the bot now...**")

def ghost_input(prompt=""):
    global auth_done
    auth_done = False
    
    # Jab YouTube enter dabane ka kahega toh bot pause ho jayega
    bot.send_message(
        CHAT_ID, 
        f"⏳ **BOT PAUSED!**\nSystem is waiting... \n\n👉 Jab aap code verify kar lein, toh yahan `/done` likh kar bhejein taake main aage chalu!"
    )
    
    # Loop tab tak chalega jab tak aap /done nahi bhejte
    while not auth_done:
        time.sleep(2)
    return ""

# System ke original input ko apne ghost_input se badal diya
builtins.input = ghost_input

# ==========================================
# 👁️ THE GHOST WHISPERER (Terminal Hijacker)
# ==========================================
class ConsoleSpy:
    def __init__(self):
        self.original_stdout = sys.stdout
        
    def write(self, text):
        self.original_stdout.write(text)
        
        # YouTube ka device link aate hi Telegram par bhej dega
        if "google.com/device" in text:
            try:
                bot.send_message(
                    CHAT_ID, 
                    f"🚨 **YOUTUBE LOGIN REQUIRED** 🚨\n\n```text\n{text.strip()}\n```",
                    parse_mode="Markdown"
                )
            except: pass
            
    def flush(self):
        self.original_stdout.flush()

sys.stdout = ConsoleSpy()

# ==========================================
# 🤖 BOT LOGIC & QUEUE SYSTEM
# ==========================================
task_queue = queue.Queue()
is_working = False
user_context = {"state": "IDLE", "number": None, "otp": None}

# 🛡️ THE IRON SHIELD: Ajnabi logon ko block karega
@bot.message_handler(func=lambda message: str(message.chat.id) != str(CHAT_ID))
def block_strangers(message):
    bot.reply_to(message, "🚫 Access Denied! You are not the Admin.")

@bot.message_handler(commands=['start', 'status'])
def welcome_status(message):
    bot.send_message(CHAT_ID, f"🤖 **GOD MODE ACTIVATED**\n📊 Queue: {task_queue.qsize()} | Working: {is_working}\n🔗 Send YouTube Link to start!")

# 📩 Text Handler (Links aur JazzDrive OTP ke liye)
@bot.message_handler(func=lambda m: str(m.chat.id) == str(CHAT_ID) and not m.text.startswith('/'))
def handle_msg(message):
    global is_working
    text = message.text.strip()
    
    if user_context["state"] == "WAITING_FOR_NUMBER":
        user_context["number"] = text
        user_context["state"] = "NUMBER_RECEIVED"
    elif user_context["state"] == "WAITING_FOR_OTP":
        user_context["otp"] = text
        user_context["state"] = "OTP_RECEIVED"
    elif text.startswith("http"):
        task_queue.put(text)
        bot.reply_to(message, f"✅ Added to Queue! Position: {task_queue.qsize()}")
        if not is_working:
            threading.Thread(target=worker_loop).start()

def worker_loop():
    global is_working
    is_working = True
    while not task_queue.empty():
        link = task_queue.get()
        process_video(link)
        task_queue.task_done()
    is_working = False
    bot.send_message(CHAT_ID, "💤 All tasks done. Going to sleep.")

def process_video(link):
    bot.send_message(CHAT_ID, f"🎬 Processing: {link}")
    
    # --- 1. DOWNLOAD YOUTUBE ---
    try:
        bot.send_message(CHAT_ID, "⬇️ Downloading YouTube Video...")
        # Yahan OAuth code print hoga aur bot pause hoga agar zaroorat hui
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True)
        stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
        
        if not stream:
            bot.send_message(CHAT_ID, "❌ Koi suitable video quality nahi mili.")
            return
            
        filename = f"{safe_filename(yt.title)}.mp4"
        stream.download(filename=filename)
        bot.send_message(CHAT_ID, f"✅ Downloaded: {filename}")
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ YT Error: {e}")
        return

    # --- 2. UPLOAD TO JAZZDRIVE ---
    bot.send_message(CHAT_ID, "⬆️ Uploading to JazzDrive...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(storage_state="state.json" if os.path.exists("state.json") else None)
            page = context.new_page()
            
            page.goto("https://cloud.jazzdrive.com.pk/#folders", timeout=90000)
            time.sleep(4)
            
            # --- JAZZDRIVE LOGIN LOGIC ---
            if page.locator("input[type='tel']").is_visible():
                bot.send_message(CHAT_ID, "🔑 JazzDrive Login Required! Enter Number (03xxxxxxxxx):")
                user_context["state"] = "WAITING_FOR_NUMBER"
                while user_context["state"] != "NUMBER_RECEIVED": time.sleep(1)
                
                page.locator("input[type='tel']").fill(user_context["number"])
                page.locator('#signinbtn').click()
                
                bot.send_message(CHAT_ID, "🔢 OTP bhejein:")
                user_context["state"] = "WAITING_FOR_OTP"
                while user_context["state"] != "OTP_RECEIVED": time.sleep(1)
                
                page.evaluate(f'document.getElementById("otp").value = "{user_context["otp"]}"')
                page.locator('#signinbtn').click()
                time.sleep(8)
                
                context.storage_state(path="state.json")
                bot.send_message(CHAT_ID, "✅ JazzDrive Login Saved!")

            # --- UPLOAD PROCESS ---
            page.get_by_role("button").filter(has_text="Upload").first.click()
            time.sleep(2)
            with page.expect_file_chooser() as fc_info:
                page.click("/html/body/div[2]/div[3]/div/div/form/div/div/div/div[1]")
            fc_info.value.set_files(os.path.abspath(filename))
            
            # Jab tak "Uploads completed" nahi likha aata, wait karega
            while not page.locator("text=Uploads completed").is_visible():
                time.sleep(2)
                
            bot.send_message(CHAT_ID, f"🎉 Upload Success: {filename}")
            browser.close()
            
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Upload Failed: {str(e)[:100]}")
    finally:
        if os.path.exists(filename): 
            os.remove(filename)

# Bot ko 24/7 zinda rakhne ki command
bot.polling(non_stop=True)
