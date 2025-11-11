# server.py
import os
import uvicorn
from fastapi import FastAPI, Request, Response
from telegram import Update
from main import application, main 
from db import create_tables # <--- db dan create_tables ni import qilamiz

# --- Konfiguratsiya ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", 8000))
WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"

# FastAPI ilovasini yaratish
app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Server ishga tushganda botning Webhook manzilini o'rnatadi va jadvallarni yaratadi."""
    
    # 1. DB Jadvallarini yaratish (Muhim!)
    create_tables() 
    
    try:
        # 2. Botning Webhook URL manzilini aniqlaymiz.
        host_name = os.getenv("RENDER_EXTERNAL_HOSTNAME")
        if not host_name:
            print("RENDER_EXTERNAL_HOSTNAME topilmadi. Webhook o'rnatilmaydi.")
            return

        WEBHOOK_URL = f"https://{host_name}{WEBHOOK_PATH}"
        
        # 3. Telegram API ga Webhookni o'rnatish
        await application.bot.set_webhook(url=WEBHOOK_URL)
        print(f"✅ Webhook muvaffaqiyatli o'rnatildi: {WEBHOOK_URL}")

    except Exception as e:
        print(f"❌ Webhookni o'rnatishda xato: {e}")

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
        # Xabarni qabul qilishda yoki uni Python-telegram-bot formatiga o'tkazishda xato
        print(f"❌ Update qabul qilishda xato: {e}") 
        return Response(status_code=500)

if __name__ == "__main__":
    main() 
    uvicorn.run(app, host="0.0.0.0", port=PORT)
