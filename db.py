# db.py
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# --- Konfiguratsiya ---
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    print("!!! KRITIK XATO: DATABASE_URL muhit o'zgaruvchisi topilmadi.", file=sys.stderr)
    # sys.exit(1) # Renderda bu botni butunlay to'xtatishi mumkin, shuning uchun kommentariyada qoldiramiz

# --- DB Ulanish Funksiyasi ---
def get_db_connection():
    """PostgreSQL bazasiga ulanishni yaratadi."""
    try:
        conn = psycopg2.connect(DATABASE_URL)
        return conn
    except Exception as e:
        print(f"!!! KRITIK XATO (DB): Bazaga ulanishda xato: {e}", file=sys.stderr)
        return None

# --- Jadvallarni Yaratish Funksiyasi ---
def create_tables():
    """Bot uchun kerakli PostgreSQL jadvallarini yaratadi."""
    conn = get_db_connection()
    if not conn:
        print("!!! KRITIK XATO (DB): Jadvallarni yaratish uchun bazaga ulanib bo'lmadi.", file=sys.stderr)
        return

    try:
        cursor = conn.cursor()
        
        # 1. products
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                nomi VARCHAR(255) UNIQUE NOT NULL,
                narxi DECIMAL(10, 2) NOT NULL
            );
        """)
        
        # 2. sellers
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sellers (
                id SERIAL PRIMARY KEY,
                ism VARCHAR(255) NOT NULL,
                mahalla VARCHAR(255),
                telefon VARCHAR(50),
                parol VARCHAR(50) UNIQUE NOT NULL,
                chat_id BIGINT UNIQUE
            );
        """)

        # 3. inventory
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                seller_id INTEGER REFERENCES sellers(id),
                product_id INTEGER REFERENCES products(id),
                soni INTEGER NOT NULL,
                narxi DECIMAL(10, 2) NOT NULL,
                sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
    except Exception as e:
        print(f"!!! KRITIK XATO (DB): Jadvallarni yaratishda xato: {e}", file=sys.stderr)
        conn.rollback()
    finally:
        if conn:
            conn.close()

# --- Funksiyalar (Sotuvchilar/Rollar) ---

def get_user_role(chat_id: int) -> str:
    """Foydalanuvchining chat_id orqali sotuvchi ekanligini tekshiradi."""
    conn = None
    try:
        conn = get_db_connection()
        if not conn:
            print(f"DB Log: Ulanish yo'q. get_user_role xato", file=sys.stderr)
            return 'not_registered'

        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT ism FROM sellers WHERE chat_id = %s", (chat_id,))
        seller = cursor.fetchone()

        print(f"DB Log: Rol so'rovi bajarildi. Chat ID: {chat_id}, Natija: {seller}")
        
        if seller:
            return 'sotuvchi'
        else:
            return 'not_registered'
            
    except Exception as e:
        print(f"!!! KRITIK XATO (DB): get_user_role funksiyasida xato: {e}", file=sys.stderr)
        return 'not_registered' 

    finally:
        if conn: conn.close()
        
# Qolgan barcha db funksiyalari (get_seller_by_password, update_seller_chat_id, add_new_product, get_all_products, va boshqalar...)
# Avvalgi versiyadagi barcha boshqa funksiyalarni bu yerga qo'shish kerak.

def get_seller_by_password(password: str) -> dict or None:
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, ism, parol FROM sellers WHERE parol = %s", (password,))
        return cursor.fetchone()
    except Exception as e:
        print(f"DB Xato: get_seller_by_password: {e}", file=sys.stderr)
        return None
    finally:
        if conn: conn.close()

def update_seller_chat_id(seller_id: int, chat_id: int) -> bool:
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE sellers SET chat_id = %s WHERE id = %s", (chat_id, seller_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"DB Xato: update_seller_chat_id: {e}", file=sys.stderr)
        conn.rollback()
        return False
    finally:
        if conn: conn.close()
        
def get_seller_id_by_chat_id(chat_id: int) -> int or None:
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id FROM sellers WHERE chat_id = %s", (chat_id,))
        result = cursor.fetchone()
        return result['id'] if result else None
    except Exception as e:
        print(f"DB Xato: get_seller_id_by_chat_id: {e}", file=sys.stderr)
        return None
    finally:
        if conn: conn.close()

