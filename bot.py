import asyncio
import sqlite3
from datetime import datetime
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

TOKEN = "vk1.a.BSMplcd7XE_DJYe-BSTV7nD3TJiilHu55yKIn-ZvaJQw_WDTGCMqYQEAnGKFhfn_l5aisTLBFa3uTUP0TYXXgtnfUltrUMlN8O14SoNERjflr9izvEcMWs6HsGUN0e8paP-e8rFQR6qfjn7M9rBj6oJm460195nHJuSb-xzqxOqQQzkTt7j3AJyhsaMEu94lXiWyBd06DLQN8JIVG6p9Fg"
ADMIN_ID = 47965177

bot = Bot(token=TOKEN)

db = sqlite3.connect("database.db")
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER,
    name TEXT,
    arrivals INTEGER DEFAULT 0,
    late INTEGER DEFAULT 0,
    money INTEGER DEFAULT 0,
    last_day TEXT
)
""")
db.commit()


def menu_keyboard():
    keyboard = Keyboard(one_time=False)

    keyboard.add(
        Text("✅ Я на месте"),
        color=KeyboardButtonColor.POSITIVE
    )

    keyboard.row()

    keyboard.add(
        Text("🏆 Рейтинг"),
        color=KeyboardButtonColor.PRIMARY
    )

    keyboard.add(
        Text("💰 Баланс"),
        color=KeyboardButtonColor.SECONDARY
    )

    keyboard.row()

    keyboard.add(
        Text("📊 Статистика"),
        color=KeyboardButtonColor.PRIMARY
    )

    return keyboard.get_json()


def admin_keyboard():
    keyboard = Keyboard(one_time=False)

    keyboard.add(
        Text("👑 Админ панель"),
        color=KeyboardButtonColor.NEGATIVE
    )

    keyboard.row()

    keyboard.add(
        Text("🏆 Рейтинг"),
        color=KeyboardButtonColor.PRIMARY
    )

    keyboard.add(
        Text("💰 Баланс"),
        color=KeyboardButtonColor.SECONDARY
    )

    keyboard.row()

    keyboard.add(
        Text("📊 Статистика"),
        color=KeyboardButtonColor.PRIMARY
    )

    return keyboard.get_json()


@bot.on.message(text=["/start", "Начать"])
async def start(message: Message):

    user = message.from_id
    name = f"{message.from_user.first_name}"

    sql.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user,)
    )

    check = sql.fetchone()

    if not check:
        sql.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
            (user, name, 0, 0, 0, "")
        )
        db.commit()

    text = f"""
🔥 Добро пожаловать, {name}

Этот бот считает:
✅ Приходы
⏰ Опоздания
💰 Баланс
🏆 Рейтинг сотрудников

Нажимай кнопку ниже 👇
"""

    if user == ADMIN_ID:
        await message.answer(
            text,
            keyboard=admin_keyboard()
        )
    else:
        await message.answer(
            text,
            keyboard=menu_keyboard()
        )


@bot.on.message(text="✅ Я на месте")
async def arrive(message: Message):

    user = message.from_id
    now = datetime.now()

    current_time = now.strftime("%H:%M")
    current_day = now.strftime("%Y-%m-%d")

    sql.execute(
        "SELECT * FROM users WHERE user_id = ?",
        (user,)
    )

    data = sql.fetchone()

    if data[5] == current_day:
        await message.answer(
            f"⚠️ Ты уже отмечался сегодня\n\n🕒 Время: {current_time}"
        )
        return

    hour = now.hour
    minute = now.minute

    total_minutes = hour * 60 + minute

    start_minutes = 9 * 60

    money = data[4]
    arrivals = data[2]
    late = data[3]

    if total_minutes <= start_minutes:

        arrivals += 1
        money += 100

        bonus_texts = [
            "🔥 Красавчик! Пришел вовремя",
            "💪 Идеальная дисциплина",
            "🏆 Ты сегодня в топе",
            "⚡ Быстро четко мощно",
            "😎 Начальство довольно тобой"
        ]

        import random
        phrase = random.choice(bonus_texts)

        if arrivals % 30 == 0:
            money += 1000
            bonus = "\n🎁 Бонус за 30 приходов: +1000₽"
        else:
            bonus = ""

        sql.execute("""
        UPDATE users
        SET arrivals = ?, money = ?, last_day = ?
        WHERE user_id = ?
        """, (
            arrivals,
            money,
            current_day,
            user
        ))

        db.commit()

        await message.answer(
            f"""
{phrase}

🕒 Время: {current_time}

💰 +100₽
💵 Баланс: {money}₽
🏆 Приходов вовремя: {arrivals}
{bonus}
"""
        )

    else:

        late += 1
        money -= 1000

        sql.execute("""
        UPDATE users
        SET late = ?, money = ?, last_day = ?
        WHERE user_id = ?
        """, (
            late,
            money,
            current_day,
            user
        ))

        db.commit()

        await message.answer(
            f"""
🚨 ОПОЗДАНИЕ

⏰ Время: {current_time}

💸 Штраф: -1000₽
💵 Баланс: {money}₽

😬 Завтра приходи раньше
"""
        )


@bot.on.message(text="💰 Баланс")
async def balance(message: Message):

    user = message.from_id

    sql.execute(
        "SELECT money FROM users WHERE user_id = ?",
        (user,)
    )

    money = sql.fetchone()[0]

    await message.answer(
        f"""
💰 Твой баланс

💵 {money}₽
"""
    )


@bot.on.message(text="📊 Статистика")
async def stats(message: Message):

    user = message.from_id

    sql.execute("""
    SELECT arrivals, late, money
    FROM users
    WHERE user_id = ?
    """, (user,))

    data = sql.fetchone()

    await message.answer(
        f"""
📊 Твоя статистика

✅ Вовремя: {data[0]}
🚨 Опозданий: {data[1]}
💰 Баланс: {data[2]}₽
"""
    )


@bot.on.message(text="🏆 Рейтинг")
async def top(message: Message):

    sql.execute("""
    SELECT name, arrivals, money
    FROM users
    ORDER BY arrivals DESC
    LIMIT 10
    """)

    users = sql.fetchall()

    text = "🏆 ТОП СОТРУДНИКОВ\n\n"

    place = 1

    for user in users:
        text += (
            f"{place}. {user[0]}\n"
            f"✅ {user[1]} | 💰 {user[2]}₽\n\n"
        )
        place += 1

    await message.answer(text)


@bot.on.message(text="👑 Админ панель")
async def admin_panel(message: Message):

    if message.from_id != ADMIN_ID:
        return

    sql.execute("SELECT COUNT(*) FROM users")
    total_users = sql.fetchone()[0]

    sql.execute("SELECT SUM(arrivals) FROM users")
    total_arrivals = sql.fetchone()[0]

    sql.execute("SELECT SUM(late) FROM users")
    total_late = sql.fetchone()[0]

    if total_arrivals is None:
        total_arrivals = 0

    if total_late is None:
        total_late = 0

    await message.answer(
        f"""
👑 АДМИН ПАНЕЛЬ

👥 Пользователей: {total_users}

✅ Всего приходов: {total_arrivals}

🚨 Всего опозданий: {total_late}

🔥 Бот работает отлично
"""
    )


print("Бот запущен")

bot.run_forever()
