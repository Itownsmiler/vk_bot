```python
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo

import psycopg2

from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

# =====================================
# НАСТРОЙКИ
# =====================================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"

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
# SAFE PAYLOAD
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

    kb.add(
        Text("🟢 Отметиться", payload={"cmd": "arrive"}),
        KeyboardButtonColor.POSITIVE
    ).row()

    kb.add(
        Text("📊 Статистика", payload={"cmd": "stats"}),
        KeyboardButtonColor.PRIMARY
    )

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
        f"Привет, {name} 👋\nНажми кнопку для отметки.",
        keyboard=keyboard()
    )

# =====================================
# ROUTER
# =====================================

@bot.on.message()
async def router(message: Message):

    payload = safe_payload(message)

    cmd = payload.get("cmd")

    if cmd == "arrive":
        return await arrive(message)

    if cmd == "stats":
        return await stats(message)

# =====================================
# ARRIVE
# =====================================

async def arrive(message: Message):

    now = datetime.now(ZoneInfo("Europe/Moscow"))

    today = now.strftime("%Y-%m-%d")
    month = now.strftime("%Y-%m")
    current_time = now.strftime("%H:%M:%S")

    cursor.execute("""
        SELECT 1
        FROM arrivals
        WHERE user_id=%s
        AND arrival_date=%s
    """, (message.from_id, today))

    if cursor.fetchone():
        return await message.answer(
            "⚠ Вы уже отметились сегодня.",
            keyboard=keyboard()
        )

    name = await get_name(message.from_id)

    cursor.execute("""
        INSERT INTO users (user_id, name)
        VALUES (%s, %s)
        ON CONFLICT (user_id)
        DO UPDATE SET name=EXCLUDED.name
    """, (message.from_id, name))

    late = now.time() >= WORK_END

    cursor.execute("""
        INSERT INTO arrivals (
            user_id,
            arrival_date,
            arrival_time,
            arrival_month,
            late
        )
        VALUES (%s, %s, %s, %s, %s)
    """, (
        message.from_id,
        today,
        current_time,
        month,
        late
    ))

    if late:

        cursor.execute("""
            UPDATE users
            SET late_count = late_count + 1
            WHERE user_id=%s
        """, (message.from_id,))

        text = (
            f"❌ Опоздание\n"
            f"🕒 Время отметки: {current_time}"
        )

    else:

        text = (
            f"✅ Отметка принята\n"
            f"🕒 Время отметки: {current_time}"
        )

    conn.commit()

    await message.answer(
        text,
        keyboard=keyboard()
    )

# =====================================
# STATS
# =====================================

async def stats(message: Message):

    cursor.execute("""
        SELECT
            name,
            late_count
        FROM users
        WHERE user_id=%s
    """, (message.from_id,))

    row = cursor.fetchone()

    if not row:
        return await message.answer(
            "❌ Нет данных",
            keyboard=keyboard()
        )

    await message.answer(
        f"""
📊 СТАТИСТИКА

👤 {row[0]}
❌ Опозданий: {row[1]}
""",
        keyboard=keyboard()
    )

# =====================================
# RUN
# =====================================

print("BOT STARTED")
bot.run_forever()
```
