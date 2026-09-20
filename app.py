import asyncio
import os
import random
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# -------------------------------------------------------------
TOKEN = os.environ.get('BOT_TOKEN')
# -------------------------------------------------------------

DATA_FILE = "/data/players.json"

BREEDS = {
    "феникс":   {"title": "Феникс",   "class": "Универсал", "hp": 13, "dmg": (3, 5), "crit": 0.18, "dodge": 0.10},
    "каратель": {"title": "Каратель", "class": "Дамагер",   "hp": 12, "dmg": (4, 7), "crit": 0.20, "dodge": 0.10},
    "губка":    {"title": "Губка",    "class": "Танк",      "hp": 18, "dmg": (2, 4), "crit": 0.10, "dodge": 0.06},
    "вампир":   {"title": "Вампир",   "class": "Хилер",     "hp": 14, "dmg": (3, 5), "crit": 0.17, "dodge": 0.09},
    "бомба":    {"title": "Бомба",    "class": "Дамагер",   "hp": 10, "dmg": (5, 8), "crit": 0.16, "dodge": 0.08},
    "дракон":   {"title": "Дракон",   "class": "Дамагер",   "hp": 13, "dmg": (3, 6), "crit": 0.18, "dodge": 0.08},
    "голем":    {"title": "Голем",    "class": "Танк",      "hp": 20, "dmg": (2, 3), "crit": 0.05, "dodge": 0.04},
    "призрак":  {"title": "Призрак",  "class": "Универсал", "hp": 11, "dmg": (4, 6), "crit": 0.20, "dodge": 0.30},
}

bot = Bot(token=TOKEN)
dp = Dispatcher()


# --- Загрузка / сохранение статистики ---
def load_players():
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_players(data):
    try:
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


# --- Один удар ---
def make_hit(att, dfn):
    lines = []

    # Уклонение
    if random.random() < dfn["dodge"]:
        lines.append(f"🌀 {dfn['title']} увернулся!")
        return lines

    # Базовый урон
    dmg = random.randint(att["dmg"][0], att["dmg"][1])

    # Броня Голема
    if dfn["key"] == "голем":
        dmg = max(1, dmg - 2)
        lines.append(f"🛡️ Броня Голема поглотила 2 урона.")

    # Крит
    is_crit = random.random() < att["crit"]
    if is_crit:
        dmg = int(dmg * 1.5)

    # Огненное дыхание Дракона
    fire = False
    if att["key"] == "дракон" and random.random() < 0.15:
        dmg *= 2
        fire = True

    dfn["cur_hp"] -= dmg

    # Строка удара
    if fire:
        lines.append(f"🔥 Дракон дыхнул огнём! {dmg} урона!")
    elif is_crit:
        lines.append(f"💥 КРИТ! {att['title']} нанёс {dmg} урона!")
    else:
        lines.append(f"👊 {att['title']} нанёс {dmg} урона.")

    lines.append(f"   У {dfn['title']} осталось: {max(0, dfn['cur_hp'])} HP")

    # Вампиризм
    if att["key"] == "вампир" and dmg > 0:
        heal = max(1, int(dmg * 0.25))
        att["cur_hp"] = min(att["hp"], att["cur_hp"] + heal)
        lines.append(f"🩸 Вампир восстановил +{heal} HP!")

    # Регенерация Губки
    if att["key"] == "губка":
        att["cur_hp"] = min(att["hp"], att["cur_hp"] + 2)
        lines.append(f"💚 Губка регенерировала +2 HP!")

    # Метка Карателя
    att["hits"] += 1
    if att["key"] == "каратель" and att["hits"] % 2 == 0:
        dfn["cur_hp"] -= 12
        lines.append(f"💣 МЕТКА КАРАТЕЛЯ СДЕТОНИРОВАЛА! -12 HP!")

    return lines


# --- Проверка пассивок при смерти ---
def check_death(dfn, att):
    lines = []
    # Феникс воскресает
    if dfn["cur_hp"] <= 0 and dfn["key"] == "феникс" and not dfn["revived"]:
        dfn["revived"] = True
        dfn["cur_hp"] = 6
        lines.append(f"🔥 ФЕНИКС ВОСКРЕС С 6 HP!")
        return lines, False

    # Бомба взрывается
    if dfn["cur_hp"] <= 0 and dfn["key"] == "бомба" and not dfn.get("exploded"):
        dfn["exploded"] = True
        att["cur_hp"] -= 6
        lines.append(f"💥 БОМБА ВЗОРВАЛАСЬ! -6 HP врагу!")
        return lines, True

    return lines, dfn["cur_hp"] <= 0


# --- Безопасная обрезка лога ---
def trim_log(log_text, max_len=3800):
    if len(log_text) <= max_len:
        return log_text
    lines = log_text.split("\n")
    result = []
    total = 0
    for line in reversed(lines):
        if total + len(line) + 1 > max_len - 200:
            break
        result.insert(0, line)
        total += len(line) + 1
    return "...(лог сокращён)...\n" + "\n".join(result)


