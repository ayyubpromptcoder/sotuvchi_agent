import os
import sys
import threading
import asyncio
import signal
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging import getLogger

# Loggingni sozlash
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = getLogger("server")

# main.py dan Application va main funksiyalarini import qilamiz
try:
    # application obyektining main.py da GLOBAL darajada e'lon qilinganligi muhim!
    from main import main, application 
except ImportError as e:
    logger.error(f"!!! KRITIK XATO: main.py fayli topilmadi yoki import qilinmadi: {e}")
    sys.exit(1)

# --- Konfiguratsiya ---
HOST = '0.0.0.0'
# Render talab qiladigan portni muhit o'zgaruvchisidan olish
PORT = int(os.getenv("PORT", 10000)) 

# --- Global O'zgaruvchilar ---
httpd = None
bot_thread = None
bot_loop = None # Botni ishga tushiradigan Event Loop

# --- Asosiy Xizmat Ishlari ---

def start_bot_loop():
    """Botning asosiy asinxron jarayonini yangi threadda boshlash."""
    global bot_loop
    # Yangi Event Loop yaratish va uni shu Thread uchun o'rnatish
    bot_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(bot_loop)
    
    logger.info("🤖 [POLLING THREAD] Bot Polling ishga tushirilmoqda.")
    
    # main() koroutinni loopda ishga tushiramiz
    try:
        # main() funksiyasini syncron tarzda ishga tushirish (Long Polling)
        # Bu funksiya Bot to'xtatilmaguncha bloklaydi.
        bot_loop.run_until_complete(main())
    except asyncio.CancelledError:
        logger.warning("Bot jarayoni bekor qilindi (Cancelled).")
    except Exception as e:
        logger.error(f"!!! KRITIK Xato (Bot Thread): {e}")


def stop_all(signum=None, frame=None):
    """
    SIGTERM signali kelganda serverni va Bot Loopni xavfsiz to'xtatadi.
    Bu kod Cannot close a running event loop xatosini hal qilish uchun
    PTB Application.stop() usulini qo'llaydi.
    """
    global httpd, bot_thread, bot_loop, application
    logger.warning("⚠️ SIGTERM signali qabul qilindi. Jarayonlar to'xtatilmoqda...")
    
    # 1. HTTP serverni to'xtatish (httpd.shutdown alohida threadda chaqiriladi)
    if httpd:
        logger.info("Health Check Serveri o'chirilmoqda...")
        threading.Thread(target=httpd.shutdown).start()
        
    # 2. Botning Event Loop'ini xavfsiz to'xtatish
    if bot_loop and bot_loop.is_running():
        logger.info("Botning Asyncio Loop'i yopilmoqda...")
        
        async def shutdown_ptb():
            """Asinxron ravishda PTB ni yopish."""
            logger.info("PTB Application.stop() chaqirilmoqda...")
            await application.stop() # PTB ni xavfsiz yopish uchun asosiy usul
            
        try:
            # Asinxron to'xtatishni bot_loop orqali chaqirish
            future = asyncio.run_coroutine_threadsafe(shutdown_ptb(), bot_loop)
            
            # Application yopilishi uchun 5 soniya vaqt beramiz
            future.result(timeout=5) 
            logger.info("PTB Application muvaffaqiyatli yopildi.")

        except asyncio.TimeoutError:
            logger.error("PTB Application 5 soniya ichida yopilmadi. Majburan to'xtatish davom etmoqda.")
        except Exception as e:
            logger.error(f"PTBni yopishda kutilmagan xato: {e}")

        # Loopni to'liq tozalash va to'xtatish signali yuborish
        # Qolgan barcha vazifalarni (Polling) bekor qilish
        for task in asyncio.all_tasks(bot_loop):
            task.cancel()
        
        # Loop to'xtatish signali yuborish (Thread-xavfsiz)
        if bot_loop.is_running():
            bot_loop.call_soon_threadsafe(bot_loop.stop)
            
        # Bot Threadni asosiy threadda to'xtatish uchun qisqa vaqt berish
        if bot_thread and bot_thread.is_alive():
             bot_thread.join(timeout=1)
        
    # Asosiy jarayonni tugatish
    logger.info("Render jarayoni yakunlanmoqda.")
    sys.exit(0)


# --- HTTP Health Check Server (Render uchun) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Render/Platformalar uchun Health Checkni ta'minlaydi (GET/HEAD so'rovlarini qo'llab-quvvatlaydi)."""
    
    def _send_response(self, status_code, message=None):
        self.send_response(status_code)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        if message:
            self.wfile.write(message.encode('utf-8'))
    
    def do_GET(self):
        if self.path == '/health':
            self._send_response(200, 'OK')
        else:
            self._send_response(404)

    # !!! do_HEAD qo'shildi (501 Unsupported method xatosini hal qilish uchun) !!!
    def do_HEAD(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()
            
    # Agar loglar o'ta ko'p bo'lsa, bu funksiyani bo'sh qoldirish mumkin.
    def log_message(self, format, *args):
        return


def start_http_server():
    """Health Check serverni boshlash (Asosiy Threadda)."""
    global httpd
    
    # SIGTERM (15) va SIGINT (Ctrl+C) signallarini stop_all funksiyasiga ulash
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)

    try:
        httpd = HTTPServer((HOST, PORT), HealthCheckHandler)
        logger.info(f"🚀 Health Check Server {HOST}:{PORT} portida ishga tushdi (Asosiy Thread).")
        # serve_forever() bu threadni bloklaydi, to'xtatish uchun httpd.shutdown() kerak
        httpd.serve_forever() 
    except Exception as e:
        logger.error(f"!!! KRITIK Xato (HTTP Server): {e}")


# --- Ishga Tushirish Mantiqi ---

if __name__ == '__main__':
    # 1. Botni alohida Threadda boshlash (Asinxron operatsiyalar uchun)
    bot_thread = threading.Thread(target=start_bot_loop, name="BotPollingThread")
    bot_thread.start()
    
    # Kichik kutish vaqti berish (Loop to'liq boshlanishi uchun)
    time.sleep(1)

    # 2. Asosiy Threadda Health Check serverni boshlash (Bloklovchi)
    start_http_server()
    
    # Agar bu nuqtaga kelsa (HTTP server to'xtatilsa), bot threadni tozalaymiz
    if bot_thread and bot_thread.is_alive():
        bot_thread.join()
