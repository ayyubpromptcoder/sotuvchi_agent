# main.py
import os
import sys
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# db.py dan kerakli funksiyalarni import qilamiz
try:
    from db import (
        create_tables, get_user_role, add_new_product, get_all_products, 
        get_seller_by_password, update_seller_chat_id, add_new_seller,
        get_all_sellers, get_all_seller_passwords, get_seller_password_by_id,
        add_inventory, get_seller_debt_details, get_seller_id_by_chat_id
    )
except ImportError:
    print("!!! KRITIK XATO: db.py fayli topilmadi yoki import qilinmadi.", file=sys.stderr)
    sys.exit(1)


# --- 1. Konfiguratsiya va Global Holatlar ---
TOKEN = os.getenv("BOT_TOKEN")

# DB ni majburan yaratish/tekshirish (Server ishga tushganda)
try:
    print("🚀 [INIT] Baza jadvallarini yaratish/tekshirish boshlanmoqda...")
    create_tables()
    print("✅ [INIT] Baza jadvallari tayyor.")
except Exception as e:
    print(f"!!! KRITIK XATO (INIT): Baza jadvallarini yaratish/tekshirishda xato: {e}", file=sys.stderr)

ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_IDS", "").split(',') if i.strip()]

# Holatlar (ConversationHandler uchun)
(
    AWAITING_PASSWORD, ADMIN_MENU, SELLER_MENU, 
    NEW_PRODUCT_NAME, NEW_PRODUCT_PRICE,
    NEW_SELLER_NAME, NEW_SELLER_MAHALLA, NEW_SELLER_PHONE, NEW_SELLER_PASSWORD,
    AWAITING_PRODUCT_SELECTION,  
    AWAITING_PRODUCT_COUNT     
) = range(11)


# --- 2. Yordamchi Funksiyalar ---
def is_admin(chat_id: int) -> bool:
    return chat_id in ADMIN_IDS

def get_formatted_price(price: float) -> str:
    return f"{float(price):,.0f}".replace(",", " ") 

