# db.py
import os
import psycopg2
from psycopg2 import sql
from typing import List, Dict, Tuple, Optional

# Muhit o'zgaruvchilarini yuklaymiz (Render/OS dan)
DATABASE_URL: Optional[str] = os.getenv("DATABASE_URL")

# --- 1. DB Ulanish Funksiyasi ---
def get_db_connection():
    """PostgreSQL bazasiga ulanish obyektini qaytaradi (Xatolarni loglarga chiqaradi)."""
    if not DATABASE_URL:
        print("!!! XATO: DATABASE_URL muhit o'zgaruvchisi o'rnatilmagan.")
        return None
    try:
        conn = psycopg2.connect(DATABASE_URL)
        # print("✅ DB Ulanish muvaffaqiyatli.") # Logni kamaytirish uchun olib tashladik
        return conn
    except Exception as e:
        # Xatoni aniqroq qilib loglarga chiqaramiz
        print(f"❌ DATABASE XATOSI: PostgreSQLga ulanishda kutilmagan xato: {e}") 
        return None

# --- 2. Baza Tuzilmalarini Yaratish ---
def create_tables():
    """Loyiha uchun kerakli barcha jadvallarni (tables) yaratadi."""
    conn = get_db_connection()
    if not conn: 
        print("❌ Jadvallarni yaratish mumkin emas: DB ulanish xatosi.")
        return

    cur = conn.cursor()
    try:
        # 1. Sotuvchilar Jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS sellers (
                id SERIAL PRIMARY KEY,
                chat_id BIGINT UNIQUE,
                ism VARCHAR(100) NOT NULL,
                mahalla VARCHAR(100),
                telefon VARCHAR(55),
                parol VARCHAR(50) UNIQUE NOT NULL,
                rol VARCHAR(10) DEFAULT 'sotuvchi'
            );
        """)

        # 2. Mahsulotlar Jadvali
        cur.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                mahsulot_nomi VARCHAR(100) UNIQUE NOT NULL,
                narxi NUMERIC(10, 2) NOT NULL
            );
        """)

        # 3. Tovarlar Inventarizatsiyasi
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory (
                id SERIAL PRIMARY KEY,
                seller_id INTEGER REFERENCES sellers(id) ON DELETE CASCADE,
                product_id INTEGER REFERENCES products(id),
                soni INTEGER NOT NULL,
                jami_narxi NUMERIC(10, 2) NOT NULL,
                sana TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        conn.commit()
        print("✅ PostgreSQL jadvallari yaratildi yoki allaqachon mavjud.")
    except Exception as e:
        print(f"❌ Jadvallarni yaratishda xato: {e}")
    finally:
        cur.close()
        conn.close()

# --- 3. CRUD: Foydalanuvchi va ID Funksiyalari ---

def get_user_role(chat_id: int) -> str:
    """Chat ID bo'yicha foydalanuvchi rolini aniqlaydi."""
    conn = get_db_connection()
    if not conn: return 'none'
    cur = conn.cursor()
    try:
        cur.execute("SELECT rol FROM sellers WHERE chat_id = %s", (chat_id,))
        result = cur.fetchone()
        return result[0] if result else 'none'
    except Exception as e:
        print(f"❌ Rolni olishda xato: {e}")
        return 'none'
    finally:
        cur.close()
        conn.close()
        
def get_seller_id_by_chat_id(chat_id: int) -> Optional[int]:
    """Chat ID orqali sotuvchi ID'sini oladi."""
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM sellers WHERE chat_id = %s", (chat_id,))
        result = cur.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"❌ Sotuvchi ID'sini olishda xato: {e}")
        return None
    finally:
        cur.close()
        conn.close()

# --- 4. CRUD: Mahsulotlar Bo'limi Funksiyalari ---

def add_new_product(product_name: str, price: float) -> bool:
    """Yangi mahsulotni bazaga qo'shadi."""
    conn = get_db_connection()
    if not conn: return False
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO products (mahsulot_nomi, narxi) VALUES (%s, %s) ON CONFLICT (mahsulot_nomi) DO NOTHING;",
            (product_name, price)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Mahsulot kiritishda xato: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_all_products() -> List[Dict]:
    """Barcha mahsulotlar nomini va narxini bazadan oladi."""
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()
    products = []
    try:
        cur.execute(
            "SELECT id, mahsulot_nomi, narxi FROM products ORDER BY mahsulot_nomi ASC"
        )
        results = cur.fetchall()
        for id, name, price in results:
            products.append({'id': id, 'nomi': name, 'narxi': float(price)})
        return products
    except Exception as e:
        print(f"❌ Mahsulotlarni olishda xato: {e}")
        return []
    finally:
        cur.close()
        conn.close()

# --- 5. CRUD: Sotuvchilar Bo'limi Funksiyalari ---

def add_new_seller(ism: str, mahalla: str, telefon: str, parol: str) -> bool:
    """Yangi sotuvchini bazaga qo'shadi."""
    conn = get_db_connection()
    if not conn: return False
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO sellers (ism, mahalla, telefon, parol, rol) VALUES (%s, %s, %s, %s, 'sotuvchi')",
            (ism, mahalla, telefon, parol)
        )
        conn.commit()
        return True
    except psycopg2.errors.UniqueViolation:
        print("❌ Xato: Parol allaqachon mavjud.")
        return False
    except Exception as e:
        print(f"❌ Sotuvchi kiritishda xato: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_seller_by_password(password: str) -> Optional[Dict]:
    """Parol orqali sotuvchini topadi."""
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, ism, chat_id, parol FROM sellers WHERE parol = %s", (password,)
        )
        seller_data = cur.fetchone()
        if seller_data:
            return {'id': seller_data[0], 'ism': seller_data[1], 'chat_id': seller_data[2], 'parol': seller_data[3]}
        return None
    except Exception as e:
        print(f"❌ Parol tekshiruvida xato: {e}")
        return None
    finally:
        cur.close()
        conn.close()

