# main.py
import asyncio
import logging
import re
import json
import os
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
import aiohttp
import pytz

# ============== تنظیمات نهایی ==============
API_ID = 29811798
API_HASH = "ef5847a43a978d6883b97b0caeb81736"
BOT_TOKEN = "8874696899:AAE4xqezJFuTJjwLuWmsME09RN4lCUQOfCw"
CHANNEL_ID = -1004316990533
ADMIN_IDS = [7803165903, 8010044260]

# ============== راه‌اندازی ==============
logging.basicConfig(level=logging.INFO)
app = Client("scheduler_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
scheduler = AsyncIOScheduler(timezone=pytz.timezone('Asia/Tehran'))
user_data = {}

# ============== دیتابیس ساده (JSON) ==============
if not os.path.exists("data.json"):
    with open("data.json", "w") as f:
        json.dump({"scheduled": [], "products": []}, f)

def load_data():
    with open("data.json", "r") as f:
        return json.load(f)

def save_data(data):
    with open("data.json", "w") as f:
        json.dump(data, f, indent=2)

# ============== کیبورد شیشه‌ای مدرن ==============
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 ثبت پست جدید", callback_data="new_post")],
        [InlineKeyboardButton("📋 لیست پست‌های زمان‌بندی شده", callback_data="list_posts")],
        [InlineKeyboardButton("🗑 حذف پست", callback_data="delete_post")],
        [InlineKeyboardButton("🤖 استعلام قیمت", callback_data="price_check")],
        [InlineKeyboardButton("📊 آمار کانال", callback_data="stats")],
        [InlineKeyboardButton("❓ راهنما", callback_data="help")]
    ])

# ============== بررسی دسترسی ==============
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ============== دستور استارت ==============
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔ شما دسترسی استفاده از این ربات را ندارید.")
        return
    
    await message.reply_text(
        "✨ **به ربات مدیریت کانال سیب‌شاپ خوش اومدی!**\n\n"
        "من یه دستیار هوشمند برای مدیریت پست‌ها و استعلام قیمت هستم.\n"
        "از منو زیر استفاده کن:",
        reply_markup=main_menu()
    )