def add_new_product(nomi: str, narxi: float) -> bool:
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO products (nomi, narxi) VALUES (%s, %s)", (nomi, narxi))
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    except Exception as e:
        print(f"DB Xato: add_new_product: {e}", file=sys.stderr)
        conn.rollback()
        return False
    finally:
        if conn: conn.close()

def get_all_products() -> list:
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, nomi, narxi FROM products ORDER BY nomi")
        return cursor.fetchall()
    except Exception as e:
        print(f"DB Xato: get_all_products: {e}", file=sys.stderr)
        return []
    finally:
        if conn: conn.close()

def add_new_seller(ism: str, mahalla: str, telefon: str, parol: str) -> bool:
    conn = get_db_connection()
    if not conn: return False
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sellers (ism, mahalla, telefon, parol) VALUES (%s, %s, %s, %s)",
            (ism, mahalla, telefon, parol)
        )
        conn.commit()
        return True
    except psycopg2.IntegrityError:
        conn.rollback()
        return False
    except Exception as e:
        print(f"DB Xato: add_new_seller: {e}", file=sys.stderr)
        conn.rollback()
        return False
    finally:
        if conn: conn.close()

def get_all_sellers() -> list:
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT id, ism, mahalla, telefon, chat_id FROM sellers ORDER BY ism")
        return cursor.fetchall()
    except Exception as e:
        print(f"DB Xato: get_all_sellers: {e}", file=sys.stderr)
        return []
    finally:
        if conn: conn.close()

def get_all_seller_passwords() -> list:
    conn = get_db_connection()
    if not conn: return []
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT ism, parol FROM sellers ORDER BY ism")
        return cursor.fetchall()
    except Exception as e:
        print(f"DB Xato: get_all_seller_passwords: {e}", file=sys.stderr)
        return []
    finally:
        if conn: conn.close()

def get_seller_password_by_id(seller_id: int) -> str or None:
    conn = get_db_connection()
    if not conn: return None
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT parol FROM sellers WHERE id = %s", (seller_id,))
        result = cursor.fetchone()
        return result['parol'] if result else None
    except Exception as e:
        print(f"DB Xato: get_seller_password_by_id: {e}", file=sys.stderr)
        return None
    finally:
        if conn: conn.close()

def add_inventory(seller_id: int, product_id: int, count: int) -> tuple[bool, str, float]:
    conn = get_db_connection()
    if not conn: return False, "DB ulanish xatosi", 0.0

    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT nomi, narxi FROM products WHERE id = %s", (product_id,))
        product_data = cursor.fetchone()
        
        if not product_data:
            return False, "Mahsulot bazada topilmadi", 0.0
            
        product_name = product_data['nomi']
        unit_price = float(product_data['narxi'])
        total_price = unit_price * count

        cursor.execute(
            "INSERT INTO inventory (seller_id, product_id, soni, narxi) VALUES (%s, %s, %s, %s)",
            (seller_id, product_id, count, total_price)
        )
        
        conn.commit()
        return True, product_name, total_price
    except Exception as e:
        print(f"DB Xato: add_inventory: {e}", file=sys.stderr)
        conn.rollback()
        return False, f"Ichki xato: {e}", 0.0
    finally:
        if conn: conn.close()

def get_seller_debt_details(seller_id: int) -> tuple[float, list]:
    conn = get_db_connection()
    if not conn: return 0.0, []
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT 
                i.soni, 
                i.narxi AS jami_narxi, 
                TO_CHAR(i.sana, 'YYYY-MM-DD HH24:MI') AS sana, 
                p.nomi AS mahsulot_nomi
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            WHERE i.seller_id = %s
            ORDER BY i.sana DESC;
        """, (seller_id,))
        items = cursor.fetchall()
        
        total_debt = sum(float(item['jami_narxi']) for item in items)
        
        return total_debt, items
    except Exception as e:
        print(f"DB Xato: get_seller_debt_details: {e}", file=sys.stderr)
        return 0.0, []
    finally:
        if conn: conn.close()

if __name__ == '__main__':
    create_tables()