# --- 3. Buyruqlar (Handlers) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    
    print(f"🤖 [1/6] /start buyrug'i qabul qilindi. Chat ID: {chat_id}.") 
    
    # 1. Zudlik bilan tezkor javob yuborish
    try:
        await update.message.reply_text("✅ Tizim sizning xabaringizni qabul qildi. Roli tekshirilmoqda...") 
    except Exception as e:
        print(f"!!! DIQQAT: [XATO 3/6] Telegramga javob yuborishda xato: {e}", file=sys.stderr)
        
    try:
        # 2. Rolni aniqlash (DB chaqiruvi)
        if is_admin(chat_id):
            role = 'admin'
        else:
            role = get_user_role(chat_id)

        print(f"✅ [5/6] Foydalanuvchi roli aniqlandi: {role}")
        
        # 3. Mantiqiy yo'naltirish
        if role == 'admin':
            keyboard = [[KeyboardButton("/mahsulot"), KeyboardButton("/sotuvchi")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            await update.message.reply_text('Assalomu alaykum, Admin! Asosiy boshqaruv buyruqlari:', reply_markup=reply_markup)
            return ADMIN_MENU
        
        elif role == 'sotuvchi':
            keyboard = [[KeyboardButton("Mahsulotlarim"), KeyboardButton("Qarzdorligim")]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
            await update.message.reply_text("Siz tizimga kirdingiz. O'zingizga kerakli bo'limni tanlang:", reply_markup=reply_markup)
            return SELLER_MENU
        
        # 4. Ro'yxatdan o'tmagan foydalanuvchi
        await update.message.reply_text(
            "Assalomu alaykum. Iltimos, profilingizga kirish uchun maxsus parolingizni kiriting:",
            reply_markup=ReplyKeyboardRemove()
        )
        return AWAITING_PASSWORD
        
    except Exception as e:
        print(f"!!! KRITIK XATO start_command da: {e}.", file=sys.stderr) 
        await update.message.reply_text(f"Tizimda ichki xato yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return ConversationHandler.END


# --- Parol va Ro'yxatdan O'tish Mantiqlari ---

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    password = update.message.text
    chat_id = update.effective_chat.id
    
    seller_data = get_seller_by_password(password)
    
    if seller_data:
        update_seller_chat_id(seller_data['id'], chat_id)
        await update.message.reply_text(
            f"Muvaffaqiyatli kirdingiz, {seller_data['ism']}! Endi /start buyrug'ini bosing.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END 
    else:
        await update.message.reply_text("Kiritilgan parol noto'g'ri. Iltimos, qayta urinib ko'ring.")
        return AWAITING_PASSWORD

# --- Admin Mahsulot Bo'limi ---

async def mahsulot_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    keyboard = [[KeyboardButton("Mahsulotlar"), KeyboardButton("Yangi mahsulot kiritish")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Mahsulotlar bo\'limi:', reply_markup=reply_markup)
    return ADMIN_MENU

async def show_all_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    products = get_all_products()
    text = "📦 **Barcha Mahsulotlar Ro'yxati:**\n\n"
    for idx, product in enumerate(products):
        text += f"{idx+1}. **{product['nomi']}** ({get_formatted_price(product['narxi'])} so'm)\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    return ADMIN_MENU

async def new_product_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Iltimos, mahsulot nomini kiriting:")
    return NEW_PRODUCT_NAME

async def get_new_product_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_product_name'] = update.message.text
    await update.message.reply_text(f"'{context.user_data['new_product_name']}' mahsuloti uchun narxni (son) kiriting:")
    return NEW_PRODUCT_PRICE

async def get_new_product_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        price = float(update.message.text)
        product_name = context.user_data.pop('new_product_name')
        if add_new_product(product_name, price):
            await update.message.reply_text(f"Mahsulot kiritildi: **{product_name}** - {get_formatted_price(price)} so'm.", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"Xatolik yuz berdi yoki '{product_name}' allaqachon mavjud.")
        return await mahsulot_command(update, context) 
    except ValueError:
        await update.message.reply_text("Narx noto'g'ri. Iltimos, faqat son kiriting.")
        return NEW_PRODUCT_PRICE

# --- Admin Sotuvchi Bo'limi ---

async def sotuvchi_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    keyboard = [[KeyboardButton("Sotuvchilar"), KeyboardButton("Yangi Sotuvchi Qo'shish")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Sotuvchilar bo\'limi:', reply_markup=reply_markup)
    return ADMIN_MENU

async def sellers_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    keyboard = [
        [KeyboardButton("Barcha Sotuvchilar"), KeyboardButton("Sotuvchilar Parollari")],
        [KeyboardButton("/sotuvchi_orqaga")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text('Sotuvchilar Ro\'yxati Bo\'limi:', reply_markup=reply_markup)
    return ADMIN_MENU

async def show_all_sellers(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    sellers = get_all_sellers()
    if not sellers:
        await update.message.reply_text("Bazada hozircha hech qanday sotuvchi mavjud emas.")
        return await sellers_menu(update, context)

    keyboard = []
    current_row = []
    context.user_data['seller_names_to_id'] = {} 
    
    for seller in sellers:
        seller_name = seller['ism']
        context.user_data['seller_names_to_id'][seller_name] = seller['id']
        seller_button = KeyboardButton(seller_name)
        if len(current_row) < 2: current_row.append(seller_button)
        else:
            keyboard.append(current_row)
            current_row = [seller_button]
            
    if current_row: keyboard.append(current_row)
    keyboard.append([KeyboardButton("/sotuvchi_orqaga")]) 

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text("🧑‍🤝‍🧑 **Sotuvchini tanlang:**", reply_markup=reply_markup, parse_mode='Markdown')
    return ADMIN_MENU
    
async def new_seller_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Yangi sotuvchining **ism**ini kiriting:", reply_markup=ReplyKeyboardRemove())
    return NEW_SELLER_NAME
async def get_new_seller_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_seller_name'] = update.message.text
    await update.message.reply_text(f"Sotuvchining **mahalla**sini kiriting:")
    return NEW_SELLER_MAHALLA
async def get_new_seller_mahalla(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_seller_mahalla'] = update.message.text
    await update.message.reply_text(f"Sotuvchining **telefon nomeri**ni kiriting:")
    return NEW_SELLER_PHONE
async def get_new_seller_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['new_seller_phone'] = update.message.text
    await update.message.reply_text(f"Sotuvchi uchun **maxsus parol** o'ylab toping va kiriting:")
    return NEW_SELLER_PASSWORD
async def get_new_seller_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    parol = update.message.text
    ism = context.user_data.pop('new_seller_name')
    mahalla = context.user_data.pop('new_seller_mahalla')
    telefon = context.user_data.pop('new_seller_phone')
    if add_new_seller(ism, mahalla, telefon, parol):
        await update.message.reply_text(
            f"Yangi sotuvchi **{ism}** muvaffaqiyatli qo'shildi! Paroli: **{parol}**",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text("Sotuvchi qo'shishda xatolik yuz berdi (Balki parol allaqachon mavjud).")
    return await sotuvchi_command(update, context)

# ... (Qolgan Admin detali va Sotuvchi menyusi funksiyalari (start_new_inventory, show_my_debt, show_seller_debt, va h.k.) shu yerda davom etadi) ...

# --- Sotuvchi Menyusi ---

async def show_my_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    seller_id = get_seller_id_by_chat_id(chat_id)
    
    if not seller_id:
        await update.message.reply_text("Tizimda profilingiz topilmadi. /start orqali qayta urinib ko'ring.")
        return ConversationHandler.END

    total_debt, items = get_seller_debt_details(seller_id)

    formatted_debt = get_formatted_price(total_debt)
    
    text = f"💰 **Sizning Qarzdorlik Hisobotingiz:**\n\n**💳 JAMI QARZDORLIK: {formatted_debt} so'm**\n"
    
    if not items:
        text += "--------------------------------------\n📦 Sizga hali tovar berilmagan."
    
    await update.message.reply_text(text, parse_mode='Markdown')

    return SELLER_MENU 

async def show_seller_products(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    products = get_all_products()
    if not products:
        await update.message.reply_text("Bazada hozircha mahsulotlar mavjud emas.")
    else:
        product_list_text = "📦 **Mahsulotlarning Jami Ro'yxati:**\n\n"
        for idx, product in enumerate(products):
            product_list_text += f"{idx+1}. **{product['nomi']}** (Narxi: {get_formatted_price(product['narxi'])} so'm)\n"
        await update.message.reply_text(product_list_text, parse_mode='Markdown')
    return SELLER_MENU 


# --- 4. Botni ishga tushirish (Webhook Konfiguratsiyasi) ---

if not TOKEN:
    print("!!! KRITIK XATO: BOT_TOKEN muhit o'zgaruvchisi topilmadi.", file=sys.stderr)
    sys.exit(1)

application = Application.builder().token(TOKEN).build()

# Konversiya Handlerni yaratish
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_command)],
    states={
        AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
        
        ADMIN_MENU: [
            CommandHandler("mahsulot", mahsulot_command),
            MessageHandler(filters.Text("Mahsulotlar"), show_all_products),
            MessageHandler(filters.Text("Yangi mahsulot kiritish"), new_product_start),
            
            CommandHandler("sotuvchi", sotuvchi_command),
            MessageHandler(filters.Text("Sotuvchilar"), sellers_menu),
            MessageHandler(filters.Text("Yangi Sotuvchi Qo'shish"), new_seller_start),
            
            # ... (qolgan admin handlerlari)
        ],
        
        NEW_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_product_name)],
        NEW_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_product_price)],
        NEW_SELLER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_name)],
        NEW_SELLER_MAHALLA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_mahalla)],
        NEW_SELLER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_phone)],
        NEW_SELLER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_password)],
        
        # ... (qolgan holatlar)
        
        SELLER_MENU: [
            MessageHandler(filters.Text("Qarzdorligim"), show_my_debt),
            MessageHandler(filters.Text("Mahsulotlarim"), show_seller_products) 
        ]
    },
    fallbacks=[CommandHandler("start", start_command)],
)

application.add_handler(conv_handler)

def main() -> None:
    """Botni Webhook rejimida Render.com uchun ishga tushirish."""
    
    # Render odatda 10000 portni talab qiladi
    PORT = int(os.environ.get('PORT', 10000)) 
    
    # Render muhitidan asosiy URLni olish (Render tomonidan avtomatik o'rnatiladi)
    HOST_URL = os.environ.get('RENDER_EXTERNAL_URL')
    
    if not HOST_URL:
        print("!!! KRITIK XATO: RENDER_EXTERNAL_URL muhit o'zgaruvchisi topilmadi. Webhook ishga tushmaydi.", file=sys.stderr)
        return

    # Webhook URLni yasash (Masalan: https://myapp.onrender.com/webhook/token)
    WEBHOOK_PATH = f"/webhook/{TOKEN}"
    WEBHOOK_URL = HOST_URL + WEBHOOK_PATH
    
    print(f"🚀 [INIT] Webhook ishga tushirilmoqda. Host URL: {HOST_URL}. Port: {PORT}")
    
    # Webhook ishga tushirish (Uvicorn serverini ishlatadi)
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=WEBHOOK_PATH, 
        webhook_url=WEBHOOK_URL,      
    )

if __name__ == "__main__":
    main()
