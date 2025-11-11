# server.py
import os
import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from main import application, main

# --- Konfiguratsiya ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
# WEBHOOK_URL_BASE ni hosting platformasi avtomatik yaratadi (masalan: https://my-bot-name.onrender.com)

# FastAPI ilovasini yaratish
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Server ishga tushganda botning Webhook manzilini o'rnatadi."""
    try:
        # 1. Botning Webhook URL manzilini aniqlaymiz.
        # RENDER platformasida 'RENDER_EXTERNAL_HOSTNAME' muhit o'zgaruvchisidan foydalanish tavsiya etiladi.
        host_name = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if not host_name:
            print("RENDER_EXTERNAL_HOSTNAME topilmadi. Webhook o'rnatilmaydi.")
            return

        WEBHOOK_URL = f"https://{host_name}{WEBHOOK_PATH}"
        
        # 2. Telegram API ga Webhookni o'rnatish
        await application.bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook muvaffaqiyatli o'rnatildi: {WEBHOOK_URL}")

    except Exception as e:
        print(f"❌ Webhookni o'rnatishda xato: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Server o'chganda Webhookni o'chiradi (ixtiyoriy, lekin tavsiya etiladi)."""
    # await application.bot.delete_webhook()
    print("Bot serveri o'chirildi.")

@app.post(WEBHOOK_PATH)
async def webhook_handler(request: Request):
    """Telegramdan kelgan yangilanishlarni (updates) qabul qiladi va main.py ga uzatadi."""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Dispatcher orqali update ni main.py dagi handlerlarga yuboramiz
        await application.update_queue.put(update)

        return Response(status_code=200) # Telegramga muvaffaqiyatli qabul qilinganini bildiramiz

    except Exception as e:
        print(f"Update qabul qilishda xato: {e}")
        return Response(status_code=500)

# Agar server.py to'g'ridan-to'g'ri ishga tushsa (deployment platformasi uchun)
if __name__ == "__main__":
    main() # main.py dagi ilovani ishga tushirish mantiqini ishlatamiz
    
    # Uvicornni Webhookni tinglash uchun ishga tushirish
    uvicorn.run(app, host="0.0.0.0", port=PORT)
