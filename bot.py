
# bot.py
import json
from datetime import datetime, time
from zoneinfo import ZoneInfo
import psycopg2
from psycopg2 import OperationalError, InterfaceError
from vkbottle.bot import Bot, Message
from vkbottle import Keyboard, KeyboardButtonColor, Text

TOKEN = "PASTE_TOKEN"
DATABASE_URL = "PASTE_DATABASE_URL"

bot = Bot(TOKEN)

WORK_START = time(10,0)
WORK_END = time(11,41)

_conn=None

def get_conn():
    global _conn
    try:
        if _conn is None or _conn.closed:
            _conn=psycopg2.connect(DATABASE_URL)
            _conn.autocommit=False
    except Exception:
        _conn=psycopg2.connect(DATABASE_URL)
    return _conn

def execute(query, params=None, fetch=None):
    conn=get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result=None
            if fetch=="one":
                result=cur.fetchone()
            elif fetch=="all":
                result=cur.fetchall()
            conn.commit()
            return result
    except (OperationalError, InterfaceError):
        conn=psycopg2.connect(DATABASE_URL)
        globals()["_conn"]=conn
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            result=None
            if fetch=="one":
                result=cur.fetchone()
            elif fetch=="all":
                result=cur.fetchall()
            conn.commit()
            return result

execute("""CREATE TABLE IF NOT EXISTS users(
user_id BIGINT PRIMARY KEY,
name TEXT,
late_count INT DEFAULT 0,
last_reset_month TEXT DEFAULT ''
)""")
execute("""CREATE TABLE IF NOT EXISTS arrivals(
id SERIAL PRIMARY KEY,
user_id BIGINT,
arrival_date TEXT,
arrival_time TEXT,
late BOOLEAN
)""")

def keyboard():
    kb=Keyboard(one_time=False)
    kb.add(Text("🟢 Я на месте",payload={"cmd":"arrive"}),KeyboardButtonColor.POSITIVE).row()
    kb.add(Text("📊 Статистика",payload={"cmd":"stats"}),KeyboardButtonColor.PRIMARY)
    return kb.get_json()

def safe_payload(message):
    p=getattr(message,"payload",None)
    if isinstance(p,dict): return p
    if isinstance(p,str):
        try:return json.loads(p)
        except: return {}
    return {}

async def get_name(uid):
    try:
        return (await bot.api.users.get(user_ids=uid))[0].first_name
    except:
        return "Пользователь"

def check_month_reset():
    m=datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m")
    row=execute("SELECT last_reset_month FROM users LIMIT 1",fetch="one")
    if row and row[0]!=m:
        execute("UPDATE users SET late_count=0,last_reset_month=%s",(m,))

@bot.on.message(text=["/start","start","Начать"])
async def start(message:Message):
    check_month_reset()
    m=datetime.now(ZoneInfo("Europe/Moscow")).strftime("%Y-%m")
    execute("""INSERT INTO users(user_id,name,last_reset_month)
    VALUES(%s,%s,%s)
    ON CONFLICT(user_id) DO UPDATE SET name=EXCLUDED.name""",
    (message.from_id,await get_name(message.from_id),m))
    await message.answer("Привет!",keyboard=keyboard())

@bot.on.message()
async def router(message:Message):
    cmd=safe_payload(message).get("cmd")
    if cmd=="arrive":
        await arrive(message); return
    if cmd=="stats":
        await stats(message); return
    await message.answer("Используй кнопки.",keyboard=keyboard())

async def arrive(message):
    check_month_reset()
    now=datetime.now(ZoneInfo("Europe/Moscow"))
    today=now.strftime("%Y-%m-%d")
    if execute("SELECT 1 FROM arrivals WHERE user_id=%s AND arrival_date=%s",(message.from_id,today),fetch="one"):
        return await message.answer("⚠ Уже отмечался",keyboard=keyboard())
    late=not(WORK_START<=now.time()<=WORK_END)
    execute("INSERT INTO arrivals(user_id,arrival_date,arrival_time,late) VALUES(%s,%s,%s,%s)",
            (message.from_id,today,now.strftime("%H:%M:%S"),late))
    m=now.strftime("%Y-%m")
    execute("""INSERT INTO users(user_id,name,last_reset_month)
    VALUES(%s,%s,%s)
    ON CONFLICT(user_id) DO UPDATE SET name=EXCLUDED.name""",
    (message.from_id,await get_name(message.from_id),m))
    if late:
        execute("UPDATE users SET late_count=late_count+1 WHERE user_id=%s",(message.from_id,))
    await message.answer(("❌ Опоздание" if late else "✅ Вовремя"),keyboard=keyboard())

async def stats(message):
    check_month_reset()
    rows=execute("SELECT name,late_count FROM users ORDER BY late_count DESC,name",fetch="all") or []
    txt="📊 Статистика\n\n"+"\n".join(f"👤 {n} — {c}" for n,c in rows) if rows else "Нет данных"
    await message.answer(txt,keyboard=keyboard())

print("BOT STARTED")
bot.run_forever()
