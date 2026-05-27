import json
from datetime import datetime, time

import psycopg2

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

# =====================================
# НАСТРОЙКИ
# =====================================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"
ADMIN_ID = 47965177
WORK_END = time(11, 42)

DATABASE_URL = "postgresql://postgres:tBqXRFHAxgeaPsIpshqiXoEhKNOcxBAz@zephyr.proxy.rlwy.net:39924/railway"

bot = Bot(TOKEN)

# =====================================
# DATABASE
# =====================================

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    name TEXT,
    fines INT DEFAULT 0,
    xp INT DEFAULT 0,
    level INT DEFAULT 1,
    late_count INT DEFAULT 0
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    arrival_date TEXT,
    arrival_time TEXT,
    arrival_month TEXT,
    late BOOLEAN
)
""")

conn.commit()

# =====================================
# SAFE PAYLOAD (ГЛАВНЫЙ ФИКС)
# =====================================

def safe_payload(message: Message):
    p = message.payload

    if isinstance(p, str):
        try:
            return json.loads(p)
        except:
            return {}

    if isinstance(p, dict):
        return p

    return {}

# =====================================
# KEYBOARD
# =====================================

def keyboard():
    kb = Keyboard(one_time=False)

    kb.add(Text("🟢 Я на месте", payload={"cmd": "arrive"}), KeyboardButtonColor.POSITIVE).row()

    kb.add(Text("📊 Статистика", payload={"cmd": "stats"}), KeyboardButtonColor.PRIMARY)

    kb.add(Text("🏆 Топ месяца", payload={"cmd": "top"}), KeyboardButtonColor.SECONDARY).row()

    kb.add(Text("📈 Уровень", payload={"cmd": "level"}), KeyboardButtonColor.POSITIVE)

    return kb.get_json()

# =====================================
# NAME
# =====================================

async def get_name(user_id: int):
    try:
        user = await bot.api.users.get(user_ids=user_id)
        if user:
            return user[0].first_name
    except:
        pass
    return "Пользователь"

# =====================================
# XP SYSTEM
# =====================================

def add_xp(user_id: int, amount: int):
    cursor.execute("SELECT xp, level FROM users WHERE user_id=%s", (user_id,))
    row = cursor.fetchone()

    if not row:
        return False, 1, 0

    xp, level = row
    xp += amount

    level_up = False

    while xp >= 100:
        xp -= 100
        level += 1
        level_up = True

    cursor.execute("""
        UPDATE users SET xp=%s, level=%s WHERE user_id=%s
    """, (xp, level, user_id))

    conn.commit()

    return level_up, level, xp

# =====================================
# START
# =====================================

@bot.on.message(text=["/start", "start", "Начать"])
async def start(message: Message):

    name = await get_name(message.from_id)

    cursor.execute("""
        INSERT INTO users (user_id, name)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET name=EXCLUDED.name
    """, (message.from_id, name))

    conn.commit()

    await message.answer(
        f"🔥 Привет, {name}\nСистема сотрудников активна",
        keyboard=keyboard()
    )

# =====================================
# ROUTER (ИСПРАВЛЕННЫЙ)
# =====================================

@bot.on.message()
async def router(message: Message):

    payload = safe_payload(message)
    cmd = payload.get("cmd")

    if cmd == "arrive":
        return await arrive(message)

    if cmd == "stats":
        return await stats(message)

    if cmd == "top":
        return await top_month(message)

    if cmd == "level":
        return await level(message)

# =====================================
# ARRIVE
# =====================================

async def arrive(message: Message):

    now = datetime.now()

    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    current_time = now.strftime("%H:%M:%S")

    cursor.execute("""
        SELECT 1 FROM arrivals
        WHERE user_id=%s AND arrival_date=%s
    """, (message.from_id, today))

    if cursor.fetchone():
        return await message.answer("⚠ Уже отмечался", keyboard=keyboard())

    name = await get_name(message.from_id)

    cursor.execute("""
        INSERT INTO users (user_id, name)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET name=EXCLUDED.name
    """, (message.from_id, name))

    late = now.time() > WORK_END
    xp_add = 3 if late else 10

    level_up, level, xp = add_xp(message.from_id, xp_add)

    cursor.execute("""
        INSERT INTO arrivals (
            user_id, arrival_date, arrival_time, arrival_month, late
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (message.from_id, today, current_time, month, late))

    text = ""

    if late:
        cursor.execute("""
            UPDATE users SET late_count = late_count + 1
            WHERE user_id=%s
        """, (message.from_id,))

        cursor.execute("""
            SELECT late_count FROM users WHERE user_id=%s
        """, (message.from_id,))

        late_count = cursor.fetchone()[0]

        text = f"❌ ОПОЗДАНИЕ\n🕒 {current_time}\n⭐ +3 XP"

        if late_count % 3 == 0:
            cursor.execute("""
                UPDATE users SET fines = fines + 1
                WHERE user_id=%s
            """, (message.from_id,))
            text += "\n💸 Штраф"

        try:
            await bot.api.messages.send(
                user_id=ADMIN_ID,
                random_id=0,
                message=f"⚠ Пользователь опоздал"
            )
        except:
            pass

    else:
        text = f"✅ ВОВРЕМЯ\n🕒 {current_time}\n⭐ +10 XP"

    if level_up:
        text += f"\n\n🎉 LEVEL UP: {level}"

    conn.commit()

    await message.answer(text, keyboard=keyboard())

# =====================================
# STATS
# =====================================

async def stats(message: Message):

    cursor.execute("""
        SELECT name, fines, xp, level
        FROM users
        WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone()

    if not row:
        return await message.answer("❌ Нет данных", keyboard=keyboard())

    await message.answer(f"""
📊 СТАТИСТИКА

👤 {row[0]}
📈 Lv.{row[3]}
⭐ XP: {row[2]}/100
💸 Штрафы: {row[1]}
""", keyboard=keyboard())

# =====================================
# TOP MONTH
# =====================================

async def top_month(message: Message):

    month = datetime.now().strftime("%Y-%m")

    cursor.execute("""
        SELECT COALESCE(u.name,'Пользователь'), u.level, COUNT(a.user_id)
        FROM arrivals a
        LEFT JOIN users u ON u.user_id=a.user_id
        WHERE a.arrival_month=%s
        GROUP BY a.user_id, u.name, u.level
        ORDER BY COUNT(a.user_id) DESC
        LIMIT 10
    """, (month,))

    rows = cursor.fetchall()

    if not rows:
        return await message.answer("📭 Нет данных", keyboard=keyboard())

    medals = ["🥇", "🥈", "🥉"]

    text = f"🏆 ТОП МЕСЯЦА ({month})\n\n"

    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else "👤"
        text += f"{medal} {r[0]} | Lv.{r[1]} | {r[2]} дней\n"

    await message.answer(text, keyboard=keyboard())

# =====================================
# LEVEL
# =====================================

async def level(message: Message):

    cursor.execute("""
        SELECT xp, level FROM users WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone()

    if not row:
        return await message.answer("❌ Нет данных", keyboard=keyboard())

    await message.answer(f"""
📈 УРОВЕНЬ

🏅 Level: {row[1]}
⭐ XP: {row[0]}/100
""", keyboard=keyboard())

# =====================================
# RUN
# =====================================

print("BOT STARTED")
bot.run_forever()
