import os
import sys
import time
import threading
import queue
import builtins
import telebot
import yt_dlp  # 🔥 THE ULTIMATE 403 BYPASS ENGINE
from playwright.sync_api import sync_playwright

# 🔑 Aapki Details
TOKEN = "8096650971:AAGswGC1bgBuGi3XX7_oOZ6GhDiiqXE6jhM"
CHAT_ID = "7144917062"
bot = telebot.TeleBot(TOKEN)

# ==========================================
# 🤖 BOT LOGIC & QUEUE SYSTEM
# ==========================================
task_queue = queue.Queue()
is_working = False
user_context = {"state": "IDLE", "number": None, "otp": None}

@bot.message_handler(func=lambda message: str(message.chat.id) != str(CHAT_ID))
def block_strangers(message):
    bot.reply_to(message, "🚫 Access Denied! You are not the Admin.")

@bot.message_handler(commands=['start', 'status'])
def welcome_status(message):
    bot.send_message(CHAT_ID, f"🤖 **GOD MODE ACTIVATED (yt-dlp Engine)**\n📊 Queue: {task_queue.qsize()} | Working: {is_working}\n🔗 Send YouTube Link to start!")

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
    
    # --- 1. DOWNLOAD YOUTUBE (yt-dlp 403 Bypass) ---
    try:
        bot.send_message(CHAT_ID, "⬇️ Bypassing 403 Error & Downloading (High Quality)...")
        
        # yt-dlp ki khufiya settings jo YouTube block nahi kar sakta
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[m4a]/best[ext=mp4]/best', # Best Quality
            'outtmpl': '%(title)s_%(id)s.%(ext)s', # File ka naam
            'restrictfilenames': True,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info)
            
        bot.send_message(CHAT_ID, f"✅ Downloaded: {filename}")
        
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ YT Error: {str(e)[:150]}")
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
            
            while not page.locator("text=Uploads completed").is_visible():
                time.sleep(2)
                
            bot.send_message(CHAT_ID, f"🎉 Upload Success: {filename}")
            browser.close()
            
    except Exception as e:
        bot.send_message(CHAT_ID, f"❌ Upload Failed: {str(e)[:100]}")
    finally:
        if os.path.exists(filename): 
            os.remove(filename)

bot.polling(non_stop=True)
