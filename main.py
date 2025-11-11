# main.py - To'liq va To'g'ri Versiya

import os
import sys
# Threadpool importini olib tashlaymiz, chunki PTB uni avtomatik boshqaradi.
from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler, CallbackQueryHandler
)

# db.py dan kerakli funksiyalarni import qilamiz
# Eslatma: 'db' dan import qilishda sinxron DB chaqiruvlari PTB tomonidan threadpoolga yuboriladi.
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
    # Eslatma: Agar create_tables sinxron bo'lsa, u bloklaydi.
    # Lekin biz uni server ishga tushishidan oldin chaqiramiz, muammo yo'q.
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

# /start buyrug'i (DB chaqiruvini optimallashtirish shart emas, chunki PTB uni avtomatik threadpoolga yuboradi)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    
    print(f"🤖 [1/6] /start buyrug'i qabul qilindi. Chat ID: {chat_id}.") 
    
    # Zudlik bilan tezkor javob (Long Pollingda bu shart emas, lekin qoldiramiz)
    await update.message.reply_text("✅ Tizim sizning xabaringizni qabul qildi. Roli tekshirilmoqda...") 
        
    try:
        # Rolni aniqlash
        if is_admin(chat_id):
            role = 'admin'
        else:
            # get_user_role sinxron bo'lgani uchun, PTB uni avtomatik threadpoolda bajaradi.
            role = get_user_role(chat_id)

        print(f"✅ [5/6] Foydalanuvchi roli aniqlandi: {role}")
        
        # Mantiqiy yo'naltirish
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
        
        await update.message.reply_text(
            "Assalomu alaykum. Iltimos, profilingizga kirish uchun maxsus parolingizni kiriting:",
            reply_markup=ReplyKeyboardRemove()
        )
        return AWAITING_PASSWORD
            
    except Exception as e:
        print(f"!!! KRITIK XATO start_command da: {e}.", file=sys.stderr) 
        await update.message.reply_text(f"Tizimda ichki xato yuz berdi. Iltimos, keyinroq urinib ko'ring.")
        return ConversationHandler.END


# --- Barcha boshqa Handlers (O'zgartirishsiz qoldiriladi) ---

# Parolni Tekshirish Mantiqi
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

