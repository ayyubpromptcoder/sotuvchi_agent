# server.py - SIGTERM va Loop yopish xatolarini hal qiluvchi yangi versiya

import os
import threading
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import signal
import asyncio
import sys

# main.py dan asosiy funksiyani import qilamiz
try:
    from main import main as bot_main_async_func 
except ImportError:
    logging.error("!!! KRITIK XATO: main.py fayli import qilinmadi.")
    sys.exit(1)

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 8080))

# Global o'zgaruvchilar
httpd = None 
bot_thread = None
bot_loop = None # Yangi: Botning event loop'ini saqlaymiz

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
    global bot_loop
    logger.info("🤖 [POLLING THREAD] Bot Polling ishga tushirilmoqda.")
    try:
        # Yangi event loop yaratish va uni joriy thread uchun o'rnatish
        bot_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(bot_loop)
        
        # main.py dagi async def main() ni chaqirish
        bot_loop.run_until_complete(bot_main_async_func())
    except asyncio.CancelledError:
        logger.info("✅ Bot Polling thread'i bekor qilindi.")
    except Exception as e:
        # Loop yopishdagi xatolar odatda shu yerda ushlanadi.
        logger.error(f"!!! Xato (Bot Thread): {e}")

def stop_all(signum=None, frame=None):
    """SIGTERM signali kelganda serverni va Bot Loopni to'xtatadi."""
    global httpd, bot_thread, bot_loop
    logger.warning("⚠️ SIGTERM signali qabul qilindi. Jarayonlar to'xtatilmoqda...")
    
    # 1. Botning Event Loopini yopish (asosiy muammo)
    if bot_loop and bot_loop.is_running():
        logger.info("Botning Asyncio Loop'i yopilmoqda...")
        
        # Loop ichidagi barcha async tasklarni bekor qilish
        for task in asyncio.all_tasks(bot_loop):
            task.cancel()
        
        # Loopni xavfsiz to'xtatish uchun asinxron funksiya yozish
        def stop_loop():
            if bot_loop:
                bot_loop.stop()
                
        # Loopni boshqa thread orqali to'xtatish
        if bot_loop.is_running():
            bot_loop.call_soon_threadsafe(stop_loop)
            
    # 2. HTTP serverni to'xtatish
    if httpd:
        threading.Thread(target=httpd.shutdown).start()
        
    # Asosiy jarayonni tugatish
    sys.exit(0) 

def start_server():
    """Health Check Serverni va Bot Threadni boshlaydi."""
    global httpd, bot_thread
    
    # SIGTERM handlerini o'rnatish
    # PTB dan farqli o'laroq, bu yerda SIGTERMni to'g'ri boshqarish Render uchun muhim.
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
