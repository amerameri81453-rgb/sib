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

# ============== تنظیمات ==============
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

# ============== دیتابیس ==============
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
        [InlineKeyboardButton("📋 مدیریت پست‌ها", callback_data="manage_posts")],
        [InlineKeyboardButton("🤖 مشاوره هوشمند سیب‌شاپ", callback_data="ai_consultant")],
        [InlineKeyboardButton("💰 استعلام قیمت", callback_data="price_check")],
        [InlineKeyboardButton("📊 آمار کانال", callback_data="stats")],
        [InlineKeyboardButton("❓ راهنما", callback_data="help")]
    ])

def manage_posts_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 لیست پست‌ها", callback_data="list_posts")],
        [InlineKeyboardButton("✏️ ویرایش پست", callback_data="edit_post")],
        [InlineKeyboardButton("🗑 حذف پست", callback_data="delete_post")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
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
        "🍎 **به ربات هوشمند سیب‌شاپ خوش اومدی!**\n\n"
        "من دستیار تخصصی کانال سیب‌شاپ هستم.\n"
        "با من میتونی:\n"
        "• 📝 پست‌های زمان‌بندی شده ثبت کنی\n"
        "• 🤖 مشاوره تخصصی محصولات بگیری\n"
        "• 💰 قیمت لحظه‌ای محصولات رو ببینی\n"
        "• 📊 آمار کانال رو بررسی کنی\n\n"
        "از منوی زیر انتخاب کن:",
        reply_markup=main_menu()
    )

