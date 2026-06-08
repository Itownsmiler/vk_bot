import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

import psycopg2

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"

DATABASE_URL = "postgresql://postgres:tBqXRFHAxgeaPsIpshqiXoEhKNOcxBAz@zephyr.proxy.rlwy.net:39924/railway"

WORK_END = time(11, 42)

bot = Bot(TOKEN)

conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    name TEXT,
    late_count INT DEFAULT 0,
    last_reset_month TEXT DEFAULT ''
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS arrivals (
    id SERIAL PRIMARY KEY,
    user_id BIGINT,
    arrival_date TEXT,
    arrival_time TEXT,
    late BOOLEAN
)
""")

conn.commit()


def keyboard():
    kb = Keyboard(one_time=False)

    kb.add(
        Text("🟢 Я на месте", payload={"cmd": "arrive"}),
        KeyboardButtonColor.POSITIVE
    ).row()

    kb.add(
        Text("📊 Статистика", payload={"cmd": "stats"}),
        KeyboardButtonColor.PRIMARY
    )

    return kb.get_json()


def safe_payload(message):
    payload = getattr(message, "payload", None)

    if not payload:
        return {}

    if isinstance(payload, dict):
        return payload

    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except:
            return {}

    return {}


async def get_name(user_id):
    try:
        user = await bot.api.users.get(user_ids=user_id)
        if user:
            return user[0].first_name
    except:
        pass
    return "Пользователь"


def check_month_reset():
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    current_month = now.strftime("%Y-%m")

    cursor.execute("SELECT last_reset_month FROM users LIMIT 1")
    row = cursor.fetchone()

    if row and row[0] != current_month:
        cursor.execute("""
            UPDATE users
            SET late_count = 0,
                last_reset_month = %s
        """, (current_month,))
        conn.commit()


@bot.on.message(text=["/start", "start", "Начать"])
async def start(message: Message):
    check_month_reset()

    name = await get_name(message.from_id)
    current_month = datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m")

    cursor.execute("""
        INSERT INTO users (user_id, name, last_reset_month)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET name = EXCLUDED.name
    """, (message.from_id, name, current_month))

    conn.commit()

    await message.answer(
        f"Привет, {name} 👋",
        keyboard=keyboard()
    )


@bot.on.message()
async def router(message: Message):
    payload = safe_payload(message)
    cmd = payload.get("cmd")

    if cmd == "arrive":
        await arrive(message)
        return

    if cmd == "stats":
        await stats(message)
        return

    await message.answer(
        "👋 Используй кнопки ниже",
        keyboard=keyboard()
    )


async def arrive(message: Message):
    check_month_reset()

    now = datetime.now(ZoneInfo("Europe/Moscow"))

    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")
    current_month = now.strftime("%Y-%m")

    cursor.execute("""
        SELECT 1 FROM arrivals
        WHERE user_id=%s AND arrival_date=%s
    """, (message.from_id, today))

    if cursor.fetchone():
        return await message.answer("⚠ Уже отмечался сегодня", keyboard=keyboard())

    current_time = now.time()

start_ok = time(10, 0)
end_ok = time(11, 41)

late = not (start_ok <= current_time <= end_ok)

    cursor.execute("""
        INSERT INTO arrivals (user_id, arrival_date, arrival_time, late)
        VALUES (%s, %s, %s, %s)
    """, (message.from_id, today, current_time, late))

    cursor.execute("""
        INSERT INTO users (user_id, name, last_reset_month)
        VALUES (%s, %s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET name = EXCLUDED.name
    """, (message.from_id, await get_name(message.from_id), current_month))

    if late:
        cursor.execute("""
            UPDATE users
            SET late_count = late_count + 1
            WHERE user_id=%s
        """, (message.from_id,))
        text = f"❌ Опоздание\n🕒 {current_time}"
    else:
        text = f"✅ Вовремя\n🕒 {current_time}"

    conn.commit()

    await message.answer(text, keyboard=keyboard())


async def stats(message: Message):
    check_month_reset()

    cursor.execute("""
        SELECT name, late_count
        FROM users
        ORDER BY late_count DESC, name ASC
    """)

    rows = cursor.fetchall()

    if not rows:
        return await message.answer("Нет данных", keyboard=keyboard())

    text = "📊 Статистика опозданий\n\n"

    for name, late in rows:
        text += f"👤 {name} — {late}\n"

    await message.answer(text, keyboard=keyboard())


print("BOT STARTED")
bot.run_forever()
