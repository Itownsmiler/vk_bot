import sqlite3
import random
from datetime import datetime
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

# =====================================
# НАСТРОЙКИ
# =====================================

TOKEN = "vk1.a.FlawJLr5MlrkGA6EOyeVXwfx7qFiAhKYCLjbxdhbHe_udi91ofdgERFpIIRG9oFcg9GeLa1uIeVYLO3p0PcapFjI_h0TeXSzVi8mBrJiDZkHCl50Ai4oKX3hyu3IFVoYvQgF4qZYsM_2yI4JjcaGDuSly1RceyiNDxbrS89LuUwFSSWxVoXtmLFEgAPBxlV_nWMtv2T8VkfUfEN73wAD0w"
ADMIN_ID = 47965177

WORK_HOUR = 9
WORK_MINUTE = 0

BONUS_FOR_30 = 1000
PENALTY_FOR_3_LATE = 1000

# =====================================
# БОТ
# =====================================

bot = Bot(token=TOKEN)

# =====================================
# БАЗА ДАННЫХ
# =====================================

db = sqlite3.connect("workers.db")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    balance INTEGER DEFAULT 0,
    total_arrivals INTEGER DEFAULT 0,
    on_time INTEGER DEFAULT 0,
    late_count INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0
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

# =====================================
# ФРАЗЫ
# =====================================

GOOD_MESSAGES = [
    "🔥 Красавчик! Первый на месте!",
    "💪 Отличная дисциплина!",
    "🚀 Машина! Так держать!",
    "😎 Босс уже доволен тобой!",
    "🏆 Сегодня ты в топе!"
]

LATE_MESSAGES = [
    "😴 Проспал что ли?",
    "⌛ Опоздание записано...",
    "👀 Коллектив уже работает!",
    "⚠ Надо приходить раньше!",
    "📉 Минус к дисциплине"
]

# =====================================
# КЛАВИАТУРА
# =====================================

def get_keyboard(admin=False):
    keyboard = Keyboard(one_time=False)

    keyboard.add(
        Text("🟢 Я на месте"),
        color=KeyboardButtonColor.POSITIVE
    ).row()

    keyboard.add(
        Text("💰 Баланс"),
        color=KeyboardButtonColor.PRIMARY
    )

    keyboard.add(
        Text("🏆 Топ"),
        color=KeyboardButtonColor.SECONDARY
    ).row()

    keyboard.add(
        Text("📊 Статистика"),
        color=KeyboardButtonColor.PRIMARY
    )

    if admin:
        keyboard.row()
        keyboard.add(
            Text("⚙ Админ-панель"),
            color=KeyboardButtonColor.NEGATIVE
        )

    return keyboard.get_json()

# =====================================
# SAFE VK USER GET
# =====================================

async def get_user_name(user_id: int):
    try:
        users = await bot.api.users.get(user_ids=user_id)
        if users:
            return users[0].first_name
    except Exception as e:
        print("VK API error:", e)

    return "Пользователь"

# =====================================
# СТАРТ
# =====================================

@bot.on.message(text=["Начать", "/start", "start"])
async def start(message: Message):

    name = await get_user_name(message.from_id)

    cursor.execute("""
    INSERT OR IGNORE INTO users (user_id, name)
    VALUES (?, ?)
    """, (message.from_id, name))

    db.commit()

    await message.answer(
        f"""
🔥 Привет, {name}!

Добро пожаловать в систему учета сотрудников 👇
""",
        keyboard=get_keyboard(message.from_id == ADMIN_ID)
    )

# =====================================
# ПРИБЫТИЕ
# =====================================

