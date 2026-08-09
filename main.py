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
import jdatetime

# ============== تنظیمات ==============
API_ID = 29811798
API_HASH = "ef5847a43a978d6883b97b0caeb81736"
BOT_TOKEN = "8874696899:AAE4xqezJFuTJjwLuWmsME09RN4lCUQOfCw"
CHANNEL_ID = -1004316990533
ADMIN_IDS = [7803165903, 8010044260]

# ============== تنظیمات OpenRouter ==============
OPENROUTER_API_KEY = "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"

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
        [InlineKeyboardButton("🧠 هوش مصنوعی سیب‌شاپ", callback_data="ai_chat")],
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

# ============== تبدیل تاریخ شمسی ==============
def to_persian_date(dt):
    if not dt:
        return "نامشخص"
    try:
        jd = jdatetime.datetime.fromgregorian(datetime=dt)
        months = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 
                 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند']
        return f"{jd.day} {months[jd.month-1]} {jd.year} - {jd.hour:02d}:{jd.minute:02d}"
    except:
        return dt.strftime("%Y/%m/%d %H:%M")

def parse_persian_date(text):
    """تبدیل تاریخ شمسی به میلادی"""
    now = datetime.now(pytz.timezone('Asia/Tehran'))
    text = text.strip()
    
    patterns = [
        (r'امروز\s*(\d{1,2}):(\d{2})', lambda m: now.replace(hour=int(m[0]), minute=int(m[1]), second=0)),
        (r'فردا\s*(\d{1,2}):(\d{2})', lambda m: (now + timedelta(days=1)).replace(hour=int(m[0]), minute=int(m[1]), second=0)),
        (r'پس فردا\s*(\d{1,2}):(\d{2})', lambda m: (now + timedelta(days=2)).replace(hour=int(m[0]), minute=int(m[1]), second=0)),
        (r'(\d{4})/(\d{1,2})/(\d{1,2})\s*(\d{1,2}):(\d{2})', lambda m: convert_jalali_to_gregorian(int(m[0]), int(m[1]), int(m[2]), int(m[3]), int(m[4]))),
        (r'(\d{1,2}):(\d{2})', lambda m: now.replace(hour=int(m[0]), minute=int(m[1]), second=0)),
    ]
    
    for pattern, func in patterns:
        match = re.search(pattern, text)
        if match:
            return func(match.groups())
    return None

def convert_jalali_to_gregorian(year, month, day, hour, minute):
    try:
        jd = jdatetime.date(year, month, day)
        gd = jd.togregorian()
        return datetime(gd.year, gd.month, gd.day, hour, minute, tzinfo=pytz.timezone('Asia/Tehran'))
    except:
        return None

# ============== بررسی دسترسی ==============
def is_admin(user_id):
    return user_id in ADMIN_IDS