def update_seller_chat_id(seller_id: int, chat_id: int) -> bool:
    """Sotuvchining chat_id'sini ro'yxatdan o'tkazadi."""
    conn = get_db_connection()
    if not conn: return False
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE sellers SET chat_id = %s WHERE id = %s AND (chat_id IS NULL OR chat_id != %s)",
            (chat_id, seller_id, chat_id)
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as e:
        print(f"❌ Chat ID yangilanishida xato: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def get_all_sellers() -> List[Dict]:
    """Barcha sotuvchilarni ism bo'yicha alfavit tartibida oladi."""
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()
    sellers = []
    try:
        cur.execute(
            "SELECT id, ism, mahalla, telefon FROM sellers ORDER BY ism ASC"
        )
        results = cur.fetchall()
        for id, ism, mahalla, telefon in results:
            sellers.append({
                'id': id,
                'ism': ism,
                'mahalla': mahalla,
                'telefon': telefon
            })
        return sellers
    except Exception as e:
        print(f"❌ Sotuvchilarni olishda xato: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_all_seller_passwords() -> List[Dict]:
    """Barcha sotuvchilar ismlari va parollarini oladi."""
    conn = get_db_connection()
    if not conn: return []
    cur = conn.cursor()
    passwords = []
    try:
        cur.execute(
            "SELECT ism, parol FROM sellers ORDER BY ism ASC"
        )
        results = cur.fetchall()
        for ism, parol in results:
            passwords.append({'ism': ism, 'parol': parol})
        return passwords
    except Exception as e:
        print(f"❌ Sotuvchi parollarini olishda xato: {e}")
        return []
    finally:
        cur.close()
        conn.close()

def get_seller_password_by_id(seller_id: int) -> Optional[str]:
    """Sotuvchi ID'si orqali parolni oladi."""
    conn = get_db_connection()
    if not conn: return None
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT parol FROM sellers WHERE id = %s", (seller_id,)
        )
        result = cur.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"❌ Parolni olishda xato: {e}")
        return None
    finally:
        cur.close()
        conn.close()

# --- 6. CRUD: Yangi Tovar Berish (Inventory) ---
def add_inventory(seller_id: int, product_id: int, count: int) -> Tuple[bool, str, float]:
    """Sotuvchiga yangi tovar kiritadi va jami narxni qaytaradi."""
    conn = get_db_connection()
    if not conn: return False, "DB ulanish xatosi", 0.0
    cur = conn.cursor()
    
    try:
        # 1. Mahsulotning birlik narxini olish
        cur.execute("SELECT narxi, mahsulot_nomi FROM products WHERE id = %s", (product_id,))
        product_info = cur.fetchone()
        
        if not product_info:
            return False, "Mahsulot topilmadi.", 0.0

        unit_price = float(product_info[0])
        product_name = product_info[1]
        total_price = unit_price * count

        # 2. Inventory jadvaliga kiritish
        cur.execute(
            """
            INSERT INTO inventory (seller_id, product_id, soni, jami_narxi) 
            VALUES (%s, %s, %s, %s);
            """,
            (seller_id, product_id, count, total_price)
        )
        
        conn.commit()
        return True, product_name, total_price
    except Exception as e:
        print(f"❌ Inventory kiritishda xato: {e}")
        return False, str(e), 0.0
    finally:
        cur.close()
        conn.close()

# --- 7. CRUD: Qarzdorlikni Olish ---
def get_seller_debt_details(seller_id: int) -> Tuple[float, List[Dict]]:
    """
    Berilgan sotuvchi ID bo'yicha olgan barcha tovarlar ro'yxatini va jami qarzdorlikni hisoblaydi.
    """
    conn = get_db_connection()
    if not conn: return 0.0, []
    cur = conn.cursor()
    
    total_debt = 0.0
    inventory_items = []

    try:
        # 1. Jami qarzdorlikni hisoblash
        cur.execute(
            "SELECT SUM(jami_narxi) FROM inventory WHERE seller_id = %s", (seller_id,)
        )
        result_debt = cur.fetchone()
        if result_debt and result_debt[0] is not None:
            total_debt = float(result_debt[0])

        # 2. Tovarlar ro'yxatini (inventarizatsiyani) olish
        cur.execute(
            """
            SELECT 
                p.mahsulot_nomi, 
                i.soni, 
                i.jami_narxi, 
                i.sana 
            FROM inventory i
            JOIN products p ON i.product_id = p.id
            WHERE i.seller_id = %s
            ORDER BY i.sana DESC;
            """,
            (seller_id,)
        )
        results = cur.fetchall()
        
        for name, count, total_price, date in results:
            inventory_items.append({
                'mahsulot_nomi': name,
                'soni': count,
                'jami_narxi': float(total_price),
                # Vaqtni formatlash
                'sana': date.strftime("%Y-%m-%d %H:%M") 
            })
            
        return total_debt, inventory_items
        
    except Exception as e:
        print(f"❌ Qarzdorlikni olishda xato: {e}")
        return 0.0, []
    finally:
        cur.close()
        conn.close()
