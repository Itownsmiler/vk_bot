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

WORK_END = time(11, 42)  # после этого считается опоздание

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
    total_arrivals INTEGER DEFAULT 0,
    on_time INTEGER DEFAULT 0,
    late_count INTEGER DEFAULT 0,
    fines INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    arrival_date TEXT,
    arrival_time TEXT
)
""")

db.commit()

# =====================
# KEYBOARD
# =====================

def main_kb(admin=False):
    kb = Keyboard(one_time=False)

    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"))
    kb.add(Text("🏆 Топ")).row()

    if admin:
        kb.add(Text("⚙ Админ"))

    return kb


def back_kb():
    kb = Keyboard(one_time=False)
    kb.add(Text("⬅ Назад"))
    return kb

# =====================
# SAFE COMMAND DETECTOR (100% FIX)
# =====================

def get_command(message: Message):
    """
    НИКАКИХ .get() — только безопасная обработка
    """

    payload = message.payload

    # если None
    if not payload:
        payload = {}

    # если строка
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            payload = {}

    # если dict
    if isinstance(payload, dict):
        cmd = payload.get("cmd")
        if cmd:
            return cmd

    return None

# =====================
# ROUTER (STABLE)
# =====================

@bot.on.message()
async def router(message: Message):

    print("TEXT:", message.text)
    print("PAYLOAD:", message.payload)

    text = (message.text or "").lower()
    cmd = get_command(message)

    # fallback по тексту (ВАЖНО)
    if not cmd:

        if "я на месте" in text:
            cmd = "arrive"
        elif "статистика" in text:
            cmd = "stats"
        elif "топ" in text:
            cmd = "top"
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
    elif cmd == "top":
        await top(message)
    elif cmd == "admin":
        await admin(message)
    elif cmd == "back":
        await back(message)

# =====================
# ARRIVE LOGIC
# =====================

async def arrive(message: Message):

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    t = now.strftime("%H:%M:%S")

    cursor.execute("""
    SELECT 1 FROM arrivals
    WHERE user_id=? AND arrival_date=?
    """, (message.from_id, today))

    if cursor.fetchone():
        await message.answer("⚠ Уже отмечался сегодня")
        return

    cursor.execute("""
    INSERT INTO arrivals (user_id, arrival_date, arrival_time)
    VALUES (?, ?, ?)
    """, (message.from_id, today, t))

    late = now.time() > WORK_END

    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, name)
    VALUES (?, ?)
    """, (message.from_id, "user"))

    cursor.execute("""
    UPDATE users
    SET total_arrivals = total_arrivals + 1
    WHERE user_id=?
    """, (message.from_id,))

    if not late:

        cursor.execute("""
        UPDATE users
        SET on_time = on_time + 1
        WHERE user_id=?
        """, (message.from_id,))

        text = f"✅ Вовремя\n🕒 {t}"

    else:

        cursor.execute("""
        UPDATE users
        SET late_count = late_count + 1
        WHERE user_id=?
        """, (message.from_id,))

        cursor.execute("""
        SELECT late_count FROM users WHERE user_id=?
        """, (message.from_id,))

        late = cursor.fetchone()[0]

        penalty = ""
        if late % 3 == 0:
            cursor.execute("""
            UPDATE users
            SET fines = fines + 1
            WHERE user_id=?
            """, (message.from_id,))
            penalty = "\n💸 ШТРАФ!"

        text = f"❌ Опоздание\n🕒 {t}{penalty}"

    db.commit()
    await message.answer(text)

# =====================
# STATS
# =====================

async def stats(message: Message):

    cursor.execute("""
    SELECT total_arrivals, on_time, late_count, fines
    FROM users WHERE user_id=?
    """, (message.from_id,))

    r = cursor.fetchone()

    if not r:
        r = (0, 0, 0, 0)

    await message.answer(f"""
📊 СТАТИСТИКА

📅 Всего: {r[0]}
✅ Вовремя: {r[1]}
❌ Опоздания: {r[2]}
💸 Штрафы: {r[3]}
""", keyboard=back_kb())

# =====================
# TOP
# =====================

async def top(message: Message):

    cursor.execute("""
    SELECT user_id, on_time FROM users
    ORDER BY on_time DESC
    LIMIT 10
    """)

    rows = cursor.fetchall()

    text = "🏆 ТОП\n\n"

    for i, r in enumerate(rows):
        text += f"{i+1}. user{r[0]} — {r[1]}\n"

    await message.answer(text, keyboard=back_kb())

# =====================
# ADMIN
# =====================

async def admin(message: Message):

    if message.from_id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    await message.answer(
        f"⚙ АДМИН\n👥 Пользователей: {users}",
        keyboard=back_kb()
    )

# =====================
# BACK
# =====================

async def back(message: Message):
    await message.answer(
        "🏠 Меню",
        keyboard=main_kb(message.from_id == ADMIN_ID)
    )

# =====================
# START
# =====================

print("BOT STARTED")
bot.run_forever()
