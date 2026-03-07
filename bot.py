import os
import asyncio
import yt_dlp
import nest_asyncio
import urllib.request
import urllib.parse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from playwright.async_api import async_playwright

nest_asyncio.apply()

# --- THE HACKER CONFIGURATION ---
TOKEN = "8096650971:AAGswGC1bgBuGi3XX7_oOZ6GhDiiqXE6jhM"
ADMIN_ID = 7144917062

user_otp = None

# ==========================================
# 📡 TELEGRAM SENDER (For TV Auth Code)
# ==========================================
def send_tg_msg(text):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode({'chat_id': ADMIN_ID, 'text': text}).encode('utf-8')
    try: urllib.request.urlopen(url, data=data)
    except: pass

class YtLogger:
    def debug(self, msg):
        if "google.com/device" in msg or "enter code" in msg.lower():
            send_tg_msg(f"📺 **YOUTUBE TV LOGIN REQUIRED** 📺\n\n{msg}\n\n👉 Jaldi se link open karein aur browser mein code daalein. Main yahin ruka hua hoon!")
        print(msg)
    def warning(self, msg):
        if "google.com/device" in msg or "enter code" in msg.lower():
            send_tg_msg(f"📺 **YOUTUBE TV LOGIN REQUIRED** 📺\n\n{msg}\n\n👉 Jaldi se link open karein aur code daalein!")
        print(msg)
    def error(self, msg):
        print(msg)

# ==========================================
# 🔑 LOGIN SYSTEM (JazzDrive)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("👋 Boss! The Ultimate TV-Auth Bot online hai.\n\nLogin command: `/login 03xxxxxxxxx`", parse_mode='Markdown')

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global user_otp
    user_otp = None

    if len(context.args) == 0:
        await update.message.reply_text("❌ Number missing hai! Aise likhein: /login 03001234567")
        return
    
    num = context.args[0]
    await update.message.reply_text("⏳ Playwright JazzDrive par ja raha hai... Please wait.")
    asyncio.create_task(playwright_login_task(num, update))

async def playwright_login_task(num, update):
    global user_otp
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
            page = await context.new_page()
            
            await page.goto("https://cloud.jazzdrive.com.pk/login", timeout=60000)
            await asyncio.sleep(3)
            await page.fill('input[type="tel"]', num)
            await asyncio.sleep(1)
            await page.click('#signinbtn')
            
            await update.message.reply_text("🔢 OTP bhej diya gaya hai! Chat mein apna 4-digit OTP bhejein.")
            
            wait_time = 0
            while user_otp is None and wait_time < 120:
                await asyncio.sleep(1)
                wait_time += 1
                
            if user_otp is None:
                await update.message.reply_text("❌ Timeout! OTP nahi mila.")
                await browser.close()
                return
                
            await page.evaluate(f'document.getElementById("otp").value = "{user_otp}"')
            await page.click('#signinbtn')
            await asyncio.sleep(8)
            
            await context.storage_state(path="jazz_cookies.json")
            await update.message.reply_text("✅ Boss, JazzDrive Login 100% Successful!")
            user_otp = None
            await browser.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Login Error: {e}")

# ==========================================
# 📥 MESSAGE HANDLER (Link & OTP)
# ==========================================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    global user_otp
    text = update.message.text.strip()
    
    if text.isdigit() and len(text) == 4:
        user_otp = text
        await update.message.reply_text("👍 OTP pakar liya! Login verify kar raha hoon...")
        return
        
    if "youtu.be" in text or "youtube.com" in text:
        if not os.path.exists("jazz_cookies.json"):
            await update.message.reply_text("⚠️ Boss, pehle JazzDrive login toh kar lein! Command: /login 03xxxxxxxxx")
            return
        await process_youtube_link(text, update)
        return
        
    await update.message.reply_text("🤔 Boss, main sirf YouTube links aur 4-digit OTP samajhta hoon.")

# ==========================================
# 📺 QUALITY MENU & DOWNLOADER (TV AUTH)
# ==========================================
async def process_youtube_link(url, update):
    await update.message.reply_text("🔍 Video scan kar raha hoon... (Agar YouTube ne roka toh TV Code bhejunga)")
    
    # 📺 YAHAN TV OAUTH2 ENABLE KIYA GAYA HAI
    ydl_opts = {
        'quiet': True, 
        'username': 'oauth2',
        'password': '',
        'logger': YtLogger(),
        'extractor_args': {'youtube': {'client': ['android', 'ios']}}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'YouTube Video')
            formats = sorted(list(set([f.get('height') for f in info.get('formats', []) if f.get('height')])), reverse=True)
            
        keyboard = [[InlineKeyboardButton(f"{res}p", callback_data=f"{res}|{url}")] for res in formats[:6]]
        await update.message.reply_text(f"🎬 {title}\n\n👉 Konsi quality chahiye?", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"❌ Scan Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query.from_user.id != ADMIN_ID: return
    await query.answer()
    res, url = query.data.split("|", 1)
    await query.edit_message_text(f"⏳ Downloading at {res}p... Pura zor lag raha hai!")
    
    filename = f"video_{res}.mp4"
    
    ydl_opts = {
        'format': f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': filename,
        'merge_output_format': 'mp4',
        'quiet': True,
        'username': 'oauth2',
        'password': '',
        'logger': YtLogger(),
        'extractor_args': {'youtube': {'client': ['android', 'ios']}}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        await query.message.reply_text(f"✅ Download complete! Uploading to JazzDrive...")
        
        success = await upload_to_jazz(filename)
        if success: await query.message.reply_text("🎉 MISSION COMPLETE! Video JazzDrive mein safe hai.")
        else: await query.message.reply_text("❌ Upload failed. Ek dafa Drive check karein.")
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")
    finally:
        if os.path.exists(filename): os.remove(filename)

# ==========================================
# ☁️ JAZZDRIVE UPLOADER
# ==========================================
async def upload_to_jazz(file_path):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = await browser.new_context(storage_state="jazz_cookies.json")
            page = await context.new_page()
            await page.goto("https://cloud.jazzdrive.com.pk/#folders", timeout=90000)
            await asyncio.sleep(5)
            
            async with page.expect_file_chooser() as fc_info:
                try: await page.click("/html/body/div/div/div[1]/div/header/div/div/button")
                except: await page.get_by_role("button", name="Upload").first.click()
            await (await fc_info.value).set_files(file_path)
            
            await page.wait_for_selector("text=completed", timeout=900000)
            await browser.close()
            return True
    except: return False

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.run_polling()
