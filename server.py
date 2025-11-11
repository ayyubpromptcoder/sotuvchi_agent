import os
import sys
import threading
import asyncio
import signal
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from logging import getLogger

# main.py dan Application va main funksiyalarini import qilamiz
try:
    from main import main, application 
except ImportError as e:
    print(f"!!! KRITIK XATO: main.py fayli topilmadi yoki import qilinmadi: {e}", file=sys.stderr)
    sys.exit(1)

# --- Konfiguratsiya ---
HOST = '0.0.0.0'
PORT = int(os.getenv("PORT", 10000)) # Render talab qiladigan port
logger = getLogger("server")

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
    
    # main() koroutinni loopda ishga tushiramiz
    try:
        # main() funksiyasini syncron tarzda ishga tushirish (Long Polling)
        bot_loop.run_until_complete(main())
    except asyncio.CancelledError:
        logger.info("Bot jarayoni to'xtatildi (Cancelled).")
    except Exception as e:
        logger.error(f"!!! Xato (Bot Thread): {e}")


def stop_all(signum=None, frame=None):
    """SIGTERM signali kelganda serverni va Bot Loopni xavfsiz to'xtatadi."""
    global httpd, bot_thread, bot_loop, application
    logger.warning("⚠️ SIGTERM signali qabul qilindi. Jarayonlar to'xtatilmoqda...")
    
    # 1. HTTP serverni to'xtatish
    if httpd:
        logger.info("HTTP Health Check Serveri o'chirilmoqda...")
        # Shutdown() funksiyasi Blocking bo'lgani uchun uni alohida Threadda ishlatamiz
        threading.Thread(target=httpd.shutdown).start()
        
    # 2. Botning Event Loop'ini xavfsiz to'xtatish (Eng Muhim Qism)
    if bot_loop and bot_loop.is_running():
        logger.info("Botning Asyncio Loop'i va PTB Application yopilmoqda...")
        
        async def shutdown_ptb():
            """Asinxron ravishda PTB ni to'xtatish."""
            logger.info("PTB Application.stop() chaqirilmoqda...")
            await application.stop() # PTB ni xavfsiz yopish uchun PTB ning o'z usuli
            
        try:
            # Asinxron to'xtatishni bot_loop orqali chaqirish
            future = asyncio.run_coroutine_threadsafe(shutdown_ptb(), bot_loop)
            
            # 5 soniya kutamiz
            future.result(timeout=5)
            logger.info("PTB Application muvaffaqiyatli yopildi.")

        except asyncio.TimeoutError:
            logger.error("PTB Application 5 soniya ichida yopilmadi. Majburan to'xtatish...")
        except Exception as e:
            logger.error(f"PTBni yopishda kutilmagan xato: {e}")

        # Loopning o'zini to'xtatish
        bot_loop.call_soon_threadsafe(bot_loop.stop)
        
    # Asosiy jarayonni tugatish
    logger.info("Render jarayoni yakunlanmoqda.")
    sys.exit(0)


# --- HTTP Health Check Server (Render uchun) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Render uchun oddiy Health Check / Liveness Check."""
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        else:
            self.send_response(404)
            self.end_headers()

def start_http_server():
    """Health Check serverni boshlash (Asosiy Threadda)."""
    global httpd
    
    # SIGTERM (15) va SIGINT (Ctrl+C) signallarini stop_all funksiyasiga ulash
    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)

    try:
        httpd = HTTPServer((HOST, PORT), HealthCheckHandler)
        logger.info(f"🚀 Health Check Server {HOST}:{PORT} portida ishga tushdi (Asosiy Thread).")
        # httpd.serve_forever() serverni boshqa joydan to'xtatish imkonini beradi
        httpd.serve_forever() 
    except Exception as e:
        logger.error(f"!!! Xato (HTTP Server): {e}")


# --- Ishga Tushirish Mantiqi ---

if __name__ == '__main__':
    # 1. Botni alohida Threadda boshlash (Asinxron operatsiyalar uchun)
    bot_thread = threading.Thread(target=start_bot_loop, name="BotPollingThread")
    bot_thread.start()
    logger.info("🤖 [POLLING THREAD] Bot Polling ishga tushirilmoqda.")

    # Kichik kutish vaqti berish (Loop to'liq boshlanishi uchun)
    time.sleep(1)

    # 2. Asosiy Threadda Health Check serverni boshlash
    start_http_server()
    
    # Server o'chirilgandan keyin Bot Threadni tozalash
    if bot_thread.is_alive():
        bot_thread.join(timeout=5)
