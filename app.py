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


# --- Статистика ---
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


def get_player(user_id, username):
    players = load_players()
    uid = str(user_id)
    if uid not in players:
        players[uid] = {
            "name": username,
            "total": 0,
            "wins": 0,
            "loses": 0,
            "draws": 0,
            "coins": 500,
            "breeds": {}
        }
        save_players(players)
    return players[uid]


def update_stats(user_id, username, breed_key, result):
    players = load_players()
    uid = str(user_id)

    if uid not in players:
        players[uid] = {
            "name": username, "total": 0, "wins": 0, "loses": 0,
            "draws": 0, "coins": 500, "breeds": {}
        }

    p = players[uid]
    p["name"] = username
    p["total"] += 1

    # Защита старых записей
    if "coins" not in p:
        p["coins"] = 500
    if "breeds" not in p:
        p["breeds"] = {}

    if result == "win":
        p["wins"] += 1
        p["coins"] += 100
    elif result == "lose":
        p["loses"] += 1
        p["coins"] = max(0, p["coins"] - 50)
    else:
        p["draws"] += 1
        p["coins"] += 50

    p["breeds"][breed_key] = p["breeds"].get(breed_key, 0) + 1

    save_players(players)


# --- Атмосфера ---
EVENTS = [
    "🐔 Петух разъярён! Следующий удар может быть сильнее.",
    "😤 Противник в ярости!",
    "💪 Боец собрался с силами!",
    "🌟 Удача на стороне бойца!",
    "🔥 Атмосфера на арене накаляется!",
    "👀 Толпа зрителей ревёт!",
    "💨 Пыль столбом на арене!",
    "⚡ Что-то невероятное происходит на ринге!",
]

COMMENTATOR = [
    "🎤 Комментатор: «Что происходит на ринге?!»",
    "🎤 Комментатор: «Это было мощно!»",
    "🎤 Комментатор: «Зрители в восторге!»",
    "🎤 Комментатор: «Бой набирает обороты!»",
]

VERBS = ["атаковал", "врезал", "ударил", "набросился на", "заехал по клюву"]


# --- Один удар ---
def make_hit(att, dfn):
    lines = []

    # Оглушение — пропуск хода
    if att.get("stunned", 0) > 0:
        att["stunned"] -= 1
        lines.append(f"😵 {att['title']} оглушён и пропускает ход!")
        return lines

    # Кровотечение
    if att.get("bleed", 0) > 0:
        att["cur_hp"] -= 2
        att["bleed"] -= 1
        lines.append(f"🩸 {att['title']} теряет 2 HP от кровотечения!")

    if att["cur_hp"] <= 0:
        return lines

    # Уклонение
    if random.random() < dfn["dodge"]:
        lines.append(f"🌀 {dfn['title']} увернулся!")
        return lines

    dmg = random.randint(att["dmg"][0], att["dmg"][1])

    # Броня Голема
    if dfn["key"] == "голем":
        dmg = max(1, dmg - 2)
        lines.append(f"🛡️ Броня Голема поглотила 2 урона.")

    # Ярость
    rage = False
    if att["cur_hp"] / att["hp"] < 0.3:
        dmg = int(dmg * 1.5)
        rage = True

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
    verb = random.choice(VERBS)

    if fire:
        lines.append(f"🔥 Дракон дыхнул огнём! {dmg} урона!")
    elif is_crit:
        lines.append(f"💥 КРИТ! {att['title']} {verb} {dfn['title']} на {dmg} урона!")
    elif rage:
        lines.append(f"😡 В ЯРОСТИ! {att['title']} {verb} {dfn['title']} на {dmg} урона!")
    else:
        lines.append(f"👊 {att['title']} {verb} {dfn['title']} на {dmg} урона.")

    lines.append(f"   У {dfn['title']} осталось: {max(0, dfn['cur_hp'])} HP")

    # Кровотечение от крита
    if is_crit:
        dfn["bleed"] = 2
        lines.append(f"🩸 {dfn['title']} начинает кровоточить!")

    # Оглушение от крита
    if is_crit and random.random() < 0.5:
        dfn["stunned"] = 1
        lines.append(f"😵 {dfn['title']} оглушён!")

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

    # Случайное событие
    if random.random() < 0.15:
        lines.append(f"   {random.choice(EVENTS)}")

    # Комментатор
    if random.random() < 0.10:
        lines.append(f"   {random.choice(COMMENTATOR)}")

    return lines


