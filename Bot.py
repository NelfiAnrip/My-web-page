#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Nelfi Dm - ФАРМ БОТ 250K
С КД 1 час, двойным бонусом по выходным, агрессией для не-топов
"""

import asyncio
import sqlite3
import os
import random
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.fsm.storage.memory import MemoryStorage

# ================= КОНФИГ =================
BOT_TOKEN = "8603000938:AAEnIyamjKgpS7-0FvZ-QSiXPtE_349yjts"
COOLDOWN_SECONDS = 3600  # 1 час
BONUS_AMOUNT = 250000

# Ссылка на твой веб-сайт (GitHub Pages)
WEBAPP_URL = "https://nelfianrip.github.io/My-web-page/"

# ================= БАЗА ДАННЫХ =================
DB_PATH = os.environ.get('DB_PATH', '/tmp/nelfi_farm.db')
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 0,
    last_claim TIMESTAMP,
    total_claims INTEGER DEFAULT 0,
    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================= ФУНКЦИИ =================
def is_weekend_bonus() -> bool:
    """Пятница 12:00 МСК - понедельник 12:00 МСК"""
    now = datetime.now()
    msk = now + timedelta(hours=3)
    weekday = msk.weekday()
    hour = msk.hour
    
    if weekday == 4 and hour >= 12:
        return True
    if weekday == 5:
        return True
    if weekday == 6 and hour < 12:
        return True
    return False

def get_cooldown(user_id: int):
    cursor.execute('SELECT last_claim FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if not res or not res[0]:
        return None
    last = datetime.fromisoformat(res[0])
    next_time = last + timedelta(seconds=COOLDOWN_SECONDS)
    if datetime.now() >= next_time:
        return None
    return int((next_time - datetime.now()).total_seconds())

def add_balance(user_id: int, username: str, first_name: str):
    bonus = BONUS_AMOUNT
    multiplier = 2 if is_weekend_bonus() else 1
    total_bonus = bonus * multiplier
    
    cursor.execute('''
    INSERT INTO users (user_id, username, first_name, balance, last_claim, total_claims)
    VALUES (?, ?, ?, ?, ?, ?)
    ON CONFLICT(user_id) DO UPDATE SET
        balance = balance + ?,
        last_claim = ?,
        total_claims = total_claims + 1
    ''', (user_id, username, first_name, total_bonus, datetime.now().isoformat(), 1,
          total_bonus, datetime.now().isoformat()))
    conn.commit()
    return total_bonus, multiplier

def get_user_data(user_id: int):
    cursor.execute('''
    SELECT balance, total_claims, join_date, username, first_name
    FROM users WHERE user_id = ?
    ''', (user_id,))
    result = cursor.fetchone()
    if result:
        return {
            'balance': result[0],
            'total_claims': result[1],
            'join_date': result[2],
            'username': result[3],
            'first_name': result[4]
        }
    return None

def get_leaderboard(limit: int = 10):
    cursor.execute('''
    SELECT user_id, username, first_name, balance, total_claims
    FROM users
    ORDER BY balance DESC
    LIMIT ?
    ''', (limit,))
    return cursor.fetchall()

def get_user_rank(user_id: int):
    cursor.execute('''
    SELECT COUNT(*) + 1 FROM users WHERE balance > (SELECT balance FROM users WHERE user_id = ?)
    ''', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else None

# ================= КЛАВИАТУРЫ =================
def get_main_keyboard(user_id: int, username: str):
    web_app_url_with_params = f"{WEBAPP_URL}?uid={user_id}&un={username}"
    
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 ЗАБРАТЬ 250К", callback_data="claim")],
        [InlineKeyboardButton(text="🌐 ОТКРЫТЬ ПАНЕЛЬ", web_app=WebAppInfo(url=web_app_url_with_params))],
        [InlineKeyboardButton(text="🏆 ТОП", callback_data="leaderboard")],
        [InlineKeyboardButton(text="📖 КАК РАБОТАЕТ", callback_data="help")]
    ])

# ================= ОБРАБОТЧИКИ =================
@dp.message(Command('start'))
async def cmd_start(message: types.Message):
    user = message.from_user
    user_id = user.id
    username = user.username or "no_username"
    first_name = user.first_name or "User"
    
    cursor.execute('INSERT OR IGNORE INTO users (user_id, username, first_name, balance, last_claim) VALUES (?, ?, ?, ?, ?)',
                   (user_id, username, first_name, 0, None))
    conn.commit()
    
    cooldown = get_cooldown(user_id)
    keyboard = get_main_keyboard(user_id, username)
    
    if cooldown:
        await message.answer(
            f"🔴 <b>Привет, {first_name}</b>\n"
            f"🆔 {user_id}\n"
            f"@{username}\n\n"
            f"⏳ <b>КД:</b> {cooldown // 3600}ч {(cooldown % 3600) // 60}м\n\n"
            f"Жди...",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"🟢 <b>Привет, {first_name}</b>\n"
            f"🆔 {user_id}\n"
            f"@{username}\n\n"
            f"✅ <b>ЖМИ КНОПКУ</b>\n"
            f"Забери свои 250к",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

@dp.callback_query(lambda c: c.data == "claim")
async def cmd_claim(callback: types.CallbackQuery):
    user = callback.from_user
    user_id = user.id
    
    cooldown = get_cooldown(user_id)
    if cooldown:
        await callback.answer(f"КД {cooldown // 3600}ч {(cooldown % 3600) // 60}м", show_alert=True)
        return
    
    total_bonus, multiplier = add_balance(user_id, user.username or "no_username", user.first_name or "User")
    
    rank = get_user_rank(user_id)
    user_data = get_user_data(user_id)
    
    bonus_text = "🔥 ДВОЙНОЙ" if multiplier == 2 else "💰 ОБЫЧНЫЙ"
    
    message_text = (
        f"✅ <b>Забрал {bonus_text} {total_bonus:,} ₽</b>\n\n"
        f"🏆 <b>Баланс:</b> {user_data['balance']:,} ₽\n"
        f"📊 <b>Всего бабок:</b> {user_data['total_claims']}\n\n"
        f"🕐 <i>Следующий через 1 час</i>"
    )
    
    if rank and rank > 1:
        phrases = [
            f"\n\n<b>Чо ты мешок, первым стать не мог чоле</b>",
            f"\n\n<b>Эй, {rank}-й, ну ты и мешок</b>",
            f"\n\n<b>Чо ты мешок, топ-1 не твой</b>"
        ]
        message_text += random.choice(phrases)
    elif rank == 1:
        message_text += f"\n\n<b>Ты первый! Держи корону</b>"
    
    # Обновляем клавиатуру (чтобы обновилась ссылка с параметрами)
    keyboard = get_main_keyboard(user_id, user.username or "no_username")
    
    await callback.message.edit_text(message_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer(f"+{total_bonus:,} ₽")

@dp.callback_query(lambda c: c.data == "leaderboard")
async def cmd_leaderboard(callback: types.CallbackQuery):
    user = callback.from_user
    top = get_leaderboard(10)
    
    if not top:
        await callback.answer("Пока никого нет", show_alert=True)
        return
    
    text = "🏆 <b>ТОП 10</b> 🏆\n\n"
    for i, (uid, uname, fname, balance, claims) in enumerate(top, 1):
        name = f"@{uname}" if uname and uname != "no_username" else fname
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "📌"
        text += f"{medal} {i}. {name} — {balance:,} ₽ (бабок: {claims})\n"
    
    keyboard = get_main_keyboard(user.id, user.username or "no_username")
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "help")
async def cmd_help(callback: types.CallbackQuery):
    user = callback.from_user
    help_text = (
        "📖 <b>КАК РАБОТАЕТ</b>\n\n"
        "💰 <b>КАК ЗАБРАТЬ 250К:</b>\n"
        "• ЖМИ КНОПКУ «ЗАБРАТЬ 250К»\n"
        "• ПОЛУЧАЙ БАБЛО\n"
        "• ЖДИ 1 ЧАС\n\n"
        "🔥 <b>ДВОЙНОЙ БОНУС:</b>\n"
        "ПЯТНИЦА 12:00 — ПН 12:00 (МСК)\n"
        "ЖИРНЫЙ ДВОЙНОЙ ЗАБОР!\n\n"
        "🏆 <b>ТОП:</b>\n"
        "КТО БОЛЬШЕ ВСЕГО ЗАБРАЛ — ТОТ ПЕРВЫЙ\n"
        "ОСТАЛЬНЫЕ — МЕШКИ"
    )
    keyboard = get_main_keyboard(user.id, user.username or "no_username")
    await callback.message.edit_text(help_text, parse_mode="HTML", reply_markup=keyboard)
    await callback.answer()

# ================= ЗАПУСК =================
async def main():
    print("🔥 NELFI DM - ФАРМ БОТ ЗАПУЩЕН")
    print(f"💰 БОНУС: {BONUS_AMOUNT:,} ₽")
    print("⏱️ КД: 1 ЧАС")
    print("🔥 ДВОЙНОЙ ПО ВЫХОДНЫМ")
    print(f"🌐 WEB APP: {WEBAPP_URL}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
