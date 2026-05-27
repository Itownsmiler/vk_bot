import sqlite3
import random
import json
from datetime import datetime, time

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, Text

# =====================
# CONFIG
# =====================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"
ADMIN_ID = 47965177

WORK_END = time(11, 42)

bot = Bot(token=TOKEN)

# =====================
# DB
# =====================

db = sqlite3.connect("workers.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    fines INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    arrival_date TEXT,
    arrival_time TEXT,
    arrival_month TEXT
)
""")

db.commit()

# =====================
# KEYBOARD
# =====================

def kb_main(admin=False):
    kb = Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"))
    kb.add(Text("🏆 Топ месяца")).row()

    if admin:
        kb.add(Text("⚙ Админ"))

    return kb

def kb_back():
    kb = Keyboard(one_time=False)
    kb.add(Text("⬅ Назад"))
    return kb

# =====================
# SAFE CMD
# =====================

def get_cmd(message: Message):
    payload = message.payload

    if not payload:
        return None

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            return None

    if isinstance(payload, dict):
        return payload.get("cmd")

    return None

# =====================
# ROUTER
# =====================

@bot.on.message()
async def router(message: Message):

    print("TEXT:", message.text)
    print("PAYLOAD:", message.payload)

    cmd = get_cmd(message)
    text = (message.text or "").lower()

    if not cmd:
        if "я на месте" in text:
            cmd = "arrive"
        elif "статистика" in text:
            cmd = "stats"
        elif "топ" in text:
            cmd = "top"
        elif "топ месяц" in text:
            cmd = "top_month"
        elif "админ" in text:
            cmd = "admin"
        elif "назад" in text:
            cmd = "back"

    if not cmd:
        return

    if cmd == "arrive":
        await arrive(message)
    elif cmd == "stats":
        await stats(message)
    elif cmd == "top_month":
        await top_month(message)
    elif cmd == "admin":
        await admin(message)
    elif cmd == "back":
        await back(message)

# =====================
# ARRIVE (MONTH FIX)
# =====================

async def arrive(message: Message):

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    t = now.strftime("%H:%M:%S")

    cursor.execute("""
    SELECT 1 FROM arrivals
    WHERE user_id=? AND arrival_date=?
    """, (message.from_id, today))

    if cursor.fetchone():
        await message.answer("⚠ Уже отмечался")
        return

    cursor.execute("""
    INSERT INTO users (user_id, name)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO NOTHING
    """, (message.from_id, "user"))

    cursor.execute("""
    INSERT INTO arrivals (user_id, arrival_date, arrival_time, arrival_month)
    VALUES (?, ?, ?, ?)
    """, (message.from_id, today, t, month))

    late = now.time() > WORK_END

    if not late:
        text = f"✅ Вовремя\n🕒 {t}"
    else:
        text = f"❌ Опоздание\n🕒 {t}"

        cursor.execute("""
        UPDATE users SET fines = fines + 1 WHERE user_id=?
        """, (message.from_id,))

    db.commit()
    await message.answer(text)

# =====================
# STATS (MONTH)
# =====================

async def stats(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*)
    FROM arrivals
    WHERE user_id=? AND arrival_month=?
    """, (message.from_id, month))

    total = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*)
    FROM arrivals
    WHERE user_id=? AND arrival_month=? AND arrival_time <= ?
    """, (message.from_id, month, "11:42:00"))

    on_time = cursor.fetchone()[0]

    cursor.execute("""
    SELECT fines FROM users WHERE user_id=?
    """, (message.from_id,))

    fines = cursor.fetchone()
    fines = fines[0] if fines else 0

    await message.answer(f"""
📊 СТАТИСТИКА ({month})

📅 Всего: {total}
✅ Вовремя: {on_time}
💸 Штрафы: {fines}
""", keyboard=kb_back())

# =====================
# TOP MONTH
# =====================

async def top_month(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT user_id, COUNT(*) as cnt
    FROM arrivals
    WHERE arrival_month=?
    GROUP BY user_id
    ORDER BY cnt DESC
    LIMIT 10
    """, (month,))

    rows = cursor.fetchall()

    text = f"🏆 ТОП МЕСЯЦА ({month})\n\n"

    for i, r in enumerate(rows):
        text += f"{i+1}. user{r[0]} — {r[1]} приходов\n"

    await message.answer(text, keyboard=kb_back())

# =====================
# ADMIN
# =====================

async def admin(message: Message):

    if message.from_id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM arrivals")
    all_time = cursor.fetchone()[0]

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*) FROM arrivals WHERE arrival_month=?
    """, (month,))

    this_month = cursor.fetchone()[0]

    await message.answer(f"""
⚙ АДМИН

📊 Всего: {all_time}
📅 Этот месяц: {this_month}
""", keyboard=kb_back())

# =====================
# BACK
# =====================

async def back(message: Message):
    await message.answer(
        "🏠 Меню",
        keyboard=kb_main(message.from_id == ADMIN_ID)
    )

# =====================
# RUN
# =====================

print("BOT STARTED")
bot.run_forever()
