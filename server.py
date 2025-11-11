# server.py - Render Web Service va PTB Long Pollingni bog'lovchi fayl

import os
import threading
import asyncio
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import signal 

# main.py dan asosiy funksiyani import qilamiz
try:
    from main import main as bot_main_async_func # main.py dagi async def main()
except ImportError:
    # Agar main.py da xato bo'lsa
    logging.error("!!! KRITIK XATO: main.py fayli import qilinmadi. Tekshiring!")
    exit(1)

# Logging sozlamalari
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Render Environment Variable'dan PORT ni olish
PORT = int(os.environ.get("PORT", 8080))

# Global o'zgaruvchilar
polling_task = None
httpd = None 

# --- HTTP HANDLER (Health Check uchun) ---

class HealthCheckHandler(BaseHTTPRequestHandler):
    """Render'dan kelgan Health Check so'rovlariga javob beradi."""
    
    def _send_response(self):
        """Javob yuborish uchun yordamchi funksiya."""
        self.send_response(200) # 200 OK
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running and awake.")

    def do_GET(self): self._send_response()
    def do_HEAD(self): self._send_response()
    def do_POST(self): self._send_response()
        
    def log_message(self, format, *args): 
        """HTTP serverning keraksiz loglarini o'chiradi."""
        return 

# --- SERVER BOSHQARUVI ---

def start_health_check_server():
    """HTTP serverni alohida thread'da ishga tushiradi."""
    global httpd
    server_address = ('0.0.0.0', PORT)
    try:
        httpd = HTTPServer(server_address, HealthCheckHandler)
        logger.info(f"🚀 Health Check Server 0.0.0.0:{PORT} portida ishga tushdi.")
        httpd.serve_forever()
    except Exception as e:
        logger.error(f"!!! KRITIK XATO: HTTP Serverni ishga tushirishda xato: {e}")


def stop_health_check_server(signum=None, frame=None):
    """SIGTERM signali kelganda serverni to'xtatadi."""
    global httpd, polling_task
    logger.warning("⚠️ SIGTERM signali qabul qilindi. Jarayonlar to'xtatilmoqda...")
    
    if httpd:
        # HTTP serverni to'xtatish (bloklamasligi uchun alohida thread)
        threading.Thread(target=httpd.shutdown).start()
        
    if polling_task:
        # Bot Pollingni bekor qilish
        polling_task.cancel()
        logger.info("Bot Polling bekor qilindi.")


async def run_bot_and_server(main_func):
    """Bot Pollingni va HTTP Health Check serverni birga boshqaradi."""
    global polling_task
    
    # SIGTERM handlerini o'rnatish
    signal.signal(signal.SIGTERM, stop_health_check_server)

    # 1. HTTP serverni alohida thread'da ishga tushirish
    server_thread = threading.Thread(target=start_health_check_server)
    server_thread.daemon = True 
    server_thread.start()
    
    # 2. HTTP server ishga tushishini kutish
    await asyncio.sleep(2) 
    
    # 3. Asosiy bot funksiyasini ishga tushirish
    logger.info("🤖 Telegram Polling boshlanmoqda...")
    polling_task = asyncio.create_task(main_func()) 
    
    try:
        await polling_task
    except asyncio.CancelledError:
        logger.info("✅ Bot Polling jarayoni muvaffaqiyatli to'xtatildi.")
    except Exception as e:
        logger.error(f"!!! KRITIK XATO: Bot Polling jarayonida kutilmagan xato: {e}")
        stop_health_check_server()


if __name__ == "__main__":
    try:
        # main.py dagi async def main() funksiyasini ishga tushiramiz
        asyncio.run(run_bot_and_server(bot_main_async_func))
        
    except Exception as e:
        logger.error(f"!!! ASOSIY XATO: Server ishga tushirishda xato: {e}")
