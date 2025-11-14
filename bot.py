from aiogram import Bot, Dispatcher, types, executor
import sqlite3
import uuid
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# ===== Налаштування =====
BOT_TOKEN = "8229120396:AAFgq8WzvzcpStdA3LykV8Rq6n1BL7AjdzU"
ADMIN_ID = 8325355827
DB_FILE = "gifts.db"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ===== Стани =====
class GiftStates(StatesGroup):
    waiting_gift = State()
    waiting_price = State()

# ===== Ініціалізація БД =====
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sales (
        id TEXT PRIMARY KEY,
        seller_id INTEGER,
        gift_message_id INTEGER,
        gift_chat_id INTEGER,
        price INTEGER,
        status TEXT,
        buyer_id INTEGER
    )
    """)
    conn.commit()
    conn.close()

def add_sale(sale_id, seller_id, gift_chat_id, gift_message_id, price):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sale_id, seller_id, gift_chat_id, gift_message_id, price, "waiting_sale", None))
    conn.commit()
    conn.close()

def update_status(sale_id, status):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE sales SET status=? WHERE id=?", (status, sale_id))
    conn.commit()
    conn.close()

def set_buyer(sale_id, buyer_id):
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("UPDATE sales SET buyer_id=?, status=? WHERE id=?", (buyer_id, "sold", sale_id))
    conn.commit()
    conn.close()

def get_active_sales():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT id, gift_message_id, gift_chat_id, price, status FROM sales WHERE status='waiting_sale' OR status='in_market'")
    data = cur.fetchall()
    conn.close()
    return data

# ===== Handlers =====
@dp.message_handler(commands=["start"])
async def start(m: types.Message):
    await m.answer("👋 Привіт!\nКоманди:\n/sell — виставити Gift на продаж\n/buy — купити Gift\n/my — мої лоти")

@dp.message_handler(commands=["sell"])
async def sell(m: types.Message):
    await m.answer("Будь ласка, надішліть свій Telegram Gift/NFT як повідомлення боту:")
    await GiftStates.waiting_gift.set()

@dp.message_handler(content_types=types.ContentType.ANY, state=GiftStates.waiting_gift)
async def receive_gift(m: types.Message, state: FSMContext):
    # Зберігаємо chat_id і message_id, щоб контролювати Gift
    async with state.proxy() as data:
        data['gift_chat_id'] = m.chat.id
        data['gift_message_id'] = m.message_id

    await m.answer("Тепер введи ціну в зірках за цей Gift:")
    await GiftStates.waiting_price.set()

@dp.message_handler(state=GiftStates.waiting_price)
async def set_gift_price(m: types.Message, state: FSMContext):
    try:
        price = int(m.text.strip())
    except ValueError:
        await m.answer("Будь ласка, введи число для ціни.")
        return

    async with state.proxy() as data:
        gift_chat_id = data['gift_chat_id']
        gift_message_id = data['gift_message_id']

    sale_id = str(uuid.uuid4())[:8]
    seller_id = m.from_user.id

    # Додаємо лот у базу
    add_sale(sale_id, seller_id, gift_chat_id, gift_message_id, price)

    # Тут логіка: Gift і зірки переходять на твій акаунт (ADMIN_ID)
    await m.answer(f"✅ Лот створено! ID: {sale_id}\nGift і зірки переходять на твій акаунт для контролю (ID: {ADMIN_ID}).\nЛот доступний для покупців через /buy")

    # Пересилаємо Gift на твій акаунт
    try:
        await bot.forward_message(chat_id=ADMIN_ID, from_chat_id=gift_chat_id, message_id=gift_message_id)
    except Exception as e:
        await m.answer(f"❌ Не вдалося переслати Gift на твій акаунт: {e}")

    await state.finish()

@dp.message_handler(commands=["buy"])
async def buy(m: types.Message):
    parts = m.text.split()
    if len(parts) == 1:
        active = [f"{s[0]} — {s[4]} зірок" for s in get_active_sales()]
        if not active:
            await m.answer("Немає доступних лотів 😢")
        else:
            await m.answer("📋 Доступні лоти:\n" + "\n".join(active))
        return

    sale_id = parts[1]
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT * FROM sales WHERE id=?", (sale_id,))
    sale = cur.fetchone()
    conn.close()
    if not sale:
        await m.answer("❌ Лот не знайдено.")
        return

    buyer_id = m.from_user.id
    set_buyer(sale_id, buyer_id)

    # Пересилаємо Gift покупцю з акаунту ADMIN_ID
    gift_chat_id, gift_message_id = sale[3], sale[2]
    try:
        await bot.forward_message(chat_id=buyer_id, from_chat_id=gift_chat_id, message_id=gift_message_id)
        await m.answer(f"✅ Ви купили Gift! Він надісланий вам від контролюючого акаунту.")
    except Exception as e:
        await m.answer(f"❌ Не вдалося переслати Gift: {e}")

# ===== Start =====
if name == "__main__":
    init_db()
    executor.start_polling(dp, skip_updates=True)
