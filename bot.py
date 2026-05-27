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
    fines INTEGER DEFAULT 0,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
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
# LEVEL SYSTEM
# =====================

def add_xp(user_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)",
                       (user_id, "user"))
        cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

    xp, level = row
    xp += amount

    leveled_up = False

    if xp >= level * 100:
        xp = 0
        level += 1
        leveled_up = True

    cursor.execute("""
    UPDATE users SET xp=?, level=? WHERE user_id=?
    """, (xp, level, user_id))

    return leveled_up, level

# =====================
# NOTIFY ADMIN
# =====================

async def notify_admin(text: str):
    try:
        await bot.api.messages.send(
            peer_id=ADMIN_ID,
            message=text,
            random_id=0
        )
    except:
        pass

# =====================
# KEYBOARDS
# =====================

def kb_main(admin=False):
    kb = Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"))
    kb.add(Text("🏆 Топ месяц")).row()
    kb.add(Text("📈 Уровень"))

    if admin:
        kb.row()
        kb.add(Text("⚙ Админ"))

    return kb


def kb_back():
    kb = Keyboard(one_time=False)
    kb.add(Text("⬅ Назад"))
    return kb

# =====================
# SAFE COMMAND
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

    text = (message.text or "").lower()
    cmd = get_cmd(message)

    if not cmd:
        if "я на месте" in text:
            cmd = "arrive"
        elif "статистика" in text:
            cmd = "stats"
        elif "топ" in text:
            cmd = "top"
        elif "топ месяц" in text:
            cmd = "top_month"
        elif "уровень" in text:
            cmd = "level"
        elif "админ" in text:
            cmd = "admin"
        elif "лучший" in text:
            cmd = "best"
        elif "назад" in text:
            cmd = "back"

    if not cmd:
        return

    match cmd:
        case "arrive":
            await arrive(message)
        case "stats":
            await stats(message)
        case "top_month":
            await top_month(message)
        case "level":
            await level(message)
        case "admin":
            await admin(message)
        case "best":
            await best_worker(message)
        case "back":
            await back(message)

# =====================
# ARRIVE
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

    leveled_up, level = add_xp(message.from_id, 10 if not late else 3)

    if not late:

        text = f"✅ Вовремя\n🕒 {t}"

    else:

        cursor.execute("""
        UPDATE users SET fines = fines + 1 WHERE user_id=?
        """, (message.from_id,))

        await notify_admin(
            f"⚠ ОПОЗДАНИЕ\n👤 {message.from_id}\n🕒 {t}\n📅 {today}"
        )

        text = f"❌ Опоздание\n🕒 {t}"

    if leveled_up:
        text += f"\n🎉 LEVEL UP! → {level}"

    db.commit()
    await message.answer(text)

# =====================
# STATS
# =====================

async def stats(message: Message):

    cursor.execute("""
    SELECT COUNT(*) FROM arrivals
    WHERE user_id=?
    """, (message.from_id,))

    total = cursor.fetchone()[0]

    cursor.execute("""
    SELECT fines, level, xp FROM users
    WHERE user_id=?
    """, (message.from_id,))

    r = cursor.fetchone()

    fines, level, xp = r if r else (0, 1, 0)

    await message.answer(f"""
📊 СТАТИСТИКА

📅 Всего: {total}
💸 Штрафы: {fines}
📈 Уровень: {level}
⭐ XP: {xp}
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

    text = f"🏆 ТОП МЕСЯЦ ({month})\n\n"

    for i, r in enumerate(rows):
        text += f"{i+1}. user{r[0]} — {r[1]} приходов\n"

    await message.answer(text, keyboard=kb_back())

# =====================
# BEST WORKER
# =====================

async def best_worker(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT user_id, COUNT(*) as cnt
    FROM arrivals
    WHERE arrival_month=?
    GROUP BY user_id
    ORDER BY cnt DESC
    LIMIT 1
    """, (month,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Нет данных")
        return

    await message.answer(
        f"🏆 ЛУЧШИЙ СОТРУДНИК\n👤 user{row[0]}\n📊 {row[1]} приходов",
        keyboard=kb_back()
    )

# =====================
# LEVEL
# =====================

async def level(message: Message):

    cursor.execute("""
    SELECT level, xp FROM users WHERE user_id=?
    """, (message.from_id,))

    r = cursor.fetchone()

    if not r:
        r = (1, 0)

    await message.answer(f"""
📈 УРОВЕНЬ

🏅 Level: {r[0]}
⭐ XP: {r[1]}
""", keyboard=kb_back())

# =====================
# ADMIN
# =====================

async def admin(message: Message):

    if message.from_id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM arrivals")
    total = cursor.fetchone()[0]

    await message.answer(f"""
⚙ АДМИН

📊 Всего приходов: {total}
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
# START
# =====================

print("BOT STARTED")
bot.run_forever()