# --- Проверка смерти ---
def check_death(dfn, att):
    lines = []
    if dfn["cur_hp"] <= 0 and dfn["key"] == "феникс" and not dfn["revived"]:
        dfn["revived"] = True
        dfn["cur_hp"] = 6
        lines.append(f"🔥 ФЕНИКС ВОСКРЕС С 6 HP!")
        return lines, False

    if dfn["cur_hp"] <= 0 and dfn["key"] == "бомба" and not dfn.get("exploded"):
        dfn["exploded"] = True
        att["cur_hp"] -= 6
        lines.append(f"💥 БОМБА ВЗОРВАЛАСЬ! -6 HP врагу!")
        return lines, True

    return lines, dfn["cur_hp"] <= 0


# --- Обрезка лога ---
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


# --- Бой ---
async def run_fight_visual(message, p1_key, p2_key):
    p1 = {**BREEDS[p1_key], "key": p1_key, "cur_hp": BREEDS[p1_key]["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0}
    p2 = {**BREEDS[p2_key], "key": p2_key, "cur_hp": BREEDS[p2_key]["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0}

    log_text = (
        f"⚔️ **БОЙ НАЧАЛСЯ!**\n"
        f"Твой боец: **{p1['title']}** ({p1['hp']} HP)\n"
        f"Противник: **{p2['title']}** ({p2['hp']} HP)\n\n"
    )
    await message.edit_text(log_text, parse_mode="Markdown")

    for _ in range(15):
        for att, dfn in [(p1, p2), (p2, p1)]:
            if att["cur_hp"] <= 0:
                continue

            hit_lines = make_hit(att, dfn)
            log_text += "\n".join(hit_lines) + "\n"

            # Комбо
            if random.random() < 0.10 and att["cur_hp"] > 0 and dfn["cur_hp"] > 0:
                log_text += f"⚡ ДВОЙНОЙ УДАР! {att['title']} бьёт снова!\n"
                combo_lines = make_hit(att, dfn)
                log_text += "\n".join(combo_lines) + "\n"

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
        result = "win"
    elif p2["cur_hp"] > 0 and p1["cur_hp"] <= 0:
        winner_text = f"🏆 **ПОБЕДИЛ: {p2['title']}!**"
        result = "lose"
    else:
        winner_text = "🤝 **НИЧЬЯ! Бой затянулся.**"
        result = "draw"

    log_text += f"\n{winner_text}"
    try:
        await message.edit_text(log_text, parse_mode="Markdown")
    except Exception:
        pass

    return result


# --- Клавиатура петухов ---
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
    get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")
    await msg.answer(
        "🐔 **Петушиные бои**\n\nВыбери своего бойца для дуэли:",
        reply_markup=breeds_keyboard(),
        parse_mode="Markdown"
    )


# --- /profile ---
@dp.message(Command("profile"))
async def profile_cmd(msg: types.Message):
    p = get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")
    total = p["total"]
    winrate = round(p["wins"] / total * 100, 1) if total > 0 else 0
    favorite = "нет"
    if p.get("breeds"):
        fav_key = max(p["breeds"], key=p["breeds"].get)
        favorite = BREEDS[fav_key]["title"]

    coins = p.get("coins", 500)
    text = (
        f"📊 **Профиль: {p['name']}**\n\n"
        f"💰 Монеты: **{coins}**\n"
        f"Всего боёв: **{total}**\n"
        f"Побед: **{p['wins']}** ✅\n"
        f"Поражений: **{p['loses']}** ❌\n"
        f"Ничьих: **{p['draws']}** 🤝\n"
        f"Процент побед: **{winrate}%**\n"
        f"Любимый петух: **{favorite}**"
    )
    await msg.answer(text, parse_mode="Markdown")


# --- /top ---
@dp.message(Command("top"))
async def top_cmd(msg: types.Message):
    players = load_players()
    if not players:
        await msg.answer("📊 Пока никто не играл.")
        return

    sorted_players = sorted(players.values(), key=lambda x: x.get("wins", 0), reverse=True)[:10]

    text = "🏆 **ТОП-10 ИГРОКОВ**\n\n"
    for i, p in enumerate(sorted_players, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} **{p.get('name', 'Игрок')}** — {p.get('wins', 0)} побед, {p.get('coins', 0)} 💰\n"

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
