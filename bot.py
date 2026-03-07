import os
import asyncio
import yt_dlp
import nest_asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from playwright.async_api import async_playwright

nest_asyncio.apply()

# --- THE HACKER CONFIGURATION ---
TOKEN = "8096650971:AAGswGC1bgBuGi3XX7_oOZ6GhDiiqXE6jhM"
ADMIN_ID = 7144917062

user_otp = None

# ==========================================
# 🔑 LOGIN SYSTEM (With Jasoosi Screenshot)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("👋 Boss! Bot online hai. Login command: `/login 03xxxxxxxxx`", parse_mode='Markdown')

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
            # 🛡️ Anti-Bot Bypass Args
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            page = await context.new_page()
            
            await page.goto("https://cloud.jazzdrive.com.pk/login", timeout=60000)
            await asyncio.sleep(3) # Page load hone ka wait
            
            await page.fill('input[type="tel"]', num)
            await asyncio.sleep(1)
            await page.click('#signinbtn')
            
            await update.message.reply_text("📸 Button click ho gaya! Screen check kar raha hoon...")
            await asyncio.sleep(4) # JazzDrive ke response ka wait
            
            # 🕵️ THE JASOOSI SCREENSHOT 🕵️
            await page.screenshot(path="debug_login.png")
            try:
                await update.message.reply_photo(photo=open("debug_login.png", 'rb'), caption="👀 Boss, Playwright ko is waqt screen aisi nazar aa rahi hai!")
            except: pass
            
            await update.message.reply_text("🔢 Agar OTP aa gaya hai, toh jaldi se chat mein apna 4-digit OTP bhejein.")
            
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
            await update.message.reply_text("✅ Boss, Login 100% Successful!")
            user_otp = None
            await browser.close()
    except Exception as e:
        await update.message.reply_text(f"❌ Login Error: {e}")

# ==========================================
# 📥 MESSAGE HANDLER (Link & OTP Catcher)
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
            await update.message.reply_text("⚠️ Boss, pehle login toh kar lein! Command: /login 03xxxxxxxxx")
            return
        await process_youtube_link(text, update)
        return
        
    await update.message.reply_text("🤔 Boss, main sirf YouTube links aur 4-digit OTP samajhta hoon.")

# ==========================================
# 📺 QUALITY MENU & DOWNLOADER
# ==========================================
async def process_youtube_link(url, update):
    await update.message.reply_text("🔍 Video scan kar raha hoon...")
    ydl_opts = {'quiet': True, 'extractor_args': {'youtube': {'client': ['android', 'ios']}}}
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
    await query.edit_message_text(f"⏳ Downloading at {res}p... please wait.")
    
    filename = f"video_{res}.mp4"
    ydl_opts = {
        'format': f'bestvideo[height<={res}][ext=mp4]+bestaudio[ext=m4a]/best',
        'outtmpl': filename,
        'merge_output_format': 'mp4',
        'quiet': True,
        'extractor_args': {'youtube': {'client': ['android', 'ios']}}
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            await asyncio.to_thread(ydl.download, [url])
        await query.message.reply_text(f"✅ Download complete! Uploading to JazzDrive...")
        
        success = await upload_to_jazz(filename)
        if success: await query.message.reply_text("🎉 MISSION COMPLETE! Video Drive mein safe hai.")
        else: await query.message.reply_text("❌ Upload failed.")
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