# ============== هوش مصنوعی OpenRouter ==============
async def get_ai_response(question):
    """ارسال سوال به OpenRouter و دریافت پاسخ"""
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://openrouter.ai/api/v1/chat/completions"
            
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://t.me/sib_bot",
                "X-Title": "سیب‌شاپ"
            }
            
            payload = {
                "model": "meta-llama/llama-3.3-70b-instruct:free",
                "messages": [
                    {
                        "role": "system", 
                        "content": """تو یک دستیار هوشمند و حرفه‌ای برای کانال سیب‌شاپ هستی.
                        به سوال کاربر به فارسی پاسخ بده.
                        پاسخ باید مفید، دقیق، دوستانه و کامل باشه.
                        درباره محصولات اپل اطلاعات دقیق بده.
                        قیمت‌ها رو به تومان بگو.
                        گارانتی ۱۸ ماهه رو توضیح بده."""
                    },
                    {"role": "user", "content": question}
                ],
                "temperature": 0.7,
                "max_tokens": 800,
                "top_p": 0.9
            }
            
            async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status == 401:
                    return "❌ خطا: کلید API معتبر نیست. لطفاً کلید جدید از openrouter.ai/keys بگیر."
                elif resp.status == 429:
                    return "⚠️ محدودیت درخواست روزانه پر شده. لطفاً فردا دوباره تلاش کن."
                else:
                    error_text = await resp.text()
                    return f"❌ خطا: {error_text[:200]}"
    except asyncio.TimeoutError:
        return "⏳ زمان پاسخ‌دهی به پایان رسید. لطفاً دوباره تلاش کن."
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# ============== دستور استارت ==============
@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    if not is_admin(message.from_user.id):
        await message.reply_text("⛔ شما دسترسی استفاده از این ربات را ندارید.")
        return
    
    await message.reply_text(
        "🍎 **به ربات هوشمند سیب‌شاپ خوش اومدی!**\n\n"
        "من یک هوش مصنوعی پیشرفته با **Llama 3.3** از OpenRouter هستم!\n"
        "مخصوص کانال سیب‌شاپ طراحی شدم.\n\n"
        "✨ **قابلیت‌های من:**\n"
        "• 📝 ثبت پست با هر نوع رسانه\n"
        "• 🧠 هوش مصنوعی واقعی برای پاسخ به هر سوالی\n"
        "• 💰 استعلام قیمت از دیجی‌کالا و ترب\n"
        "• 📊 مدیریت کامل پست‌ها\n\n"
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
        "📎 هر چیزی که میخوای بفرست:\n"
        "• 📝 متن ساده\n"
        "• 🖼 عکس\n"
        "• 🎬 فیلم\n"
        "• 🎞 گیف\n"
        "• 🎭 استیکر\n"
        "• 📁 فایل\n\n"
        "⏳ بعدش زمان انتشار رو مشخص کن.",
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
            "📅 **فرمت‌های قابل قبول:**\n"
            "• `امروز 14:30`\n"
            "• `فردا 20:00`\n"
            "• `پس فردا 18:00`\n"
            "• `1402/12/20 18:00` (تاریخ شمسی)\n"
            "• `14:30` (همین امروز)\n\n"
            "مثال: `فردا 15:30`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return
    
    # مرحله 2: دریافت زمان
    if user_id in user_data and user_data[user_id].get("step") == "waiting_time":
        time_text = message.text.strip()
        scheduled_time = parse_persian_date(time_text)
        
        if not scheduled_time:
            await message.reply_text(
                "❌ **فرمت زمان اشتباه!**\n\n"
                "از این فرمت‌ها استفاده کن:\n"
                "• `امروز 14:30`\n"
                "• `فردا 20:00`\n"
                "• `پس فردا 18:00`\n"
                "• `1402/12/20 18:00`\n"
                "• `14:30`"
            )
            return
        
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
        
        scheduler.add_job(
            send_scheduled_post,
            DateTrigger(run_date=scheduled_time),
            args=[post_id],
            id=f"post_{post_id}"
        )
        
        persian_time = to_persian_date(scheduled_time)
        
        await message.reply_text(
            f"✅ **پست با موفقیت ثبت شد!**\n\n"
            f"🆔 شماره پست: `{post_id}`\n"
            f"📅 زمان انتشار: `{persian_time}`\n"
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
        
        digi_price = await get_digikala_price(product_name)
        torob_price = await get_torob_price(product_name)
        
        response = f"💰 **قیمت محصول:**\n`{product_name}`\n\n"
        response += f"🛒 **دیجی‌کالا:** {digi_price}\n"
        response += f"🛍 **ترب:** {torob_price}\n\n"
        response += "📌 قیمت‌ها لحظه‌ای هستن و ممکنه تغییر کنن."
        
        await message.reply_text(response, reply_markup=main_menu())
        del user_data[user_id]
        return
    
    # مرحله 4: هوش مصنوعی OpenRouter
    if user_id in user_data and user_data[user_id].get("step") == "waiting_ai_question":
        question = message.text
        
        loading_msg = await message.reply_text("🧠 در حال فکر کردن با Llama 3.3... لطفاً چند ثانیه صبر کن.")
        
        try:
            ai_response = await get_ai_response(question)
            
            await loading_msg.delete()
            
            await message.reply_text(
                f"🧠 **پاسخ هوش مصنوعی سیب‌شاپ (Llama 3.3):**\n\n"
                f"{ai_response}\n\n"
                f"❓ سوال دیگه‌ای داری؟ بپرس!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت به منو", callback_data="back")]
                ])
            )
            
        except Exception as e:
            await loading_msg.delete()
            await message.reply_text(
                f"❌ خطا در ارتباط با هوش مصنوعی: {str(e)}\n"
                f"لطفاً دوباره تلاش کن.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
                ])
            )
        
        del user_data[user_id]
        return
    
    # مرحله 5: ویرایش پست
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
@app.on_message(filters.photo | filters.document | filters.video | filters.animation | filters.sticker)
async def handle_media_messages(client, message: Message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    
    if user_id in user_data and user_data[user_id].get("step") == "waiting_post_content":
        if message.photo:
            content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption or ""}
        elif message.video:
            content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
        elif message.animation:
            content = {"type": "animation", "file_id": message.animation.file_id, "caption": message.caption or ""}
        elif message.sticker:
            content = {"type": "sticker", "file_id": message.sticker.file_id}
        elif message.document:
            content = {"type": "document", "file_id": message.document.file_id, "caption": message.caption or ""}
        else:
            await message.reply_text("❌ نوع فایل پشتیبانی نمیشه!")
            return
        
        user_data[user_id]["content"] = content
        user_data[user_id]["step"] = "waiting_time"
        
        await message.reply_text(
            "⏰ **زمان انتشار رو مشخص کن**\n\n"
            "📅 **فرمت‌های قابل قبول:**\n"
            "• `امروز 14:30`\n"
            "• `فردا 20:00`\n"
            "• `پس فردا 18:00`\n"
            "• `1402/12/20 18:00`\n"
            "• `14:30`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
            ])
        )
        return
    
    if user_id in user_data and user_data[user_id].get("step") == "waiting_edit_content":
        post_id = user_data[user_id]["edit_post_id"]
        
        if message.photo:
            content = {"type": "photo", "file_id": message.photo.file_id, "caption": message.caption or ""}
        elif message.video:
            content = {"type": "video", "file_id": message.video.file_id, "caption": message.caption or ""}
        elif message.animation:
            content = {"type": "animation", "file_id": message.animation.file_id, "caption": message.caption or ""}
        elif message.sticker:
            content = {"type": "sticker", "file_id": message.sticker.file_id}
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
        elif content["type"] == "animation":
            await app.send_animation(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        elif content["type"] == "sticker":
            await app.send_sticker(CHANNEL_ID, content["file_id"])
        elif content["type"] == "document":
            await app.send_document(CHANNEL_ID, content["file_id"], caption=content.get("caption", ""))
        
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
        time = datetime.fromisoformat(post["scheduled_time"])
        persian_time = to_persian_date(time)
        line = f"🆔 #{post['id']} | {persian_time} | {status}\n"
        
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
        time = datetime.fromisoformat(post["scheduled_time"])
        persian_time = to_persian_date(time)
        keyboard.append([InlineKeyboardButton(f"✏️ ویرایش #{post['id']} - {persian_time}", callback_data=f"select_edit_{post['id']}")])
    
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
        "میتونی هر چیزی بفرستی: متن، عکس، فیلم، گیف، استیکر، فایل.",
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
        time = datetime.fromisoformat(post["scheduled_time"])
        persian_time = to_persian_date(time)
        keyboard.append([InlineKeyboardButton(f"🗑 حذف #{post['id']} - {persian_time}", callback_data=f"confirm_delete_{post['id']}")])
    
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

# ============== هوش مصنوعی OpenRouter ==============
@app.on_callback_query(filters.regex("ai_chat"))
async def ai_chat(client, callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ شما دسترسی ندارید!", show_alert=True)
        return
    
    await callback.message.edit_text(
        "🧠 **هوش مصنوعی سیب‌شاپ (Llama 3.3)**\n\n"
        "من یک هوش مصنوعی واقعی با مدل **Llama 3.3 70B** از OpenRouter هستم!\n"
        "میتونی هر سوالی بپرسی:\n"
        "• درباره محصولات اپل 🍎\n"
        "• مقایسه و راهنمای خرید 📱\n"
        "• هر سوال دیگه‌ای 🤔\n\n"
        "❓ سوال خودت رو بفرست:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back")]
        ])
    )
    user_data[callback.from_user.id] = {"step": "waiting_ai_question"}

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
        "• مک بوک\n\n"
        "مثال: `آیفون ۱۶ پرو`",
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
        
        now = datetime.now(pytz.timezone('Asia/Tehran'))
        persian_date = to_persian_date(now)
        
        stats_text = f"📊 **آمار کانال سیب‌شاپ**\n\n"
        stats_text += f"👥 تعداد اعضا: {members:,}\n"
        stats_text += f"📝 کل پست‌ها: {total}\n"
        stats_text += f"✅ ارسال شده: {sent}\n"
        stats_text += f"⏳ در انتظار: {pending}\n"
        stats_text += f"📅 امروز: {persian_date}\n"
        
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
2. هر چیزی بفرست: متن، عکس، فیلم، گیف، استیکر، فایل
3. زمان انتشار رو مشخص کن

**📋 مدیریت پست‌ها:**
• **لیست پست‌ها:** دیدن همه پست‌ها
• **ویرایش پست:** تغییر محتوای پست‌های در انتظار
• **حذف پست:** حذف پست‌های در انتظار

**🧠 هوش مصنوعی Llama 3.3:**
هر سوالی داری بپرس! من با مدل Llama 3.3 70B بهت پاسخ میدم.

**💰 استعلام قیمت:**
اسم محصول رو بفرست تا قیمت از دیجی‌کالا و ترب بگیرم

**📊 آمار کانال:**
مشاهده تعداد اعضا و وضعیت پست‌ها

⏰ **فرمت‌های زمان (تاریخ شمسی):**
• `امروز 14:30`
• `فردا 20:00`
• `پس فردا 18:00`
• `1402/12/20 18:00`
• `14:30` (همین امروز)
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
    print("🍎 ربات هوشمند سیب‌شاپ با Llama 3.3 در حال اجرا...")
    print(f"👥 فقط کاربران با آیدی {ADMIN_IDS} دسترسی دارند.")
    scheduler.start()
    app.run()