# ============== ثبت پست جدید ==============
@app.on_callback_query(filters.regex("new_post"))
async def new_post_callback(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 **ثبت پست جدید**\n\n"
        "لطفاً پیام یا عکس مورد نظر رو ارسال کن.\n"
        "بعد از ارسال، زمان انتشار رو مشخص می‌کنی.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )
    user_data[callback.from_user.id] = {"step": "waiting_post_content"}

# ============== دریافت محتوای پست ==============
@app.on_message(filters.text & ~filters.command("start"))
async def handle_text_messages(client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    # اگر کاربر در مرحله ثبت پست هست
    if user_id in user_data and user_data[user_id].get("step") == "waiting_post_content":
        content = {"type": "text", "data": message.text}
        user_data[user_id]["content"] = content
        user_data[user_id]["step"] = "waiting_time"
        
        await message.reply_text(
            "⏰ **زمان انتشار رو مشخص کن**\n\n"
            "فرمت‌های قابل قبول:\n"
            "• `امروز 14:30`\n"
            "• `فردا 20:00`\n"
            "• `1402/12/20 18:00`\n"
            "• `12:00` (همین امروز)\n\n"
            "مثلاً: `امروز 15:30`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return
    
    # اگر کاربر در مرحله زمان هست
    if user_id in user_data and user_data[user_id].get("step") == "waiting_time":
        time_text = message.text.strip()
        scheduled_time = parse_time(time_text)
        
        if not scheduled_time:
            await message.reply_text("❌ فرمت زمان اشتباه! دوباره امتحان کن.")
            return
        
        # ذخیره در دیتابیس
        data = load_data()
        post_id = len(data["scheduled"]) + 1
        post_data = {
            "id": post_id,
            "content": user_data[user_id]["content"],
            "scheduled_time": scheduled_time.isoformat(),
            "status": "pending"
        }
        data["scheduled"].append(post_data)
        save_data(data)
        
        # برنامه‌ریزی برای ارسال
        scheduler.add_job(
            send_scheduled_post,
            DateTrigger(run_date=scheduled_time),
            args=[post_id],
            id=f"post_{post_id}"
        )
        
        await message.reply_text(
            f"✅ پست با موفقیت ثبت شد!\n"
            f"📅 زمان انتشار: `{scheduled_time.strftime('%Y/%m/%d %H:%M')}`\n"
            f"🆔 شماره پست: `{post_id}`",
            reply_markup=main_menu()
        )
        del user_data[user_id]
        return
    
    # اگر کاربر در مرحله استعلام قیمت هست
    if user_id in user_data and user_data[user_id].get("step") == "waiting_product_name":
        product_name = message.text
        await message.reply_text("🔍 در حال جستجو... لطفاً چند ثانیه صبر کن.")
        
        # دریافت قیمت از دیجی‌کالا و ترب
        digi_price = await get_digikala_price(product_name)
        torob_price = await get_torob_price(product_name)
        
        # هوش مصنوعی رایگان
        ai_response = await get_ai_response(product_name)
        
        response = f"🤖 **نتیجه استعلام قیمت برای:**\n`{product_name}`\n\n"
        response += f"🛒 **دیجی‌کالا:** {digi_price}\n"
        response += f"🛍 **ترب:** {torob_price}\n\n"
        response += f"💡 **توضیحات:**\n{ai_response}\n\n"
        response += "📌 قیمت‌ها ممکن است تغییر کنند، لطفاً دقت کنید."
        
        await message.reply_text(response, reply_markup=main_menu())
        del user_data[user_id]
        return

# ============== دریافت عکس و فایل ==============
@app.on_message(filters.photo | filters.document | filters.video)
async def handle_media_messages(client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    if user_id not in user_data or user_data[user_id].get("step") != "waiting_post_content":
        return
    
    # ذخیره محتوای مدیا
    if message.photo:
        content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption}
    elif message.document:
        content = {"type": "document", "file_id": message.document.file_id, "caption": message.caption}
    elif message.video:
        content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption}
    else:
        return
    
    user_data[user_id]["content"] = content
    user_data[user_id]["step"] = "waiting_time"
    
    await message.reply_text(
        "⏰ **زمان انتشار رو مشخص کن**\n\n"
        "فرمت‌های قابل قبول:\n"
        "• `امروز 14:30`\n"
        "• `فردا 20:00`\n"
        "• `1402/12/20 18:00`\n"
        "• `12:00` (همین امروز)\n\n"
        "مثلاً: `امروز 15:30`",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )

def parse_time(text):
    now = datetime.now(pytz.timezone('Asia/Tehran'))
    text = text.lower().replace('ساعت', '').strip()
    
    # بررسی فرمت‌های مختلف
    patterns = [
        (r'امروز\s*(\d{1,2}):(\d{2})', lambda m: now.replace(hour=int(m[0]), minute=int(m[1]), second=0)),
        (r'فردا\s*(\d{1,2}):(\d{2})', lambda m: (now + timedelta(days=1)).replace(hour=int(m[0]), minute=int(m[1]), second=0)),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})\s*(\d{1,2}):(\d{2})', lambda m: datetime(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]), tzinfo=pytz.timezone('Asia/Tehran'))),
        (r'(\d{1,2}):(\d{2})', lambda m: now.replace(hour=int(m[0]), minute=int(m[1]), second=0))
    ]
    
    for pattern, func in patterns:
        match = re.search(pattern, text)
        if match:
            return func(match.groups())
    return None