# ============== ثبت پست جدید ==============
@app.on_callback_query(filters.regex("new_post"))
async def new_post_callback(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📝 **ثبت پست جدید در کانال سیب‌شاپ**\n\n"
        "📎 لطفاً محتوای پست رو ارسال کن:\n"
        "• میتونی **متن** ساده بفرستی\n"
        "• میتونی **عکس** با توضیحات بفرستی\n"
        "• میتونی **ویدئو** با توضیحات بفرستی\n"
        "• میتونی **فایل** با توضیحات بفرستی\n\n"
        "⏳ بعد از ارسال، زمان انتشار رو مشخص میکنی.",
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
    
    # مرحله 1: دریافت محتوای پست
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
    
    # مرحله 2: دریافت زمان
    if user_id in user_data and user_data[user_id].get("step") == "waiting_time":
        time_text = message.text.strip()
        scheduled_time = parse_time(time_text)
        
        if not scheduled_time:
            await message.reply_text(
                "❌ فرمت زمان اشتباه!\n"
                "از این فرمت‌ها استفاده کن:\n"
                "• `امروز 14:30`\n"
                "• `فردا 20:00`\n"
                "• `12:00`"
            )
            return
        
        # ذخیره در دیتابیس
        data = load_data()
        post_id = len(data["scheduled"]) + 1
        post_data = {
            "id": post_id,
            "content": user_data[user_id]["content"],
            "scheduled_time": scheduled_time.isoformat(),
            "status": "pending",
            "created_at": datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
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
            f"✅ **پست با موفقیت ثبت شد!**\n\n"
            f"🆔 شماره پست: `{post_id}`\n"
            f"📅 زمان انتشار: `{scheduled_time.strftime('%Y/%m/%d %H:%M')}`\n"
            f"📌 وضعیت: ⏳ در انتظار\n\n"
            f"💡 برای ویرایش یا حذف از بخش مدیریت استفاده کن.",
            reply_markup=main_menu()
        )
        del user_data[user_id]
        return
    
    # مرحله 3: استعلام قیمت
    if user_id in user_data and user_data[user_id].get("step") == "waiting_product_name":
        product_name = message.text
        await message.reply_text("🔍 در حال جستجو... لطفاً چند ثانیه صبر کن.")
        
        # دریافت قیمت از دیجی‌کالا و ترب
        digi_price = await get_digikala_price(product_name)
        torob_price = await get_torob_price(product_name)
        
        response = f"💰 **قیمت محصول:**\n`{product_name}`\n\n"
        response += f"🛒 **دیجی‌کالا:** {digi_price}\n"
        response += f"🛍 **ترب:** {torob_price}\n\n"
        response += "📌 قیمت‌ها لحظه‌ای هستن و ممکنه تغییر کنن."
        
        await message.reply_text(response, reply_markup=main_menu())
        del user_data[user_id]
        return
    
    # مرحله 4: ویرایش پست
    if user_id in user_data and user_data[user_id].get("step") == "waiting_edit_content":
        post_id = user_data[user_id]["edit_post_id"]
        content = {"type": "text", "data": message.text}
        
        data = load_data()
        for post in data["scheduled"]:
            if post["id"] == post_id:
                post["content"] = content
                break
        save_data(data)
        
        await message.reply_text(
            f"✅ **پست #{post_id} با موفقیت ویرایش شد!**",
            reply_markup=main_menu()
        )
        del user_data[user_id]
        return

# ============== دریافت رسانه ==============
@app.on_message(filters.photo | filters.document | filters.video | filters.animation)
async def handle_media_messages(client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    # مرحله 1: دریافت محتوای پست
    if user_id in user_data and user_data[user_id].get("step") == "waiting_post_content":
        # تشخیص نوع رسانه
        if message.photo:
            content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption or ""}
        elif message.video:
            content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
        elif message.document:
            content = {"type": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        elif message.animation:
            content = {"type": "animation", "file_id": message.animation.file_id, "caption": message.caption or ""}
        else:
            await message.reply_text("❌ نوع فایل پشتیبانی نمیشه!")
            return
        
        user_data[user_id]["content"] = content
        user_data[user_id]["step"] = "waiting_time"
        
        await message.reply_text(
            "⏰ **زمان انتشار رو مشخص کن**\n\n"
            "فرمت‌های قابل قبول:\n"
            "• `امروز 14:30`\n"
            "• `فردا 20:00`\n"
            "• `12:00` (همین امروز)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return
    
    # مرحله ویرایش
    if user_id in user_data and user_data[user_id].get("step") == "waiting_edit_content":
        post_id = user_data[user_id]["edit_post_id"]
        
        if message.photo:
            content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption or ""}
        elif message.video:
            content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
        elif message.document:
            content = {"type": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        else:
            await message.reply_text("❌ نوع فایل پشتیبانی نمیشه!")
            return
        
        data = load_data()
        for post in data["scheduled"]:
            if post["id"] == post_id:
                post["content"] = content
                break
        save_data(data)
        
        await message.reply_text(
            f"✅ **پست #{post_id} با موفقیت ویرایش شد!**",
            reply_markup=main_menu()
        )
        del user_data[user_id]
        return

def parse_time(text):
    now = datetime.now(pytz.timezone('Asia/Tehran'))
    text = text.lower().replace('ساعت', '').strip()
    
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
        elif content["type"] == "video":
            await app.send_video(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        elif content["type"] == "document":
            await app.send_document(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        elif content["type"] == "animation":
            await app.send_animation(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        
        post["status"] = "sent"
        post["sent_at"] = datetime.now(pytz.timezone('Asia/Tehran')).isoformat()
        save_data(data)
        logging.info(f"✅ پست {post_id} ارسال شد")
    except Exception as e:
        logging.error(f"❌ خطا در ارسال پست {post_id}: {e}")

# ============== مدیریت پست‌ها ==============
@app.on_callback_query(filters.regex("manage_posts"))
async def manage_posts(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "📋 **مدیریت پست‌های کانال سیب‌شاپ**\n\n"
        "از گزینه‌های زیر انتخاب کن:",
        reply_markup=manage_posts_menu()
    )

# ============== لیست پست‌ها ==============
@app.on_callback_query(filters.regex("list_posts"))
async def list_posts(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    data = load_data()
    if not data["scheduled"]:
        await callback.message.edit_text(
            "📭 **هیچ پستی در سیستم وجود نداره.**",
            reply_markup=manage_posts_menu()
        )
        return
    
    text = "📋 **لیست پست‌های کانال سیب‌شاپ**\n\n"
    pending = []
    sent = []
    
    for post in data["scheduled"]:
        status = "✅ ارسال شده" if post["status"] == "sent" else "⏳ در انتظار"
        time = datetime.fromisoformat(post["scheduled_time"]).strftime("%Y/%m/%d %H:%M")
        line = f"🆔 #{post['id']} | {time} | {status}\n"
        
        if post["status"] == "pending":
            pending.append(line)
        else:
            sent.append(line)
    
    if pending:
        text += "**⏳ در انتظار ارسال:**\n" + "".join(pending) + "\n"
    if sent:
        text += "**✅ ارسال شده:**\n" + "".join(sent)
    
    await callback.message.edit_text(text, reply_markup=manage_posts_menu())

# ============== ویرایش پست ==============
@app.on_callback_query(filters.regex("edit_post"))
async def edit_post(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    data = load_data()
    pending_posts = [p for p in data["scheduled"] if p["status"] == "pending"]
    
    if not pending_posts:
        await callback.message.edit_text(
            "📭 **هیچ پست در انتظاری برای ویرایش وجود نداره.**",
            reply_markup=manage_posts_menu()
        )
        return
    
    keyboard = []
    for post in pending_posts:
        time = datetime.fromisoformat(post["scheduled_time"]).strftime("%Y/%m/%d %H:%M")
        keyboard.append([InlineKeyboardButton(f"✏️ ویرایش #{post['id']} - {time}", callback_data=f"select_edit_{post['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_posts")])
    await callback.message.edit_text(
        "✏️ **انتخاب پست برای ویرایش:**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@app.on_callback_query(filters.regex("select_edit_"))
async def select_edit(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[2])
    user_data[callback.from_user.id] = {
        "step": "waiting_edit_content",
        "edit_post_id": post_id
    }
    
    await callback.message.edit_text(
        f"✏️ **ویرایش پست #{post_id}**\n\n"
        "لطفاً محتوای جدید رو ارسال کن.\n"
        "میتونی متن، عکس، ویدئو یا فایل بفرستی.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="manage_posts")]
        ])
    )

# ============== حذف پست ==============
@app.on_callback_query(filters.regex("delete_post"))
async def delete_post(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    data = load_data()
    pending_posts = [p for p in data["scheduled"] if p["status"] == "pending"]
    
    if not pending_posts:
        await callback.message.edit_text(
            "📭 **هیچ پست در انتظاری برای حذف وجود نداره.**",
            reply_markup=manage_posts_menu()
        )
        return
    
    keyboard = []
    for post in pending_posts:
        time = datetime.fromisoformat(post["scheduled_time"]).strftime("%Y/%m/%d %H:%M")
        keyboard.append([InlineKeyboardButton(f"🗑 حذف #{post['id']} - {time}", callback_data=f"confirm_delete_{post['id']}")])
    
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_posts")])
    await callback.message.edit_text(
        "🗑 **انتخاب پست برای حذف:**",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

@app.on_callback_query(filters.regex("confirm_delete_"))
async def confirm_delete(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    post_id = int(callback.data.split("_")[2])
    data = load_data()
    data["scheduled"] = [p for p in data["scheduled"] if p["id"] != post_id]
    save_data(data)
    
    try:
        scheduler.remove_job(f"post_{post_id}")
    except:
        pass
    
    await callback.message.edit_text(
        f"✅ **پست #{post_id} با موفقیت حذف شد.**",
        reply_markup=manage_posts_menu()
    )

# ============== هوش مصنوعی تخصصی سیب‌شاپ ==============
@app.on_callback_query(filters.regex("ai_consultant"))
async def ai_consultant(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🤖 **مشاوره هوشمند سیب‌شاپ**\n\n"
        "سلام! من مریم احمدی، مشاور تخصصی محصولات اپل هستم.\n\n"
        "سوالاتت رو از من بپرس:\n"
        "• مقایسه محصولات\n"
        "• راهنمای خرید\n"
        "• مشخصات فنی\n"
        "• قیمت‌ها و تخفیف‌ها\n"
        "• گارانتی و خدمات\n\n"
        "سوال خودت رو بفرست:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )
    user_data[callback.from_user.id] = {"step": "waiting_ai_question"}

@app.on_message(filters.text & ~filters.command("start"))
async def handle_ai_question(client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    if user_id in user_data and user_data[user_id].get("step") == "waiting_ai_question":
        question = message.text
        
        # پاسخ هوشمند
        response = await get_ai_response(question)
        
        await message.reply_text(
            f"🤖 **پاسخ مشاور سیب‌شاپ (مریم احمدی):**\n\n"
            f"{response}\n\n"
            f"❓ سوال دیگه‌ای داری؟ بپرس!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back")]
            ])
        )
        del user_data[user_id]

async def get_ai_response(question):
    question = question.lower()
    
    # دیتابیس دانش تخصصی سیب‌شاپ
    knowledge = {
        "گوشی": {
            "keywords": ["گوشی", "آیفون", "iphone", "موبایل", "مبایل"],
            "response": """📱 **راهنمای خرید گوشی اپل:**

🔹 **آیفون ۱۶ پرو مکس:** بهترین دوربین، باتری عالی، صفحه‌نمایش ۶.۹ اینچ
🔹 **آیفون ۱۶ پرو:** دوربین تله‌فوتو، اندازه مناسب ۶.۳ اینچ
🔹 **آیفون ۱۶:** گزینه اقتصادی با کیفیت بالا

💡 **نکته:** اگر به دوربین حرفه‌ای نیاز داری، پرو مکس رو انتخاب کن.
✅ **گارانتی:** ۱۸ ماهه معتبر
📞 **مشاوره:** برای قیمت دقیق با ما تماس بگیر."""
        },
        
        "هدفون": {
            "keywords": ["هدفون", "ایرپاد", "airpods", "هندزفری"],
            "response": """🎧 **راهنمای خرید ایرپاد:**

🔹 **ایرپاد پرو ۲:** بهترین کیفیت صدا، حذف نویز فعال
🔹 **ایرپاد ۴:** گزینه اقتصادی با صدای عالی
🔹 **ایرپاد مکس:** برای علاقه‌مندان به موسیقی حرفه‌ای

💡 **نکته:** ایرپاد پرو ۲ برای استفاده روزمره بهترین انتخابه.
✅ **گارانتی:** ۱۸ ماهه
🎵 **کیفیت صدا:** بی‌نظیر با بیس عمیق"""
        },
        
        "ساعت": {
            "keywords": ["ساعت", "واچ", "watch", "اپل واچ"],
            "response": """⌚ **راهنمای خرید اپل واچ:**

🔹 **اپل واچ سری ۹:** جدیدترین مدل با صفحه‌نمایش همیشه روشن
🔹 **اپل واچ اولترا ۲:** برای ورزش‌های حرفه‌ای و کوهنوردی
🔹 **اپل واچ SE:** گزینه اقتصادی با امکانات کامل

💡 **نکته:** برای استفاده روزمره سری ۹ و برای ورزش اولترا ۲.
✅ **گارانتی:** ۱۸ ماهه
📊 **امکانات:** اندازه‌گیری ضربان قلب، اکسیژن خون، خواب"""
        },
        
        "تبلت": {
            "keywords": ["تبلت", "آیپد", "ipad", "پد"],
            "response": """📱 **راهنمای خرید آیپد:**

🔹 **آیپد پرو M4:** قدرتمندترین تبلت، مناسب طراحی و ویرایش
🔹 **آیپد ایر M2:** تعادل بین قیمت و قدرت
🔹 **آیپد ۱۰:** گزینه اقتصادی برای مطالعه و نت‌برداری

💡 **نکته:** برای طراحی و حرفه‌ای بودن، پرو رو انتخاب کن.
✅ **گارانتی:** ۱۸ ماهه
✏️ **قلم اپل:** پشتیبانی از نسل دوم"""
        },
        
        "مک": {
            "keywords": ["مک", "مک بوک", "macbook", "ایمک"],
            "response": """💻 **راهنمای خرید مک:**

🔹 **مک‌بوک پرو M3:** بهترین برای برنامه‌نویسی و تدوین
🔹 **مک‌بوک ایر M3:** سبک و مناسب برای استفاده روزمره
🔹 **آی‌مک ۲۴ اینچ:** همه‌کاره با صفحه‌نمایش عالی

💡 **نکته:** برای حمل روزمره، ایر و برای کارهای سنگین، پرو.
✅ **گارانتی:** ۱۸ ماهه
🔋 **باتری:** تا ۲۲ ساعت"""
        },
        
        "شارژر": {
            "keywords": ["شارژر", "اداپتور", "کابل", "پاوربانک"],
            "response": """🔋 **راهنمای خرید شارژر و کابل:**

🔹 **شارژر ۲۰ وات:** سریع‌ترین شارژ برای آیفون
🔹 **شارژر ۳۰ وات:** مناسب برای آیپد و مک‌بوک
🔹 **کابل USB-C به لایتنینگ:** اصلی و با کیفیت
🔹 **پاوربانک ۱۰۰۰۰:** همراه همیشگی

💡 **نکته:** حتماً از محصولات اصلی استفاده کن تا به باتری آسیب نرسه.
✅ **گارانتی:** ۱۲ ماهه
⚡ **شارژ سریع:** تا ۵۰٪ در ۳۰ دقیقه"""
        },
        
        "کیس": {
            "keywords": ["کیس", "قاب", "محافظ", "گلس"],
            "response": """🛡️ **راهنمای خرید محافظ:**

🔹 **کیس سیلیکونی اصلی:** نرم و ضد ضربه
🔹 **کیس شفاف:** نمایش زیبایی گوشی
🔹 **کیس چرمی:** شیک و با کیفیت
🔹 **گلس ضدخش:** محافظت کامل از صفحه

💡 **نکته:** کیس سیلیکونی برای محافظت بیشتر پیشنهاد میشه.
✅ **گارانتی:** اصالت کالا
🎨 **رنگ‌بندی:** متنوع و جدید"""
        }
    }
    
    # جستجو در دانش
    for category, info in knowledge.items():
        for keyword in info["keywords"]:
            if keyword in question:
                return info["response"] + "\n\n📞 **برای مشاوره بیشتر با ما تماس بگیرید:** @AppleShopChannel"
    
    # پاسخ پیش‌فرض
    return """🍎 **سیب‌شاپ - مریم احمدی**\n\n
سوال شما در دیتابیس من موجود نیست، ولی خوشحال میشم کمکت کنم!

📌 **سوالات رایج:**
• مقایسه آیفون ۱۶ و ۱۶ پرو
• قیمت ایرپاد پرو ۲
• گارانتی محصولات
• روش خرید و ارسال

📞 **تماس با ما:** @AppleShopChannel
💬 **پشتیبانی:** ۲۴ ساعته

سوال خودت رو دقیق‌تر بپرس تا بهتر راهنماییت کنم!"""

# ============== استعلام قیمت ==============
@app.on_callback_query(filters.regex("price_check"))
async def price_check(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "💰 **استعلام قیمت محصولات**\n\n"
        "لطفاً نام محصول رو ارسال کن:\n"
        "• گوشی\n"
        "• ایرپاد\n"
        "• ساعت\n"
        "• تبلت\n"
        "• مک بوک",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )
    user_data[callback.from_user.id] = {"step": "waiting_product_name"}

async def get_digikala_price(product_name):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://api.digikala.com/v1/search/?q={product_name}"
            async with session.get(url, timeout=5) as resp:
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
            async with session.get(url, timeout=5) as resp:
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
        total = len(data["scheduled"])
        sent = len([p for p in data["scheduled"] if p["status"] == "sent"])
        pending = len([p for p in data["scheduled"] if p["status"] == "pending"])
        
        stats_text = f"📊 **آمار کانال سیب‌شاپ**\n\n"
        stats_text += f"👥 تعداد اعضا: {members:,}\n"
        stats_text += f"📝 کل پست‌ها: {total}\n"
        stats_text += f"✅ ارسال شده: {sent}\n"
        stats_text += f"⏳ در انتظار: {pending}\n"
        stats_text += f"📅 امروز: {datetime.now(pytz.timezone('Asia/Tehran')).strftime('%Y/%m/%d - %H:%M')}\n"
        
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
🍎 **راهنمای کامل ربات سیب‌شاپ**

**📝 ثبت پست جدید:**
1. روی دکمه "ثبت پست جدید" کلیک کن
2. متن، عکس، ویدئو یا فایل رو ارسال کن
3. زمان انتشار رو مشخص کن (مثل `امروز 14:30`)

**📋 مدیریت پست‌ها:**
• **لیست پست‌ها:** دیدن همه پست‌ها
• **ویرایش پست:** تغییر محتوای پست‌های در انتظار
• **حذف پست:** حذف پست‌های در انتظار

**🤖 مشاوره هوشمند:**
سوالات تخصصی درباره محصولات اپل رو از من بپرس

**💰 استعلام قیمت:**
اسم محصول رو بفرست تا قیمت از دیجی‌کالا و ترب بگیرم

**📊 آمار کانال:**
مشاهده تعداد اعضا و وضعیت پست‌ها

⏰ **فرمت‌های زمان:**
• `امروز 14:30`
• `فردا 20:00`
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
        "🍎 **منوی اصلی سیب‌شاپ:**\n\n"
        "از گزینه‌های زیر انتخاب کن:",
        reply_markup=main_menu()
    )

# ============== ران کردن ربات ==============
if __name__ == "__main__":
    print("🍎 ربات سیب‌شاپ در حال اجرا...")
    print(f"👥 فقط کاربران با آیدی {ADMIN_IDS} دسترسی دارند.")
    scheduler.start()
    app.run()
