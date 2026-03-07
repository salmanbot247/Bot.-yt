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

# Global variable OTP ke liye
user_otp = None

# ==========================================
# 🔑 LOGIN SYSTEM (In-Chat OTP)
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Security Check: Sirf Boss (Aap) use kar sakte hain
    if update.effective_user.id != ADMIN_ID:
        return
        
    await update.message.reply_text(
        "👋 Boss! Aapka apna Private GitHub Bot online aa gaya hai.\n\n"
        "👉 Sab se pehle login karein. Ye command likhein:\n"
        "`/login 03xxxxxxxxx`", parse_mode='Markdown'
    )

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    
    global user_otp
    user_otp = None  # Purana OTP reset

    if len(context.args) == 0:
        await update.message.reply_text("❌ Number missing hai! Aise likhein: /login 03001234567")
        return
    
    num = context.args[0]
    await update.message.reply_text("⏳ Playwright JazzDrive par ja raha hai... Please wait.")
    
    # Background mein login task chalayen
    asyncio.create_task(playwright_login_task(num, update))

async def playwright_login_task(num, update):
    global user_otp
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = await browser.new_context()
            page = await context.new_page()
            
            await page.goto("https://cloud.jazzdrive.com.pk/login", timeout=60000)
            await page.fill('input[type="tel"]', num)
            await page.click('#signinbtn')
            
            await update.message.reply_text("🔢 OTP bhej diya gaya hai! Jaldi se chat mein sirf apna 4-digit OTP likh kar bhejein (Jaise: 1234).")
            
            # OTP ka intezar (Maximum 2 minute)
            wait_time = 0
            while user_otp is None and wait_time < 120:
                await asyncio.sleep(1)
                wait_time += 1
                
            if user_otp is None:
                await update.message.reply_text("❌ Timeout! OTP nahi mila. Dubara /login chalayen.")
                await browser.close()
                return
                
            await page.evaluate(f'document.getElementById("otp").value = "{user_otp}"')
            await page.click('#signinbtn')
            await asyncio.sleep(8)  # Login process complete hone ka wait
            
            await context.storage_state(path="jazz_cookies.json")
            await update.message.reply_text("✅ Boss, Login 100% Successful! Ab aap YouTube links bhej sakte hain.")
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
    
    # Agar 4 digits hain, toh bot isay OTP samjhega
    if text.isdigit() and len(text) == 4:
        user_otp = text
        await update.message.reply_text("👍 OTP pakar liya! Login verify kar raha hoon...")
        return
        
    # Agar YouTube link hai
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
    await update.message.reply_text("🔍 Video scan kar raha hoon... (Quality menu aa raha hai)")
    ydl_opts = {'quiet': True, 'extractor_args': {'youtube': {'client': ['android', 'ios']}}}
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            title = info.get('title', 'YouTube Video')
            formats = sorted(list(set([f.get('height') for f in info.get('formats', []) if f.get('height')])), reverse=True)
            
        keyboard = []
        for res in formats[:6]:  # Top 6 qualities
            keyboard.append([InlineKeyboardButton(f"{res}p", callback_data=f"{res}|{url}")])
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🎬 {title}\n\n👉 Konsi quality chahiye boss?", reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f"❌ Scan Error: {e}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    # Security check inside button click
    if query.from_user.id != ADMIN_ID: 
        await query.answer("Aapko ijazat nahi hai!")
        return
        
    await query.answer()
    res, url = query.data.split("|", 1)
    
    await query.edit_message_text(f"⏳ Downloading at {res}p... Pura zor lag raha hai, please wait.")
    
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
        
        await query.message.reply_text(f"✅ Download complete! Ab JazzDrive par upload shuru ho gayi hai...")
        
        # Upload shuru karein
        success = await upload_to_jazz(filename)
        if success:
            await query.message.reply_text("🎉 MISSION COMPLETE! Video JazzDrive mein safe hai.")
        else:
            await query.message.reply_text("❌ Upload failed. Ek dafa Drive check karein.")
            
    except Exception as e:
        await query.message.reply_text(f"❌ Error: {e}")
    finally:
        if os.path.exists(filename):
            os.remove(filename)  # GitHub ka kachra saaf

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
                # Naye interface ke mutabiq Upload button click
                try:
                    await page.click("/html/body/div/div/div[1]/div/header/div/div/button")
                except:
                    await page.get_by_role("button", name="Upload").first.click()
                    
            await (await fc_info.value).set_files(file_path)
            
            # Wait for 100% completion (Timeout 15 minutes)
            await page.wait_for_selector("text=completed", timeout=900000)
            await browser.close()
            return True
    except Exception as e:
        print(f"Upload Error: {e}")
        return False

# ==========================================
# 🚀 START SERVER
# ==========================================
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    print("🤖 The 24/7 Hacker Bot is Online! Waiting for Admin...")
    app.run_polling()