# --- Основной бой ---
async def run_fight_visual(message, p1_key, p2_key):
    p1 = {**BREEDS[p1_key], "key": p1_key, "cur_hp": BREEDS[p1_key]["hp"], "hits": 0, "revived": False, "exploded": False}
    p2 = {**BREEDS[p2_key], "key": p2_key, "cur_hp": BREEDS[p2_key]["hp"], "hits": 0, "revived": False, "exploded": False}

    log_text = (
        f"⚔️ **БОЙ НАЧАЛСЯ!**\n"
        f"Твой боец: **{p1['title']}** ({p1['hp']} HP)\n"
        f"Противник: **{p2['title']}** ({p2['hp']} HP)\n\n"
    )
    await message.edit_text(log_text, parse_mode="Markdown")

    turn = 0
    max_turns = 15

    for _ in range(max_turns):
        for att, dfn in [(p1, p2), (p2, p1)]:
            if att["cur_hp"] <= 0:
                continue
            turn += 1

            hit_lines = make_hit(att, dfn)
            log_text += "\n".join(hit_lines) + "\n"

            death_lines, is_dead = check_death(dfn, att)
            if death_lines:
                log_text += "\n".join(death_lines) + "\n"

            log_text = trim_log(log_text)

            try:
                await message.edit_text(log_text, parse_mode="Markdown")
            except Exception:
                pass

            await asyncio.sleep(1.2)

            if is_dead or p1["cur_hp"] <= 0 or p2["cur_hp"] <= 0:
                break

        if p1["cur_hp"] <= 0 or p2["cur_hp"] <= 0:
            break

    # Итог
    if p1["cur_hp"] > 0 and p2["cur_hp"] <= 0:
        winner_text = f"🏆 **ПОБЕДИЛ: {p1['title']}!**"
        result_for_save = "win"
    elif p2["cur_hp"] > 0 and p1["cur_hp"] <= 0:
        winner_text = f"🏆 **ПОБЕДИЛ: {p2['title']}!**"
        result_for_save = "lose"
    else:
        winner_text = "🤝 **НИЧЬЯ! Бой затянулся.**"
        result_for_save = "draw"

    log_text += f"\n{winner_text}"
    try:
        await message.edit_text(log_text, parse_mode="Markdown")
    except Exception:
        pass

    return result_for_save


# --- Сохранение статистики ---
def update_stats(user_id, username, breed_key, result):
    players = load_players()
    uid = str(user_id)

    if uid not in players:
        players[uid] = {
            "name": username,
            "total": 0,
            "wins": 0,
            "loses": 0,
            "draws": 0,
            "breeds": {}
        }

    p = players[uid]
    p["name"] = username
    p["total"] += 1

    if result == "win":
        p["wins"] += 1
    elif result == "lose":
        p["loses"] += 1
    else:
        p["draws"] += 1

    p["breeds"][breed_key] = p["breeds"].get(breed_key, 0) + 1

    save_players(players)


# --- Клавиатура выбора петуха ---
def breeds_keyboard():
    kb = InlineKeyboardBuilder()
    for key, data in BREEDS.items():
        kb.button(
            text=f"{data['title']} ({data['class']}, {data['hp']} HP)",
            callback_data=f"fight:{key}"
        )
    kb.adjust(1)
    return kb.as_markup()


# --- /start ---
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    await msg.answer(
        "🐔 **Петушиные бои**\n\nВыбери своего бойца для дуэли:",
        reply_markup=breeds_keyboard(),
        parse_mode="Markdown"
    )


# --- /profile ---
@dp.message(Command("profile"))
async def profile_cmd(msg: types.Message):
    players = load_players()
    uid = str(msg.from_user.id)

    if uid not in players:
        await msg.answer("📊 Ты ещё не сражался ни разу. Напиши /start, чтобы начать!")
        return

    p = players[uid]
    total = p["total"]
    wins = p["wins"]
    loses = p["loses"]
    draws = p["draws"]
    winrate = round(wins / total * 100, 1) if total > 0 else 0

    favorite = "нет"
    if p["breeds"]:
        fav_key = max(p["breeds"], key=p["breeds"].get)
        favorite = BREEDS[fav_key]["title"]

    text = (
        f"📊 **Профиль: {p['name']}**\n\n"
        f"Всего боёв: **{total}**\n"
        f"Побед: **{wins}** ✅\n"
        f"Поражений: **{loses}** ❌\n"
        f"Ничьих: **{draws}** 🤝\n"
        f"Процент побед: **{winrate}%**\n"
        f"Любимый петух: **{favorite}**"
    )
    await msg.answer(text, parse_mode="Markdown")


# --- Бой ---
@dp.callback_query(lambda c: c.data.startswith("fight:"))
async def fight_action(call: types.CallbackQuery):
    my_pick = call.data.split(":")[1]
    enemy_pick = random.choice(list(BREEDS.keys()))

    await call.message.edit_text("⏳ *Бой начинается...*", parse_mode="Markdown")

    result = await run_fight_visual(call.message, my_pick, enemy_pick)

    update_stats(
        call.from_user.id,
        call.from_user.first_name or "Игрок",
        my_pick,
        result
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сразиться снова", callback_data="again")
    try:
        await call.message.edit_reply_markup(reply_markup=kb.as_markup())
    except Exception:
        pass
    await call.answer()


# --- Сразиться снова ---
@dp.callback_query(lambda c: c.data == "again")
async def again_action(call: types.CallbackQuery):
    try:
        await call.message.edit_text(
            "🐔 **Петушиные бои**\n\nВыбери своего бойца для дуэли:",
            reply_markup=breeds_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await call.answer()


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
