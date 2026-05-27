import os
import psycopg2
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
# POSTGRES CONNECT (RAILWAY AUTO)
# =====================

DATABASE_URL = os.getenv("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# =====================
# INIT TABLES
# =====================

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

        cursor.execute("SELECT xp, level FROM users WHERE user_id=%s", (user_id,))
        row = cursor.fetchone()

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
# GET NAME SAFE
# =====================

async def get_name(user_id: int):
    try:
        user = await bot.api.users.get(user_id)
        return user[0].first_name
    except:
        return "Пользователь"

# =====================
# KEYBOARD
# =====================

def kb():
    kb = Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте")).row()
    kb.add(Text("📊 Статистика"))
    kb.add(Text("🏆 ТОП МЕСЯЦА")).row()
    kb.add(Text("📈 Уровень"))
    return kb

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
        await message.answer("⚠ Уже отмечался")
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

    text = "❌ Опоздание" if late else "✅ Вовремя"
    if leveled:
        text += f"\n🎉 LEVEL UP → {level}"

    await message.answer(text, keyboard=kb())

# =====================
# STATS
# =====================

@bot.on.message(text="📊 Статистика")
async def stats(message: Message):

    cursor.execute("""
    SELECT fines, xp, level, name FROM users
    WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone()

    if not row:
        await message.answer("Нет данных")
        return

    await message.answer(f"""
📊 СТАТИСТИКА

👤 {row[3]}
📈 Level: {row[2]}
⭐ XP: {row[1]}/100
💸 Штрафы: {row[0]}
""")

# =====================
# TOP MONTH
# =====================

@bot.on.message(text="🏆 ТОП МЕСЯЦА")
async def top_month(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
    SELECT COALESCE(u.name, 'Пользователь'), u.level, COUNT(a.user_id)
    FROM arrivals a
    LEFT JOIN users u ON u.user_id=a.user_id
    WHERE a.arrival_month=%s
    GROUP BY a.user_id, u.name, u.level
    ORDER BY COUNT(a.user_id) DESC
    """, (month,))

    rows = cursor.fetchall()

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
