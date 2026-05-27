import sqlite3
import random
from datetime import datetime, time

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

# =====================
# CONFIG
# =====================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"
ADMIN_ID = 47965177

LATE_TIME = time(11, 42)

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
    streak INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    fines INTEGER DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    name TEXT,
    arrival_time TEXT,
    arrival_date TEXT
)
""")

db.commit()

# =====================
# TEXTS
# =====================

GOOD = ["🔥 Отлично!", "💪 Молодец!", "🚀 Красавчик!"]
LATE = ["😴 Опоздал", "⌛ Поздно", "⚠ Дисциплина"]

# =====================
# LEVEL
# =====================

def add_xp(user_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    if not row:
        return

    xp, level = row
    xp += amount

    if xp >= level * 100:
        xp = 0
        level += 1

    cursor.execute("""
    UPDATE users SET xp=?, level=? WHERE user_id=?
    """, (xp, level, user_id))

# =====================
# KEYBOARD (VK SAFE)
# =====================

def kb_main(admin=False):
    kb = Keyboard(one_time=False)

    kb.add(Text("🟢 Я на месте", payload={"cmd": "arrive"})).row()

    kb.add(Text("📊 Статистика", payload={"cmd": "stats"}))
    kb.add(Text("🏆 Топ", payload={"cmd": "top"})).row()

    kb.add(Text("📈 Уровень", payload={"cmd": "level"}))

    if admin:
        kb.row()
        kb.add(Text("⚙ Админ", payload={"cmd": "admin"}))

    return kb


def kb_back():
    kb = Keyboard(one_time=False)
    kb.add(Text("⬅ Назад", payload={"cmd": "back"}))
    return kb

# =====================
# SAFE ROUTER (FIXED)
# =====================

@bot.on.message()
async def router(message: Message):

    print("TEXT:", message.text)
    print("PAYLOAD:", message.payload)

    payload = message.payload or {}
    cmd = payload.get("cmd")

    text = (message.text or "").lower()

    # 🔥 FALLBACK если VK не дал payload
    if not cmd:
        if "я на месте" in text:
            cmd = "arrive"
        elif "статистика" in text:
            cmd = "stats"
        elif "топ" in text:
            cmd = "top"
        elif "уровень" in text:
            cmd = "level"
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

    elif cmd == "level":
        await level(message)

    elif cmd == "admin":
        await admin(message)

    elif cmd == "back":
        await back(message)

# =====================
# ARRIVE
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
        await message.answer("⚠ Уже отмечался")
        return

    cursor.execute("""
    INSERT INTO arrivals (user_id, name, arrival_time, arrival_date)
    VALUES (?, ?, ?, ?)
    """, (message.from_id, "User", t, today))

    late = now.time() >= LATE_TIME

    cursor.execute("""
    UPDATE users
    SET total_arrivals = total_arrivals + 1
    WHERE user_id=?
    """, (message.from_id,))

    if not late:

        cursor.execute("""
        UPDATE users
        SET on_time = on_time + 1,
            streak = streak + 1
        WHERE user_id=?
        """, (message.from_id,))

        add_xp(message.from_id, 10)

        text = f"✅ {random.choice(GOOD)}\n🕒 {t}\n🟢 Вовремя"

    else:

        cursor.execute("""
        UPDATE users
        SET late_count = late_count + 1,
            streak = 0
        WHERE user_id=?
        """, (message.from_id,))

        cursor.execute("""
        SELECT late_count FROM users WHERE user_id=?
        """, (message.from_id,))

        late_count = cursor.fetchone()[0]

        penalty = ""
        if late_count % 3 == 0:
            cursor.execute("""
            UPDATE users
            SET fines = fines + 1
            WHERE user_id=?
            """, (message.from_id,))
            penalty = "\n💸 ШТРАФ!"

        add_xp(message.from_id, 3)

        text = f"❌ {random.choice(LATE)}\n🕒 {t}\n🔴 Опоздание{penalty}"

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

    await message.answer(f"""
📊 СТАТИСТИКА

📅 {r[0] if r else 0}
✅ {r[1] if r else 0}
❌ {r[2] if r else 0}
💸 {r[3] if r else 0}
""", keyboard=kb_back())

# =====================
# TOP
# =====================

async def top(message: Message):

    cursor.execute("""
    SELECT name, on_time FROM users
    ORDER BY on_time DESC
    LIMIT 10
    """)

    rows = cursor.fetchall()

    text = "🏆 ТОП\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, r in enumerate(rows):
        text += f"{medals[i] if i < 3 else '👤'} {r[0]} — {r[1]}\n"

    await message.answer(text, keyboard=kb_back())

# =====================
# LEVEL
# =====================

async def level(message: Message):

    cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (message.from_id,))
    r = cursor.fetchone()

    await message.answer(
        f"📈 LEVEL {r[1] if r else 1}\n⭐ XP {r[0] if r else 0}",
        keyboard=kb_back()
    )

# =====================
# ADMIN
# =====================

async def admin(message: Message):

    if message.from_id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    await message.answer(f"⚙ USERS: {users}", keyboard=kb_back())

# =====================
# BACK
# =====================

async def back(message: Message):
    await message.answer(
        "🏠 MENU",
        keyboard=kb_main(message.from_id == ADMIN_ID)
    )

# =====================
# RUN
# =====================

print("BOT STARTED")
bot.run_forever()
