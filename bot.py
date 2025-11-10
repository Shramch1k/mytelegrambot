from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
import asyncio, uuid, urllib.parse, sqlite3, requests

# ==== Налаштування ====
BOT_TOKEN = "8229120396:AAFgq8WzvzcpStdA3LykV8Rq6n1BL7AjdzU"
ESCROW_ADDRESS = "UQCGxGw37OFxqzjt78ExcihhD27PWoqS6nVDiG2nD-gaOfqy"
ADMIN_ID = 8325355827
TON_API_URL = "https://tonapi.io/v2/blockchain/accounts"
# =======================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# =============== DATABASE ===============
DB_FILE = "sales.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        seller_addr TEXT,
        nft_addr TEXT,
        price REAL,
        status TEXT,
        buyer_addr TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_sale(id, seller_addr, nft_addr, price):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?)",
                (id, seller_addr, nft_addr, price, "waiting_nft", None))
    conn.commit()
    conn.close()

def update_status(id, status):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE sales SET status=? WHERE id=?", (status, id))
    conn.commit()
    conn.close()

def set_buyer(id, buyer_addr):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE sales SET buyer_addr=? WHERE id=?", (buyer_addr, id))
    conn.commit()
    conn.close()

def get_sale(id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales WHERE id=?", (id,))
    sale = cur.fetchone()
    conn.close()
    return sale

def get_active_sales():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, nft_addr, price, status FROM sales")
    data = cur.fetchall()
    conn.close()
    return data

# =============== HELPERS ===============
def ton_payment_link(to_addr, amount, text):
    params = {"amount": amount, "text": text}
    return f"ton://transfer/{to_addr}?" + urllib.parse.urlencode(params)

def ton_nft_transfer_link(to_addr, nft_addr, memo):
    payload = f"NFT:{nft_addr}:{memo}"
    params = {"text": payload}
    return f"ton://transfer/{to_addr}?" + urllib.parse.urlencode(params)

def check_balance(addr):
    try:
        r = requests.get(f"{TON_API_URL}/{addr}")
        if r.status_code == 200:
            data = r.json()
            balance = data.get("balance", 0) / 1e9
            return round(balance, 4)
    except:
        pass
    return None

# =============== HANDLERS ===============
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("👋 Привіт!\n"
                   "Команди:\n"
                   "/sell — виставити NFT\n"
                   "/buy — купити NFT\n"
                   "/my — мої угоди")

@dp.message_handler(commands=["sell"])
async def sell(m: types.Message):
    await m.answer("Надішли адресу свого TON-гаманця (починається з EQ...).")

@dp.message_handler(lambda m: m.text and m.text.startswith("EQ") and len(m.text) > 40)
async def seller_addr(m: types.Message):
    sale_id = str(uuid.uuid4())[:8]
    seller_addr = m.text.strip()
    nft_addr = "EQ_FAKE_NFT_EXAMPLE"
    price = 10.0

    add_sale(sale_id, seller_addr, nft_addr, price)

    link = ton_nft_transfer_link(ESCROW_ADDRESS, nft_addr, sale_id)
    await m.answer(f"✅ Продаж створено (ID: {sale_id})\n"
                   f"NFT: {nft_addr}\n"
                   f"Ціна: {price} TON\n\n"
                   f"🔹 Передай NFT на ескроу-гаманець:\n{link}\n\n"
                   f"Після переказу напиши /confirm_nft {sale_id}")

@dp.message_handler(commands=["confirm_nft"])
async def confirm_nft(m: types.Message):
    parts = m.text.split()
    if len(parts) < 2:
        await m.answer("⚠️ Використай: /confirm_nft <sale_id>")
        return

    sale_id = parts[1]
    sale = get_sale(sale_id)
    if not sale:
        await m.answer("❌ Такого лота не існує.")
        return

    update_status(sale_id, "nft_in_escrow")
    await m.answer(f"✅ NFT отримано в ескроу!\nТепер покупець може купити NFT через /buy {sale_id}")

@dp.message_handler(commands=["buy"])
async def buy(m: types.Message):
    parts = m.text.split()
    if len(parts) == 1:
        active = [f"{s[0]} — {s[2]} TON ({s[3]})" for s in get_active_sales() if s[3] == "nft_in_escrow"]
        if not active:
            await m.answer("Немає активних лотів 😢")
        else:
            await m.answer("📋 Доступні лоти:\n" + "\n".join(active))
        return

    sale_id = parts[1]
    sale = get_sale(sale_id)
    if not sale:
        await m.answer("❌ Лот не знайдено.")
        return

    buyer_addr = m.from_user.id  # приклад, можна змінити
    set_buyer(sale_id, buyer_addr)
    update_status(sale_id, "sold")
    await m.answer(f"✅ Ви купили NFT {sale_id}!")

# =============== START BOT ===============
if __name__ == "__main__":
    init_db()
    executor.start_polling(dp, skip_updates=True)