@bot.on.message(text="🟢 Я на месте")
async def arrive(message: Message):

    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M:%S")

    cursor.execute("""
    SELECT * FROM arrivals
    WHERE user_id = ? AND arrival_date = ?
    """, (message.from_id, today))

    if cursor.fetchone():
        await message.answer("⚠ Ты уже отмечался сегодня.")
        return

    name = await get_user_name(message.from_id)

    cursor.execute("""
    INSERT INTO arrivals (user_id, name, arrival_time, arrival_date)
    VALUES (?, ?, ?, ?)
    """, (message.from_id, name, current_time, today))

    cursor.execute("""
    SELECT COUNT(*) FROM arrivals
    WHERE arrival_date = ?
    """, (today,))

    position = cursor.fetchone()[0]

    work_time = now.replace(
        hour=WORK_HOUR,
        minute=WORK_MINUTE,
        second=0,
        microsecond=0
    )

    # =====================
    # ВОВРЕМЯ
    # =====================

    if now <= work_time:

        reward = 100
        if position == 1:
            reward += 50

        cursor.execute("""
        UPDATE users
        SET balance = balance + ?,
            total_arrivals = total_arrivals + 1,
            on_time = on_time + 1,
            streak = streak + 1
        WHERE user_id = ?
        """, (reward, message.from_id))

        cursor.execute("""
        SELECT on_time FROM users WHERE user_id = ?
        """, (message.from_id,))

        on_time = cursor.fetchone()[0]

        bonus_text = ""

        if on_time and on_time % 30 == 0:
            cursor.execute("""
            UPDATE users
            SET balance = balance + ?
            WHERE user_id = ?
            """, (BONUS_FOR_30, message.from_id))

            bonus_text = f"\n🎁 Бонус за 30 приходов: +{BONUS_FOR_30}₽"

        text = f"""
✅ {random.choice(GOOD_MESSAGES)}

🕒 Время: {current_time}
🏆 Место сегодня: #{position}
💰 Получено: +{reward}₽
{bonus_text}
"""

    # =====================
    # ОПОЗДАНИЕ
    # =====================

    else:

        cursor.execute("""
        UPDATE users
        SET total_arrivals = total_arrivals + 1,
            late_count = late_count + 1,
            streak = 0
        WHERE user_id = ?
        """, (message.from_id,))

        cursor.execute("""
        SELECT late_count FROM users WHERE user_id = ?
        """, (message.from_id,))

        late_count = cursor.fetchone()[0]

        penalty_text = ""

        if late_count and late_count % 3 == 0:
            cursor.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE user_id = ?
            """, (PENALTY_FOR_3_LATE, message.from_id))

            penalty_text = f"\n💸 Штраф: -{PENALTY_FOR_3_LATE}₽"

        text = f"""
❌ {random.choice(LATE_MESSAGES)}

🕒 Время: {current_time}
🏆 Место сегодня: #{position}
{penalty_text}
"""

    db.commit()
    await message.answer(text)

# =====================================
# БАЛАНС
# =====================================

@bot.on.message(text="💰 Баланс")
async def balance(message: Message):

    cursor.execute("""
    SELECT balance, streak FROM users WHERE user_id = ?
    """, (message.from_id,))

    user = cursor.fetchone()

    if not user:
        await message.answer("Нет данных о тебе. Напиши /start")
        return

    await message.answer(f"""
💰 Баланс: {user[0]}₽
🔥 Серия вовремя: {user[1]}
""")

# =====================================
# СТАТИСТИКА
# =====================================

@bot.on.message(text="📊 Статистика")
async def stats(message: Message):

    cursor.execute("""
    SELECT total_arrivals, on_time, late_count
    FROM users WHERE user_id = ?
    """, (message.from_id,))

    user = cursor.fetchone()

    if not user:
        await message.answer("Нет данных о тебе. Напиши /start")
        return

    await message.answer(f"""
📊 Твоя статистика

✅ Вовремя: {user[1]}
❌ Опозданий: {user[2]}
📅 Всего приходов: {user[0]}
""")

# =====================================
# ТОП
# =====================================

@bot.on.message(text="🏆 Топ")
async def top(message: Message):

    cursor.execute("""
    SELECT name, on_time
    FROM users
    ORDER BY on_time DESC
    LIMIT 10
    """)

    users = cursor.fetchall()

    text = "🏆 ТОП СОТРУДНИКОВ\n\n"
    medals = ["🥇", "🥈", "🥉"]

    for i, user in enumerate(users):
        medal = medals[i] if i < 3 else "👤"
        text += f"{medal} {user[0]} — {user[1]} вовремя\n"

    await message.answer(text)

# =====================================
# АДМИНКА
# =====================================

@bot.on.message(text="⚙ Админ-панель")
async def admin_panel(message: Message):

    if message.from_id != ADMIN_ID:
        return

    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]

    cursor.execute("""
    SELECT COUNT(*) FROM arrivals
    WHERE arrival_date = ?
    """, (datetime.now().strftime("%Y-%m-%d"),))

    today = cursor.fetchone()[0]

    await message.answer(f"""
⚙ АДМИН ПАНЕЛЬ

👥 Сотрудников: {users}
🟢 Сегодня отметились: {today}
""")

# =====================================
# ЗАПУСК
# =====================================

print("Бот запущен")
bot.run_forever()
