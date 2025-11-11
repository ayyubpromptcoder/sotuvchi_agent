# server.py - Render uchun optimallashtirilgan barqaror versiya

import os
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import signal
import asyncio
import sys # asyncio.run ni tozalash uchun kerak

# main.py dan asosiy funksiyani import qilamiz
try:
    from main import main as bot_main_async_func 
except ImportError:
    logging.error("!!! KRITIK XATO: main.py fayli import qilinmadi.")
    sys.exit(1)

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Render Environment Variable'dan PORT ni olish
PORT = int(os.environ.get("PORT", 8080))

# Global o'zgaruvchilar
httpd = None 
bot_thread = None

# --- HTTP HANDLER (Health Check uchun) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Render'dan kelgan Health Check so'rovlariga javob beradi."""
    
    def _send_response(self):
        self.send_response(200) # 200 OK
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running and awake.")

    def do_GET(self): self._send_response()
    def do_HEAD(self): self._send_response()
    def do_POST(self): self._send_response()
        
    def log_message(self, format, *args): 
        # HTTP serverning keraksiz loglarini o'chiradi
        return 

# --- SERVER BOSHQARUVI ---

def start_bot_polling():
    """Bot Pollingni mustaqil, yangi event loop bilan ishga tushiradi."""
    logger.info("🤖 [POLLING THREAD] Bot Polling ishga tushirilmoqda.")
    try:
        # Yangi event loop yaratish va uni joriy thread uchun o'rnatish
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # main.py dagi async def main() ni chaqirish
        loop.run_until_complete(bot_main_async_func())
    except asyncio.CancelledError:
        logger.info("✅ Bot Polling thread'i bekor qilindi.")
    except Exception as e:
        logger.error(f"!!! KRITIK XATO (Bot Thread): {e}")

def stop_all(signum=None, frame=None):
    """SIGTERM signali kelganda serverni to'xtatadi."""
    global httpd, bot_thread
    logger.warning("⚠️ SIGTERM signali qabul qilindi. Jarayonlar to'xtatilmoqda...")
    
    # 1. HTTP serverni to'xtatish
    if httpd:
        threading.Thread(target=httpd.shutdown).start()
        
    # 2. Bot threadini to'xtatish (Afsuski, to'g'ri to'xtatish PTB ga bog'liq, lekin Render majburiy yopadi)
    if bot_thread and bot_thread.is_alive():
        # Bu yerda botning ichki asyncio loopiga signal yuborish murakkab,
        # shuning uchun shunchaki Render ning majburiy to'xtatishini kutamiz.
        logger.info("Bot Polling thread'i yopilishi kutilmoqda...")

    sys.exit(0) # Jarayonni xavfsiz tugatish

def start_server():
    """Health Check Serverni va Bot Threadni boshlaydi."""
    global httpd, bot_thread
    
    # SIGTERM handlerini o'rnatish
    signal.signal(signal.SIGTERM, stop_all)

    # 1. Bot Pollingni alohida Threadda ishga tushirish
    bot_thread = threading.Thread(target=start_bot_polling)
    bot_thread.daemon = True # Asosiy jarayon tugasa, bu ham tugaydi
    bot_thread.start()
    
    # 2. Health Check Serverni asosiy Threadda ishga tushirish
    server_address = ('0.0.0.0', PORT)
    try:
        httpd = HTTPServer(server_address, HealthCheckHandler)
        logger.info(f"🚀 Health Check Server 0.0.0.0:{PORT} portida ishga tushdi (Asosiy Thread).")
        # server.py jarayonini Health Check Server ishlayotgan holda ushlab turadi
        httpd.serve_forever() 
    except Exception as e:
        logger.error(f"!!! KRITIK XATO: HTTP Serverni ishga tushirishda xato: {e}")
        stop_all()


if __name__ == "__main__":
    start_server()
