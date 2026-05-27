import random
from datetime import datetime, time

import psycopg2
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, Text

# =====================
# CONFIG
# =====================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w")  # положи токен в Railway ENV
ADMIN_ID = 47965177

WORK_END = time(11, 42)

bot = Bot(token=TOKEN)

# =====================
# DATABASE (POSTGRES)
# =====================

DATABASE_URL = os.getenv("DATABASE_URL")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    name TEXT,
    fines INT DEFAULT 0,
    xp INT DEFAULT 0,
    level INT DEFAULT 1
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    arrival_date TEXT,
    arrival_time TEXT,
    arrival_month TEXT
)
""")

conn.commit()

# =====================
# KEYBOARD
# =====================

def keyboard():
    kb = Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"), Text("🏆 Топ месяца")).row()
    kb.add(Text("📈 Уровень"))
    return kb

# =====================
# GET NAME SAFE
# =====================

async def get_name(user_id: int):
    try:
        u = await bot.api.users.get(user_id)
        return u[0].first_name
    except:
        return "Пользователь"

# =====================
# XP SYSTEM
# =====================

def add_xp(user_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM users WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()

    if not row:
        cursor.execute("""
        INSERT INTO users (user_id, name)
        VALUES (%s, %s)
        ON CONFLICT (user_id) DO NOTHING
        """, (user_id, "user"))
        conn.commit()
        row = (0, 1)

    xp, level = row
    xp += amount

    leveled = False

    while xp >= 100:
        xp -= 100
        level += 1
        leveled = True

    cursor.execute("""
    UPDATE users SET xp=%s, level=%s WHERE user_id=%s
    """, (xp, level, user_id))

    conn.commit()

    return leveled, level, xp

# =====================
# START
# =====================

@bot.on.message(text=["/start", "Начать", "start"])
async def start(message: Message):

    name = await get_name(message.from_id)

    cursor.execute("""
    INSERT INTO users (user_id, name)
    VALUES (%s, %s)
    ON CONFLICT (user_id) DO UPDATE SET name=EXCLUDED.name
    """, (message.from_id, name))

    conn.commit()

    await message.answer(
        f"🔥 Привет, {name}\nСистема сотрудников активна.",
        keyboard=keyboard()
    )

# =====================
# ARRIVE
# =====================

@bot.on.message(text="🟢 Я на месте")
async def arrive(message: Message):

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    t = now.strftime("%H:%M:%S")

    cursor.execute("""
    SELECT 1 FROM arrivals
    WHERE user_id=%s AND arrival_date=%s
    """, (message.from_id, today))

    if cursor.fetchone():
        await message.answer("⚠ Ты уже отмечался сегодня")
        return

    name = await get_name(message.from_id)

    cursor.execute("""
    INSERT INTO users (user_id, name)
    VALUES (%s, %s)
    ON CONFLICT (user_id) DO UPDATE SET name=EXCLUDED.name
    """, (message.from_id, name))

    late = now.time() > WORK_END

    xp_gain = 10 if not late else 3
    leveled, level, xp = add_xp(message.from_id, xp_gain)

    cursor.execute("""
    INSERT INTO arrivals (user_id, arrival_date, arrival_time, arrival_month)
    VALUES (%s, %s, %s, %s)
    """, (message.from_id, today, t, month))

    conn.commit()

    text = "❌ ОПОЗДАНИЕ" if late else "✅ ВОВРЕМЯ"

    if leveled:
        text += f"\n🎉 LEVEL UP → {level}"

    await message.answer(text, keyboard=keyboard())

# =====================
# STATISTICS
# =====================

@bot.on.message(text="📊 Статистика")
async def stats(message: Message):

    cursor.execute("""
    SELECT name, xp, level, fines FROM users
    WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Нет данных")
        return

    await message.answer(f"""
📊 СТАТИСТИКА

👤 {row[0]}
📈 Level: {row[2]}
⭐ XP: {row[1]}/100
💸 Штрафы: {row[3]}
""")

# =====================
# TOP MONTH
# =====================

@bot.on.message(text="🏆 Топ месяца")
async def top_month(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT COALESCE(u.name, 'Пользователь'), u.level, COUNT(a.user_id)
    FROM arrivals a
    LEFT JOIN users u ON u.user_id=a.user_id
    WHERE a.arrival_month=%s
    GROUP BY u.name, u.level, a.user_id
    ORDER BY COUNT(a.user_id) DESC
    """, (month,))

    rows = cursor.fetchall()

    if not rows:
        await message.answer("📭 Пока нет данных")
        return

    text = f"🏆 ТОП МЕСЯЦА ({month})\n\n"

    for i, (name, lvl, cnt) in enumerate(rows):
        medal = ["🥇","🥈","🥉"][i] if i < 3 else "👤"
        text += f"{medal} {name} (Lv.{lvl}) — {cnt}\n"

    await message.answer(text)

# =====================
# LEVEL
# =====================

@bot.on.message(text="📈 Уровень")
async def level(message: Message):

    cursor.execute("""
    SELECT xp, level FROM users WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone() or (0, 1)

    await message.answer(f"""
📈 УРОВЕНЬ

🏅 Level: {row[1]}
⭐ XP: {row[0]}/100
""")

# =====================
# RUN
# =====================

print("BOT STARTED")
bot.run_forever()
