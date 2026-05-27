import sqlite3
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

CURRENT_MONTH = datetime.now().strftime("%Y-%m")

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
# MONTH SYSTEM
# =====================

def check_month():
    global CURRENT_MONTH
    now = datetime.now().strftime("%Y-%m")
    if now != CURRENT_MONTH:
        CURRENT_MONTH = now

# =====================
# XP SYSTEM
# =====================

def add_xp(user_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT OR IGNORE INTO users (user_id, name)
        VALUES (?, ?)
        """, (user_id, "user"))

        cursor.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
        row = cursor.fetchone()

    xp, level = row
    xp += amount

    leveled = False

    while xp >= 100:
        xp -= 100
        level += 1
        leveled = True

    cursor.execute("""
    UPDATE users SET xp=?, level=? WHERE user_id=?
    """, (xp, level, user_id))

    return leveled, level, xp

# =====================
# ADMIN NOTIFY
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
# KEYBOARD
# =====================

def kb_main():
    kb = Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"))
    kb.add(Text("🏆 ТОП МЕСЯЦА")).row()
    kb.add(Text("📈 Уровень"))
    return kb

def kb_back():
    kb = Keyboard(one_time=False)
    kb.add(Text("⬅ Назад"))
    return kb

# =====================
# ROUTER
# =====================

@bot.on.message()
async def router(message: Message):

    text = (message.text or "").lower()

    if "я на месте" in text:
        await arrive(message)
    elif "статистика" in text:
        await stats(message)
    elif "топ месяца" in text:
        await top_month(message)
    elif "уровень" in text:
        await level(message)
    elif "назад" in text:
        await back(message)

# =====================
# ARRIVE
# =====================

async def arrive(message: Message):

    check_month()

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    t = now.strftime("%H:%M:%S")

    # уже отмечался?
    cursor.execute("""
    SELECT 1 FROM arrivals
    WHERE user_id=? AND arrival_date=?
    """, (message.from_id, today))

    if cursor.fetchone():
        await message.answer("⚠ Уже отмечался")
        return

    # СТАРТОВОЕ СОХРАНЕНИЕ ИМЕНИ (ВАЖНО)
    try:
        user = await bot.api.users.get(message.from_id)
        name = user[0].first_name
    except:
        name = "Без имени"

    cursor.execute("""
    INSERT INTO users (user_id, name)
    VALUES (?, ?)
    ON CONFLICT(user_id) DO UPDATE SET name=excluded.name
    """, (message.from_id, name))

    cursor.execute("""
    INSERT INTO arrivals (user_id, arrival_date, arrival_time, arrival_month)
    VALUES (?, ?, ?, ?)
    """, (message.from_id, today, t, month))

    late = now.time() > WORK_END

    xp_gain = 10 if not late else 3
    leveled, level, xp = add_xp(message.from_id, xp_gain)

    if late:
        cursor.execute("""
        UPDATE users SET fines = fines + 1 WHERE user_id=?
        """, (message.from_id,))

        await notify_admin(
            f"⚠ ОПОЗДАНИЕ\n👤 {name}\n🕒 {t}\n📅 {today}"
        )

    db.commit()

    text = "❌ Опоздание" if late else "✅ Вовремя"

    if leveled:
        text += f"\n🎉 LEVEL UP → {level}"

    await message.answer(text)

# =====================
# STATS
# =====================

async def stats(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT COUNT(*) FROM arrivals
    WHERE user_id=? AND arrival_month=?
    """, (message.from_id, month))

    total = cursor.fetchone()[0]

    cursor.execute("""
    SELECT fines, level, xp, name FROM users
    WHERE user_id=?
    """, (message.from_id,))

    r = cursor.fetchone() or (0, 1, 0, "Без имени")

    await message.answer(f"""
📊 СТАТИСТИКА

📅 Месяц: {month}
📅 Приходов: {total}

👤 Имя: {r[3]}
📈 Уровень: {r[1]}
⭐ XP: {r[2]}/100
💸 Штрафы: {r[0]}
""", keyboard=kb_back())

# =====================
# ТОП МЕСЯЦА (ИМЕНА ИСПРАВЛЕНЫ)
# =====================

async def top_month(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT u.name, u.level, COUNT(a.user_id) as cnt
    FROM arrivals a
    JOIN users u ON u.user_id = a.user_id
    WHERE a.arrival_month = ?
    GROUP BY a.user_id
    ORDER BY cnt DESC
    """, (month,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("📭 Нет данных за месяц")
        return

    text = f"🏆 ТОП МЕСЯЦА ({month})\n\n"

    for i, (name, level, cnt) in enumerate(rows):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "👤"
        text += f"{medal} {name} (Lv.{level}) — {cnt} приходов\n"

    await message.answer(text, keyboard=kb_back())

# =====================
# LEVEL
# =====================

async def level(message: Message):

    cursor.execute("""
    SELECT level, xp FROM users WHERE user_id=?
    """, (message.from_id,))

    r = cursor.fetchone() or (1, 0)

    percent = int((r[1] / 100) * 100)

    await message.answer(f"""
📈 УРОВЕНЬ

🏅 Level: {r[0]}
⭐ XP: {r[1]}/100
📊 Прогресс: {percent}%
""", keyboard=kb_back())

# =====================
# BACK
# =====================

async def back(message: Message):
    await message.answer("🏠 Меню", keyboard=kb_main())

# =====================
# START
# =====================

print("BOT STARTED")
bot.run_forever()