async def show_seller_password(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    
    selected_seller_id = context.user_data.get('selected_seller_id')
    selected_seller_name = context.user_data.get('selected_seller_name')

    if not selected_seller_id:
        await update.message.reply_text("Avval sotuvchini tanlang.")
        return ADMIN_MENU

    password = get_seller_password_by_id(selected_seller_id)
    
    if password:
        await update.message.reply_text(
            f"👤 **{selected_seller_name}** paroli: `{password}`",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"Parol topilmadi yoki xatolik yuz berdi.")
        
    return await show_seller_detail_menu(update, context) 

async def show_seller_passwords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    passwords = get_all_seller_passwords()
    text = "🔐 **Sotuvchilar Parollari Ro'yxati:**\n\n"
    for seller in passwords:
        text += f"👤 {seller['ism']}: `{seller['parol']}`\n"
    await update.message.reply_text(text, parse_mode='Markdown')
    return await sellers_menu(update, context)


# --- Admin Sotuvchi Qo'shish ---

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

# --- Admin Sotuvchi Detal Menyusi ---

async def show_seller_detail_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END

    # Agar Message Handler orqali kelsa (sotuvchi tanlansa)
    if update.message and update.message.text:
        selected_seller_name = update.message.text
        seller_id_map = context.user_data.get('seller_names_to_id', {})
        selected_seller_id = seller_id_map.get(selected_seller_name)
        
        if selected_seller_id:
            context.user_data['selected_seller_id'] = selected_seller_id
            context.user_data['selected_seller_name'] = selected_seller_name
    
    selected_seller_name = context.user_data.get('selected_seller_name', 'Tanlanmagan Sotuvchi')
    
    if selected_seller_name == 'Tanlanmagan Sotuvchi':
        await update.message.reply_text("Iltimos, avval ro'yxatdan sotuvchini tanlang.")
        return ADMIN_MENU

    keyboard = [
        [KeyboardButton("Mahsulotlar va Qarzdorlik"), KeyboardButton("Yangi Tovar Berish")],
        [KeyboardButton("Sotuvchi Paroli")],
        [KeyboardButton("/sotuvchi_orqaga_detal")] 
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)
    
    await update.message.reply_text(
        f"👤 **{selected_seller_name}** uchun boshqaruv menyusi:",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return ADMIN_MENU

# --- Admin Tovar Berish Mantiqi ---

async def start_new_inventory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    
    selected_seller_id = context.user_data.get('selected_seller_id')
    selected_seller_name = context.user_data.get('selected_seller_name')

    if not selected_seller_id:
        await update.message.reply_text("Avval sotuvchini tanlang.")
        return ADMIN_MENU

    products = get_all_products()
    if not products:
        await update.message.reply_text("Bazada mahsulotlar mavjud emas. Avval mahsulot kiriting.")
        return ADMIN_MENU

    inline_keyboard = []
    for i in range(0, len(products), 2):
        row = []
        for product in products[i:i+2]:
             callback_data = f"prod:{product['id']}"
             row.append(InlineKeyboardButton(product['nomi'], callback_data=callback_data))
        inline_keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(inline_keyboard)
    
    await update.message.reply_text(
        f"➡️ **{selected_seller_name}** uchun qaysi **mahsulot**ni berasiz?",
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    return AWAITING_PRODUCT_SELECTION 

async def select_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    callback_data = query.data
    
    if callback_data.startswith('prod:'):
        product_id = int(callback_data.split(':')[1])
        context.user_data['temp_product_id'] = product_id
        
        await query.edit_message_text(
            f"✅ Mahsulot tanlandi. Iltimos, **necha dona** berayotganingizni kiriting (faqat butun son):",
            parse_mode='Markdown'
        )
        return AWAITING_PRODUCT_COUNT
    
    return AWAITING_PRODUCT_SELECTION 

async def finalize_inventory_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    
    selected_seller_id = context.user_data.get('selected_seller_id')
    selected_seller_name = context.user_data.get('selected_seller_name')
    product_id = context.user_data.get('temp_product_id')
    
    try:
        count = int(update.message.text)
        if count <= 0: raise ValueError
    except ValueError:
        await update.message.reply_text("Noto'g'ri qiymat. Iltimos, musbat butun son kiriting.")
        return AWAITING_PRODUCT_COUNT

    success, product_name, total_price = add_inventory(selected_seller_id, product_id, count)
    
    if success:
        formatted_price = get_formatted_price(total_price)
        await update.message.reply_text(
            f"✅ Tovar muvaffaqiyatli berildi!\n\n"
            f"👤 Sotuvchi: **{selected_seller_name}**\n"
            f"📦 Mahsulot: **{product_name}**\n"
            f"🔢 Soni: **{count} dona**\n"
            f"💵 Jami narx: **{formatted_price} so'm**",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(f"Xatolik yuz berdi: {product_name}")

    context.user_data.pop('temp_product_id', None)
    return await show_seller_detail_menu(update, context) 

# --- Admin Qarzdorlik Bo'limi ---

async def show_seller_debt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_admin(update.effective_chat.id): return ConversationHandler.END
    
    selected_seller_id = context.user_data.get('selected_seller_id')
    selected_seller_name = context.user_data.get('selected_seller_name')

    if not selected_seller_id:
        await update.message.reply_text("Avval sotuvchini tanlang.")
        return ADMIN_MENU

    total_debt, items = get_seller_debt_details(selected_seller_id)

    formatted_debt = get_formatted_price(total_debt)
    
    text = f"💰 **{selected_seller_name}** uchun qarzdorlik hisoboti:\n\n"
    text += f"**💳 JAMI QARZDORLIK: {formatted_debt} so'm**\n"
    text += "--------------------------------------\n"
    
    if not items:
        text += "📦 Sotuvchiga hali hech qanday tovar berilmagan."
    else:
        text += "📦 **Berilgan Tovarlar Ro'yxati:**\n\n"
        
        # Xabarni 15 tadan bo'lib yuborish
        chunk_size = 15
        
        # Eslatma: items ro'yxatdagi ma'lumotlar bilan ishlash
        
        # Barcha qismlarni yig'amiz
        all_item_texts = []
        for item in items:
            all_item_texts.append(
                f"▪️ **{item['mahsulot_nomi']}**\n"
                f"   Soni: {item['soni']} dona\n"
                f"   Narxi: {get_formatted_price(item['jami_narxi'])} so'm\n"
                f"   Sana: {item['sana']}\n"
            )
        
        # Jami qarzdorlik hisoboti
        await update.message.reply_text(text, parse_mode='Markdown')
        
        # Har bir bo'lakni yuborish
        for i in range(0, len(all_item_texts), chunk_size):
            chunk_text = "\n".join(all_item_texts[i:i + chunk_size])
            await update.message.reply_text(f"**Tovarlar ro'yxati (davomi):**\n\n{chunk_text}", parse_mode='Markdown')


    return await show_seller_detail_menu(update, context)

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
    else:
        text += "--------------------------------------\n📦 **Olingan Tovarlar Ro'yxati:**\n\n"
        
        # Xabarni 15 tadan bo'lib yuborish
        chunk_size = 15
        
        # Barcha qismlarni yig'amiz
        all_item_texts = []
        for item in items:
            all_item_texts.append(
                f"▪️ **{item['mahsulot_nomi']}**\n"
                f"   Soni: {item['soni']} dona\n"
                f"   Narxi: {get_formatted_price(item['jami_narxi'])} so'm\n"
                f"   Sana: {item['sana']}\n"
            )
        
        # Jami qarzdorlik hisoboti
        await update.message.reply_text(text, parse_mode='Markdown')
        
        # Har bir bo'lakni yuborish
        for i in range(0, len(all_item_texts), chunk_size):
            chunk_text = "\n".join(all_item_texts[i:i + chunk_size])
            await update.message.reply_text(f"**Tovarlar ro'yxati (davomi):**\n\n{chunk_text}", parse_mode='Markdown')

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

# --- 4. Botni ishga tushirish (Long Polling Konfiguratsiyasi) ---

if not TOKEN:
    print("!!! KRITIK XATO: BOT_TOKEN muhit o'zgaruvchisi topilmadi.", file=sys.stderr)
    sys.exit(1)

application = Application.builder().token(TOKEN).build()

# Konversiya Handlerni yaratish (O'zgartirishsiz)
conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start_command)],
    states={
        AWAITING_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password)],
        
        ADMIN_MENU: [
            # Mahsulot
            CommandHandler("mahsulot", mahsulot_command),
            MessageHandler(filters.Text("Mahsulotlar"), show_all_products),
            MessageHandler(filters.Text("Yangi mahsulot kiritish"), new_product_start),
            
            # Sotuvchi
            CommandHandler("sotuvchi", sotuvchi_command),
            MessageHandler(filters.Text("Sotuvchilar"), sellers_menu),
            MessageHandler(filters.Text("Yangi Sotuvchi Qo'shish"), new_seller_start),
            
            # Sotuvchi Ro'yxati
            MessageHandler(filters.Text("Barcha Sotuvchilar"), show_all_sellers),
            MessageHandler(filters.Text("Sotuvchilar Parollari"), show_seller_passwords),
            
            # Sotuvchi Detali
            MessageHandler(filters.Text("Sotuvchi Paroli"), show_seller_password),
            MessageHandler(filters.Text("Yangi Tovar Berish"), start_new_inventory),
            MessageHandler(filters.Text("Mahsulotlar va Qarzdorlik"), show_seller_debt),
            
            # Orqaga qaytish
            CommandHandler("sotuvchi_orqaga", sotuvchi_command),
            CommandHandler("sotuvchi_orqaga_detal", sellers_menu),

            # Sotuvchi ismini tanlash (show_all_sellersdan keyin)
            MessageHandler(
                filters.TEXT & ~filters.COMMAND & filters.UpdateType.MESSAGE,
                show_seller_detail_menu
            )
        ],
        
        # Ma'lumot kiritish holatlari
        NEW_PRODUCT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_product_name)],
        NEW_PRODUCT_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_product_price)],
        NEW_SELLER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_name)],
        NEW_SELLER_MAHALLA: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_mahalla)],
        NEW_SELLER_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_phone)],
        NEW_SELLER_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_new_seller_password)],
        
        # Tovar Berish mantiqi
        AWAITING_PRODUCT_SELECTION: [CallbackQueryHandler(select_product_callback)],
        AWAITING_PRODUCT_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, finalize_inventory_count)],
        
        # Sotuvchi Menyusi
        SELLER_MENU: [
            MessageHandler(filters.Text("Qarzdorligim"), show_my_debt),
            MessageHandler(filters.Text("Mahsulotlarim"), show_seller_products) 
        ]
    },
    fallbacks=[CommandHandler("start", start_command)],
)

application.add_handler(conv_handler)


# --- ASOSIY ISHGA TUSHIRISH FUNKSIYASI ---
async def main() -> None:
    """Server.py tomonidan chaqiriladigan asosiy asinxron bot funksiyasi (Long Polling)."""
    print("🤖 [INIT] Bot asosiy jarayoni (Long Polling) ishga tushirildi.")
    # Webhookni to'liq o'chirib tashlaymiz
    await application.bot.delete_webhook()
    print("✅ Telegram Webhook o'chirildi.")
    # Botni Long Polling rejimida ishga tushirish
    await application.run_polling()


# main.py endi o'zi ishga tushmaydi, balki server.py orqali ishga tushadi
# if __name__ == "__main__": blokini to'liq o'chirib tashladik.