async def send_scheduled_post(post_id):
    data = load_data()
    post = next((p for p in data["scheduled"] if p["id"] == post_id), None)
    if not post or post["status"] == "sent":
        return
    
    content = post["content"]
    try:
        if content["type"] == "text":
            await app.send_message(CHANNEL_ID, content["data"])
        elif content["type"] == "photo":
            await app.send_photo(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        elif content["type"] == "document":
            await app.send_document(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        elif content["type"] == "video":
            await app.send_video(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        
        post["status"] = "sent"
        save_data(data)
        logging.info(f"✅ پست {post_id} ارسال شد")
    except Exception as e:
        logging.error(f"❌ خطا در ارسال پست {post_id}: {e}")

# ============== لیست پست‌ها ==============
@app.on_callback_query(filters.regex("list_posts"))
async def list_posts(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    data = load_data()
    if not data["scheduled"]:
        await callback.message.edit_text(
            "📭 **هیچ پست زمان‌بندی شده‌ای وجود نداره.**",
            reply_markup=main_menu()
        )
        return
    
    text = "📋 **لیست پست‌های زمان‌بندی شده:**\n\n"
    for post in data["scheduled"]:
        status = "✅ ارسال شده" if post["status"] == "sent" else "⏳ در انتظار"
        time = datetime.fromisoformat(post["scheduled_time"]).strftime("%Y/%m/%d %H:%M")
        text += f"🆔 {post['id']} | {time} | {status}\n"
    
    await callback.message.edit_text(text, reply_markup=main_menu())

# ============== حذف پست ==============
@app.on_callback_query(filters.regex("delete_post"))
async def delete_post(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    data = load_data()
    if not data["scheduled"]:
        await callback.message.edit_text("📭 پستی برای حذف وجود نداره.", reply_markup=main_menu())
        return
    
    keyboard = []
    for post in data["scheduled"]:
        if post["status"] == "pending":
            time = datetime.fromisoformat(post["scheduled_time"]).strftime("%Y/%m/%d %H:%M")
            keyboard.append([InlineKeyboardButton(f"🗑 حذف #{post['id']} - {time}", callback_data=f"confirm_delete_{post['id']}")])
    
    if not keyboard:
        await callback.message.edit_text("📭 هیچ پست در انتظاری برای حذف وجود نداره.", reply_markup=main_menu())
        return
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="back")])
    await callback.message.edit_text("🗑 **انتخاب پست برای حذف:**", reply_markup=InlineKeyboardMarkup(keyboard))

@app.on_callback_query(filters.regex("confirm_delete_"))
async def confirm_delete(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[2])
    data = load_data()
    data["scheduled"] = [p for p in data["scheduled"] if p["id"] != post_id]
    save_data(data)
    
    # لغو job برنامه‌ریزی شده
    try:
        scheduler.remove_job(f"post_{post_id}")
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ پست #{post_id} با موفقیت حذف شد.",
        reply_markup=main_menu()
    )

# ============== استعلام قیمت ==============
@app.on_callback_query(filters.regex("price_check"))
async def price_check(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🤖 **استعلام قیمت محصول**\n\n"
        "لطفاً نام محصول رو ارسال کن تا قیمت‌ش رو از دیجی‌کالا و ترب بگیرم.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )
    user_data[callback.from_user.id] = {"step": "waiting_product_name"}

async def get_digikala_price(product_name):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.digikala.com/v1/search/?q={product_name}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data") and data["data"].get("products"):
                        product = data["data"]["products"][0]
                        price = product.get("default_variant", {}).get("price", {}).get("selling_price")
                        if price:
                            return f"{int(price):,} تومان"
        return "🔴 قیمت موجود نیست"
    except:
        return "🔴 خطا در دریافت قیمت"

async def get_torob_price(product_name):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.torob.com/v4/base-product/search/?query={product_name}"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("data") and data["data"].get("results"):
                        product = data["data"]["results"][0]
                        price = product.get("price")
                        if price:
                            return f"{int(price):,} تومان"
        return "🔴 قیمت موجود نیست"
    except:
        return "🔴 خطا در دریافت قیمت"

async def get_ai_response(product_name):
    responses = {
        "گوشی": "محصولات گوشی همراه با گارانتی ۱۸ ماهه و بهترین قیمت بازار.",
        "هدفون": "هدفون‌های با کیفیت بالا با صدای بی‌نظیر و مناسب برای استفاده روزمره.",
        "ساعت": "ساعت‌های هوشمند با قابلیت‌های پیشرفته و طراحی شیک.",
        "کیس": "کیس‌های محافظ با طراحی زیبا و مقاومت بالا.",
        "شارژر": "شارژرهای اصلی با سرعت بالا و ایمنی کامل.",
        "ایرپاد": "ایرپادهای اصل با کیفیت صدای عالی و اتصال پایدار.",
        "محافظ": "محافظ‌های صفحه با کیفیت و مقاوم در برابر ضربه.",
        "کابل": "کابل‌های اصلی و با کیفیت برای شارژ و انتقال داده."
    }
    
    for key, response in responses.items():
        if key in product_name.lower():
            return response
    
    return "محصول مورد نظر دارای کیفیت عالی و قیمت رقابتی است. برای اطلاعات بیشتر با پشتیبانی تماس بگیرید."

# ============== آمار کانال ==============
@app.on_callback_query(filters.regex("stats"))
async def stats(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    try:
        chat = await app.get_chat(CHANNEL_ID)
        members = chat.members_count if hasattr(chat, 'members_count') else "نامشخص"
        data = load_data()
        sent = len([p for p in data["scheduled"] if p["status"] == "sent"])
        pending = len([p for p in data["scheduled"] if p["status"] == "pending"])
        
        stats_text = f"📊 **آمار کانال سیب‌شاپ**\n\n"
        stats_text += f"👥 تعداد اعضا: {members}\n"
        stats_text += f"📝 پست‌های ارسال شده: {sent}\n"
        stats_text += f"⏳ پست‌های در انتظار: {pending}\n"
        stats_text += f"📅 تاریخ امروز: {datetime.now(pytz.timezone('Asia/Tehran')).strftime('%Y/%m/%d')}"
        
        await callback.message.edit_text(stats_text, reply_markup=main_menu())
    except Exception as e:
        await callback.message.edit_text(f"❌ خطا در دریافت آمار: {e}", reply_markup=main_menu())

# ============== راهنما ==============
@app.on_callback_query(filters.regex("help"))
async def help_command(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    help_text = """
❓ **راهنمای ربات سیب‌شاپ**

**📝 ثبت پست:**
1. روی دکمه "ثبت پست جدید" کلیک کن.
2. پیام یا عکس رو ارسال کن.
3. زمان انتشار رو مشخص کن.

**🗑 حذف پست:**
پست‌های زمان‌بندی شده رو میتونی قبل از ارسال حذف کنی.

**🤖 استعلام قیمت:**
اسم محصول رو بفرست تا قیمت از دیجی‌کالا و ترب بگیرم.

**📊 آمار:**
مشاهده تعداد اعضا و وضعیت پست‌ها.

**⏰ فرمت‌های زمان:**
• `امروز 14:30`
• `فردا 20:00`
• `1402/12/20 18:00`
• `12:00` (همین امروز)
"""
    await callback.message.edit_text(help_text, reply_markup=main_menu())

# ============== بازگشت ==============
@app.on_callback_query(filters.regex("back"))
async def back(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "✨ **منوی اصلی:**",
        reply_markup=main_menu()
    )

# ============== ران کردن ربات ==============
if __name__ == "__main__":
    print("🚀 ربات سیب‌شاپ در حال اجرا...")
    print(f"👥 فقط کاربران با آیدی {ADMIN_IDS} دسترسی دارند.")
    scheduler.start()
    app.run()
