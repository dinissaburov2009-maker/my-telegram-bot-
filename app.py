import asyncio
import os
import random
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import BotCommand
from aiogram.utils.keyboard import InlineKeyboardBuilder

# -------------------------------------------------------------
TOKEN = os.environ.get('BOT_TOKEN')
# -------------------------------------------------------------

DATA_FILE = "/data/players.json"

BREEDS = {
    "обычная":  {"title": "Обычная",  "tier": "C", "hp": 15, "dmg": (2, 4), "crit": 0.10, "dodge": 0.05},
    "драчун":   {"title": "Драчун",   "tier": "C", "hp": 18, "dmg": (4, 7), "crit": 0.15, "dodge": 0.08},
    "бомба":    {"title": "Бомба",    "tier": "B", "hp": 15, "dmg": (5, 8), "crit": 0.16, "dodge": 0.08},
    "призрак":  {"title": "Призрак",  "tier": "B", "hp": 17, "dmg": (4, 6), "crit": 0.20, "dodge": 0.30},
    "вампир":   {"title": "Вампир",   "tier": "B", "hp": 22, "dmg": (3, 5), "crit": 0.17, "dodge": 0.09},
    "феникс":   {"title": "Феникс",   "tier": "A", "hp": 20, "dmg": (3, 5), "crit": 0.18, "dodge": 0.10},
    "дракон":   {"title": "Дракон",   "tier": "A", "hp": 20, "dmg": (3, 6), "crit": 0.18, "dodge": 0.08},
    "голем":    {"title": "Голем",    "tier": "S", "hp": 28, "dmg": (2, 3), "crit": 0.05, "dodge": 0.04},
    "губка":    {"title": "Губка",    "tier": "S", "hp": 26, "dmg": (2, 4), "crit": 0.10, "dodge": 0.06},
}

TIER_CHANCES = {"C": 40, "B": 30, "A": 20, "S": 10}

bot = Bot(token=TOKEN)
dp = Dispatcher()

ACTIVE_DUELS = {}
DUEL_COUNTER = [0]
DUEL_TIMEOUT_TASKS = {}


# =============================================================
# СТАТИСТИКА
# =============================================================
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
            "name": username, "total": 0, "wins": 0, "loses": 0,
            "coins": 500, "chicken": None,
        }
        save_players(players)
    p = players[uid]
    if "coins" not in p:
        p["coins"] = 500
    if "chicken" not in p:
        p["chicken"] = None
    return p


def save_player(user_id, data):
    players = load_players()
    players[str(user_id)] = data
    save_players(players)


def update_stats(user_id, username, result):
    players = load_players()
    uid = str(user_id)
    if uid not in players:
        players[uid] = {
            "name": username, "total": 0, "wins": 0, "loses": 0,
            "coins": 500, "chicken": None,
        }
    p = players[uid]
    p["name"] = username
    p["total"] += 1

    if "coins" not in p:
        p["coins"] = 500
    if "chicken" not in p:
        p["chicken"] = None

    if result == "win":
        p["wins"] += 1
        p["coins"] += 100
    else:
        p["loses"] += 1
        p["coins"] = max(0, p["coins"] - 50)
        p["chicken"] = None

    save_players(players)


# =============================================================
# АТМОСФЕРА
# =============================================================
EVENTS_POSITIVE = [
    "🍗 Семки! {title} подкрепился и восстановил 3 HP.",
    "🌟 {title} воодушевлён! Следующий удар будет сильнее.",
    "🍀 {title} нашёл клевер — уклонение повышено!",
    "🎺 Фанфары! {title} чувствует поддержку зрителей (+2 HP).",
    "⚡ {title} в ударе! Следующий удар x2.",
]

EVENTS_NEGATIVE = [
    "💨 Ветер сдул {title} — пропуск хода!",
    "👟 {title} поскользнулся — пропуск хода!",
    "🧱 Зритель бросил камень в {title} — 2 урона!",
    "😱 {title} испугался — пропуск хода!",
    "🌪️ Пыльная буря! {title} дезориентирован — пропуск хода.",
    "🪨 Камень с трибуны! {title} получает 4 урона.",
]

EVENTS_NEUTRAL = [
    "🔥 Арена загорелась! Оба петуха теряют 3 HP.",
    "💧 Дождь пошёл! Уклонение у всех повышено на ход.",
    "🐔 Кукареку! Все петухи слышат крик!",
    "🏃 {title} разбежался — следующий удар x2.",
    "⚡ Удар молнии! 5 урона случайному петуху.",
    "🎉 Зрители бросают цветы! Атмосфера накаляется!",
]

COMMENTATOR = [
    "🎤 Комментатор: «Что происходит на ринге?!»",
    "🎤 Комментатор: «Это было мощно!»",
    "🎤 Комментатор: «Зрители в восторге!»",
    "🎤 Комментатор: «Бой набирает обороты!»",
    "🎤 Комментатор: «Невероятный поворот событий!»",
    "🎤 Комментатор: «Это стоит увидеть!»",
]

VERBS = ["атаковал", "врезал", "ударил", "набросился на", "заехал по клюву"]


# =============================================================
# МЕХАНИКА УДАРОВ
# =============================================================
def make_hit(att, dfn, all_fighters):
    lines = []

    if att.get("stunned", 0) > 0:
        att["stunned"] -= 1
        lines.append(f"😵 {att['title']} оглушён и пропускает ход!")
        return lines

    if att.get("bleed", 0) > 0:
        att["cur_hp"] -= 2
        att["bleed"] -= 1
        lines.append(f"🩸 {att['title']} теряет 2 HP от кровотечения!")

    if att["cur_hp"] <= 0:
        return lines

    if random.random() < 0.20:
        roll = random.random()
        if roll < 0.33:
            ev = random.choice(EVENTS_POSITIVE).format(title=att["title"])
            if "восстановил 3 HP" in ev:
                att["cur_hp"] = min(att["hp"], att["cur_hp"] + 3)
            elif "Следующий удар будет сильнее" in ev:
                att["bonus_dmg"] = 1
            elif "уклонение повышено" in ev:
                att["dodge"] = min(0.9, att["dodge"] + 0.10)
            elif "+2 HP" in ev:
                att["cur_hp"] = min(att["hp"], att["cur_hp"] + 2)
            elif "Следующий удар x2" in ev:
                att["bonus_dmg"] = 2
            lines.append(f"   {ev}")
        elif roll < 0.66:
            ev = random.choice(EVENTS_NEGATIVE).format(title=att["title"])
            if "пропуск хода" in ev or "дезориентирован" in ev:
                att["stunned"] += 1
            elif "2 урона" in ev:
                att["cur_hp"] -= 2
            elif "4 урона" in ev:
                att["cur_hp"] -= 4
            lines.append(f"   {ev}")
        else:
            ev = random.choice(EVENTS_NEUTRAL).format(title=att["title"])
            if "теряют 3 HP" in ev:
                for fighter in all_fighters:
                    if fighter["cur_hp"] > 0:
                        fighter["cur_hp"] -= 3
            elif "Уклонение у всех" in ev:
                for fighter in all_fighters:
                    fighter["dodge"] = min(0.9, fighter["dodge"] + 0.05)
            elif "5 урона случайному" in ev:
                alive = [f for f in all_fighters if f["cur_hp"] > 0]
                if alive:
                    target = random.choice(alive)
                    target["cur_hp"] -= 5
            elif "следующий удар x2" in ev:
                att["bonus_dmg"] = 2
            lines.append(f"   {ev}")

        if att["cur_hp"] <= 0:
            return lines

    if random.random() < dfn["dodge"]:
        lines.append(f"🌀 {dfn['title']} увернулся!")
        return lines

    dmg = random.randint(att["dmg"][0], att["dmg"][1])

    if dfn.get("key") == "голем":
        dmg = max(1, dmg - 2)
        lines.append(f"🛡️ Броня Голема поглотила 2 урона.")

    rage = False
    if att["cur_hp"] / att["hp"] < 0.3 and not att.get("raged"):
        att["raged"] = True
        dmg = int(dmg * 1.5)
        rage = True

    is_crit = random.random() < att["crit"]
    if is_crit:
        dmg = int(dmg * 1.5)

    fire = False
    if att.get("key") == "дракон" and random.random() < 0.15:
        dmg *= 2
        fire = True

    if att.get("bonus_dmg"):
        dmg *= att["bonus_dmg"]
        att["bonus_dmg"] = 0

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

    if is_crit:
        dfn["bleed"] = 2
        lines.append(f"🩸 {dfn['title']} начинает кровоточить!")
        if random.random() < 0.5:
            dfn["stunned"] = 1
            lines.append(f"😵 {dfn['title']} оглушён!")

    if att.get("key") == "вампир" and dmg > 0:
        heal = max(1, int(dmg * 0.25))
        att["cur_hp"] = min(att["hp"], att["cur_hp"] + heal)
        lines.append(f"🩸 Вампир восстановил +{heal} HP!")

    if att.get("key") == "губка":
        att["cur_hp"] = min(att["hp"], att["cur_hp"] + 2)
        lines.append(f"💚 Губка регенерировала +2 HP!")

    att["hits"] = att.get("hits", 0) + 1
    if att.get("key") == "каратель" and att["hits"] % 2 == 0:
        dfn["cur_hp"] -= 5
        lines.append(f"💣 МЕТКА КАРАТЕЛЯ СДЕТОНИРОВАЛА! -5 HP!")

    if random.random() < 0.10:
        lines.append(f"   {random.choice(COMMENTATOR)}")

    return lines


def check_death(dfn, att):
    lines = []
    if dfn["cur_hp"] <= 0 and dfn.get("key") == "феникс" and not dfn.get("revived"):
        dfn["revived"] = True
        dfn["cur_hp"] = 6
        lines.append(f"🔥 ФЕНИКС ВОСКРЕС С 6 HP!")
        return lines, False

    if dfn["cur_hp"] <= 0 and dfn.get("key") == "бомба" and not dfn.get("exploded"):
        dfn["exploded"] = True
        att["cur_hp"] -= 6
        lines.append(f"💥 БОМБА ВЗОРВАЛАСЬ! -6 HP врагу!")
        return lines, True

    return lines, dfn["cur_hp"] <= 0


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


# =============================================================
# PVP БОЙ
# =============================================================
async def run_pvp_fight(chat_id, p1_key, p2_key, name1, name2):
    b1 = BREEDS[p1_key]
    b2 = BREEDS[p2_key]
    p1 = {**b1, "key": p1_key, "cur_hp": b1["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0,
          "raged": False, "bonus_dmg": 0, "name": name1}
    p2 = {**b2, "key": p2_key, "cur_hp": b2["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0,
          "raged": False, "bonus_dmg": 0, "name": name2}

    all_fighters = [p1, p2]

    log_text = (
        f"⚔️ **PVP БОЙ НАЧАЛСЯ!**\n"
        f"🐔 {name1}: **{p1['title']}** ({p1['hp']} HP)\n"
        f"🐔 {name2}: **{p2['title']}** ({p2['hp']} HP)\n\n"
    )
    try:
        msg = await bot.send_message(chat_id, log_text, parse_mode="Markdown")
    except Exception:
        return "win_p1"

    for _ in range(50):
        for att, dfn in [(p1, p2), (p2, p1)]:
            if att["cur_hp"] <= 0 or dfn["cur_hp"] <= 0:
                continue

            hit_lines = make_hit(att, dfn, all_fighters)
            log_text += "\n".join(hit_lines) + "\n"

            if random.random() < 0.10 and att["cur_hp"] > 0 and dfn["cur_hp"] > 0:
                log_text += f"⚡ ДВОЙНОЙ УДАР! {att['title']} бьёт снова!\n"
                combo_lines = make_hit(att, dfn, all_fighters)
                log_text += "\n".join(combo_lines) + "\n"

            death_lines, is_dead = check_death(dfn, att)
            if death_lines:
                log_text += "\n".join(death_lines) + "\n"

            log_text = trim_log(log_text)
            try:
                await msg.edit_text(log_text, parse_mode="Markdown")
            except Exception:
                pass
            await asyncio.sleep(1.2)

            if is_dead or att["cur_hp"] <= 0 or dfn["cur_hp"] <= 0:
                break

        if p1["cur_hp"] <= 0 or p2["cur_hp"] <= 0:
            break

    p1_alive = p1["cur_hp"] > 0
    p2_alive = p2["cur_hp"] > 0

    if p1_alive and not p2_alive:
        winner_text = f"🏆 **ПОБЕДИЛ: {name1} ({p1['title']})!**"
        result = "win_p1"
    elif p2_alive and not p1_alive:
        winner_text = f"🏆 **ПОБЕДИЛ: {name2} ({p2['title']})!**"
        result = "win_p2"
    else:
        if p1["cur_hp"] >= p2["cur_hp"]:
            winner_text = f"🏆 **ПОБЕДИЛ: {name1} ({p1['title']})!**"
            result = "win_p1"
        else:
            winner_text = f"🏆 **ПОБЕДИЛ: {name2} ({p2['title']})!**"
            result = "win_p2"

    log_text += f"\n{winner_text}"
    try:
        await msg.edit_text(log_text, parse_mode="Markdown")
    except Exception:
        pass

    return result


# =============================================================
# МАГАЗИН
# =============================================================
def roll_random_chicken():
    roll = random.randint(1, 100)
    if roll <= TIER_CHANCES["C"]:
        pool = [k for k, v in BREEDS.items() if v["tier"] == "C"]
    elif roll <= TIER_CHANCES["C"] + TIER_CHANCES["B"]:
        pool = [k for k, v in BREEDS.items() if v["tier"] == "B"]
    elif roll <= TIER_CHANCES["C"] + TIER_CHANCES["B"] + TIER_CHANCES["A"]:
        pool = [k for k, v in BREEDS.items() if v["tier"] == "A"]
    else:
        pool = [k for k, v in BREEDS.items() if v["tier"] == "S"]
    return random.choice(pool)


# =============================================================
# КОМАНДЫ
# =============================================================
@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    p = get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")

    if not p.get("chicken"):
        await msg.answer(
            "🐔 **Петушиные бои**\n\n"
            "У тебя нет петуха. Купи его в магазине: /shop",
            parse_mode="Markdown"
        )
        return

    breed = BREEDS[p["chicken"]]
    kb = InlineKeyboardBuilder()
    kb.button(
        text=f"⚔️ В бой: {breed['title']} ({breed['hp']} HP)",
        callback_data=f"fight:{p['chicken']}"
    )
    kb.adjust(1)
    await msg.answer(
        f"🐔 **Петушиные бои**\n\n"
        f"Твой петух: **{breed['title']}**\n"
        f"HP: {breed['hp']}\n\n"
        f"Вызывай других игроков в группе командой /duel (ответь на их сообщение)",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


@dp.message(Command("chicken"))
async def chicken_cmd(msg: types.Message):
    p = get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")

    if not p.get("chicken"):
        await msg.answer("🐔 У тебя нет петуха. Купи в /shop")
        return

    breed = BREEDS[p["chicken"]]
    kb = InlineKeyboardBuilder()
    kb.button(text="🍲 Пустить на суп (стоит 100 монет)", callback_data="soup")
    kb.adjust(1)

    await msg.answer(
        f"🐔 **Твой петух:**\n\n"
        f"**{breed['title']}**\n"
        f"HP: {breed['hp']}\n"
        f"Урон: {breed['dmg'][0]}–{breed['dmg'][1]}\n"
        f"Крит: {int(breed['crit']*100)}%\n"
        f"Уклонение: {int(breed['dodge']*100)}%",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "soup")
async def soup_action(call: types.CallbackQuery):
    p = get_player(call.from_user.id, call.from_user.first_name or "Игрок")
    if not p.get("chicken"):
        await call.answer("У тебя нет петуха.", show_alert=True)
        return

    if p.get("coins", 0) < 100:
        await call.answer("Недостаточно монет! Нужно 100.", show_alert=True)
        return

    p["chicken"] = None
    p["coins"] -= 100
    save_player(call.from_user.id, p)

    await call.message.edit_text("🍲 Ты пустил петуха на суп за 100 монет.")
    await call.answer()


@dp.message(Command("shop"))
async def shop_cmd(msg: types.Message):
    p = get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")

    if p.get("chicken"):
        await msg.answer("🛒 У тебя уже есть петух. Сначала продай его командой /chicken")
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Купить петуха за 50 монет", callback_data="buy")
    kb.adjust(1)

    await msg.answer(
        f"🛒 **Магазин петухов**\n\n"
        f"💰 У тебя: **{p['coins']} монет**\n\n"
        f"За 50 монет ты получишь **случайного** петуха.",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


@dp.callback_query(lambda c: c.data == "buy")
async def buy_action(call: types.CallbackQuery):
    p = get_player(call.from_user.id, call.from_user.first_name or "Игрок")

    if p.get("chicken"):
        await call.answer("У тебя уже есть петух!", show_alert=True)
        return

    if p["coins"] < 50:
        await call.answer("Недостаточно монет!", show_alert=True)
        return

    key = roll_random_chicken()
    p["coins"] -= 50
    p["chicken"] = key
    save_player(call.from_user.id, p)

    breed = BREEDS[key]
    await call.message.edit_text(
        f"🎉 **Тебе выпал петух: {breed['title']}!**\n\n"
        f"HP: {breed['hp']}\n"
        f"Урон: {breed['dmg'][0]}–{breed['dmg'][1]}\n\n"
        f"Проверь его: /chicken",
        parse_mode="Markdown"
    )
    await call.answer()


@dp.message(Command("profile"))
async def profile_cmd(msg: types.Message):
    p = get_player(msg.from_user.id, msg.from_user.first_name or "Игрок")
    total = p["total"]
    winrate = round(p["wins"] / total * 100, 1) if total > 0 else 0

    chicken_name = "нет"
    if p.get("chicken"):
        chicken_name = BREEDS[p["chicken"]]["title"]

    text = (
        f"📊 **Профиль: {p['name']}**\n\n"
        f"💰 Монеты: **{p['coins']}**\n"
        f"🐔 Петух: **{chicken_name}**\n"
        f"Всего боёв: **{total}**\n"
        f"Побед: **{p['wins']}** ✅\n"
        f"Поражений: **{p['loses']}** ❌\n"
        f"Процент побед: **{winrate}%**"
    )
    await msg.answer(text, parse_mode="Markdown")


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


# =============================================================
# /duel — вызов в группе
# =============================================================
@dp.message(Command("duel"))
async def duel_cmd(msg: types.Message):
    if msg.chat.type not in ("group", "supergroup"):
        await msg.reply("❌ Вызовы доступны только в группе.")
        return

    caller = msg.from_user
    caller_p = get_player(caller.id, caller.first_name or "Игрок")

    if not caller_p.get("chicken"):
        await msg.reply("❌ У тебя нет петуха. Купи в /shop (в личке).")
        return

    target = None
    if msg.reply_to_message and msg.reply_to_message.from_user:
        target = msg.reply_to_message.from_user
    else:
        await msg.reply("❌ Ответь на сообщение игрока командой /duel, чтобы вызвать его.")
        return

    if target.id == caller.id:
        await msg.reply("❌ Нельзя вызвать самого себя!")
        return

    if target.is_bot:
        await msg.reply("❌ Нельзя вызвать бота!")
        return

    target_p = get_player(target.id, target.first_name or "Игрок")
    if not target_p.get("chicken"):
        await msg.reply(f"❌ У {target.first_name} нет петуха.")
        return

    for duel_id_check, duel_check in list(ACTIVE_DUELS.items()):
        if duel_check["caller_id"] == caller.id:
            await msg.reply("❌ У тебя уже есть активный вызов.")
            return

    DUEL_COUNTER[0] += 1
    duel_id = DUEL_COUNTER[0]
    ACTIVE_DUELS[duel_id] = {
        "caller_id": caller.id,
        "caller_name": caller.first_name or "Игрок",
        "target_id": target.id,
        "target_name": target.first_name or "Игрок",
        "chat_id": msg.chat.id,
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data=f"accept:{duel_id}")
    kb.button(text="❌ Отказаться", callback_data=f"decline:{duel_id}")
    kb.button(text="🚫 Отменить вызов", callback_data=f"cancel:{duel_id}")
    kb.adjust(2, 1)

    duel_msg = await msg.reply(
        f"⚔️ **{caller.first_name} вызывает {target.first_name} на бой!**\n\n"
        f"🐔 {caller.first_name}: {BREEDS[caller_p['chicken']]['title']}\n"
        f"🐔 {target.first_name}: {BREEDS[target_p['chicken']]['title']}\n\n"
        f"⏳ Вызов снимется автоматически через 2 минуты.",
        reply_markup=kb.as_markup(),
        parse_mode="Markdown"
    )


    ACTIVE_DUELS[duel_id]["msg_id"] = duel_msg.message_id

    task = asyncio.create_task(duel_timeout(duel_id))
    DUEL_TIMEOUT_TASKS[duel_id] = task


async def duel_timeout(duel_id):
    await asyncio.sleep(120)
    if duel_id in ACTIVE_DUELS:
        duel = ACTIVE_DUELS[duel_id]
        try:
            await bot.send_message(
                duel["chat_id"],
                f"⏰ Вызов между {duel['caller_name']} и {duel['target_name']} снят (истекло время)."
            )
        except Exception:
            pass
        del ACTIVE_DUELS[duel_id]
        DUEL_TIMEOUT_TASKS.pop(duel_id, None)


@dp.callback_query(lambda c: c.data.startswith("accept:"))
async def duel_accept(call: types.CallbackQuery):
    duel_id = int(call.data.split(":")[1])
    if duel_id not in ACTIVE_DUELS:
        await call.answer("Вызов уже неактуален.", show_alert=True)
        return

    duel = ACTIVE_DUELS[duel_id]
    if call.from_user.id != duel["target_id"]:
        await call.answer("Это не твой вызов!", show_alert=True)
        return

    caller_p = get_player(duel["caller_id"], duel["caller_name"])
    target_p = get_player(duel["target_id"], duel["target_name"])

    if not caller_p.get("chicken"):
        await call.message.edit_text(f"❌ У {duel['caller_name']} больше нет петуха. Бой отменён.")
        del ACTIVE_DUELS[duel_id]
        DUEL_TIMEOUT_TASKS.pop(duel_id, None)
        await call.answer()
        return

    if not target_p.get("chicken"):
        await call.message.edit_text(f"❌ У {duel['target_name']} больше нет петуха. Бой отменён.")
        del ACTIVE_DUELS[duel_id]
        DUEL_TIMEOUT_TASKS.pop(duel_id, None)
        await call.answer()
        return

    del ACTIVE_DUELS[duel_id]
    DUEL_TIMEOUT_TASKS.pop(duel_id, None)

    await call.message.edit_text(
        f"⚔️ **Бой принят!**\n\n"
        f"🐔 {duel['caller_name']}: {BREEDS[caller_p['chicken']]['title']}\n"
        f"🐔 {duel['target_name']}: {BREEDS[target_p['chicken']]['title']}\n\n"
        f"⏳ Бой начинается..."
    )
    await call.answer()

    result = await run_pvp_fight(
        duel["chat_id"],
        caller_p["chicken"],
        target_p["chicken"],
        duel["caller_name"],
        duel["target_name"],
    )

    if result == "win_p1":
        update_stats(duel["caller_id"], duel["caller_name"], "win")
        update_stats(duel["target_id"], duel["target_name"], "lose")
    else:
        update_stats(duel["caller_id"], duel["caller_name"], "lose")
        update_stats(duel["target_id"], duel["target_name"], "win")


@dp.callback_query(lambda c: c.data.startswith("decline:"))
async def duel_decline(call: types.CallbackQuery):
    duel_id = int(call.data.split(":")[1])
    if duel_id not in ACTIVE_DUELS:
        await call.answer("Вызов уже неактуален.", show_alert=True)
        return

    duel = ACTIVE_DUELS[duel_id]
    if call.from_user.id != duel["target_id"]:
        await call.answer("Это не твой вызов!", show_alert=True)
        return

    del ACTIVE_DUELS[duel_id]
    DUEL_TIMEOUT_TASKS.pop(duel_id, None)
    await call.message.edit_text(f"❌ {duel['target_name']} отказался от боя.")
    await call.answer()


@dp.callback_query(lambda c: c.data.startswith("cancel:"))
async def duel_cancel(call: types.CallbackQuery):
    duel_id = int(call.data.split(":")[1])
    if duel_id not in ACTIVE_DUELS:
        await call.answer("Вызов уже неактуален.", show_alert=True)
        return

    duel = ACTIVE_DUELS[duel_id]
    if call.from_user.id != duel["caller_id"]:
        await call.answer("Только вызывающий может отменить вызов!", show_alert=True)
        return

    del ACTIVE_DUELS[duel_id]
    DUEL_TIMEOUT_TASKS.pop(duel_id, None)
    await call.message.edit_text(f"🚫 {duel['caller_name']} отменил вызов.")
    await call.answer()


@dp.callback_query(lambda c: c.data.startswith("fight:"))
async def fight_action(call: types.CallbackQuery):
    p = get_player(call.from_user.id, call.from_user.first_name or "Игрок")
    my_pick = call.data.split(":")[1]

    if p.get("chicken") != my_pick:
        await call.answer("Это не твой петух!", show_alert=True)
        return

    enemy_pick = random.choice(list(BREEDS.keys()))

    await call.message.edit_text("⏳ *Бой начинается...*", parse_mode="Markdown")

    b1 = BREEDS[my_pick]
    b2 = BREEDS[enemy_pick]
    p1 = {**b1, "key": my_pick, "cur_hp": b1["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0,
          "raged": False, "bonus_dmg": 0, "name": "Ты"}
    p2 = {**b2, "key": enemy_pick, "cur_hp": b2["hp"], "hits": 0,
          "revived": False, "exploded": False, "bleed": 0, "stunned": 0,
          "raged": False, "bonus_dmg": 0, "name": "Враг"}

    all_fighters = [p1, p2]

    log_text = (
        f"⚔️ **БОЙ НАЧАЛСЯ!**\n"
        f"Твой боец: **{p1['title']}** ({p1['hp']} HP)\n"
        f"Противник: **{p2['title']}** ({p2['hp']} HP)\n\n"
    )
    try:
        await call.message.edit_text(log_text, parse_mode="Markdown")
    except Exception:
        pass

    for _ in range(50):
        for att, dfn in [(p1, p2), (p2, p1)]:
            if att["cur_hp"] <= 0 or dfn["cur_hp"] <= 0:
                continue

            hit_lines = make_hit(att, dfn, all_fighters)
            log_text += "\n".join(hit_lines) + "\n"

            if random.random() < 0.10 and att["cur_hp"] > 0 and dfn["cur_hp"] > 0:
                log_text += f"⚡ ДВОЙНОЙ УДАР! {att['title']} бьёт снова!\n"
                combo_lines = make_hit(att, dfn, all_fighters)
                log_text += "\n".join(combo_lines) + "\n"

            death_lines, is_dead = check_death(dfn, att)
            if death_lines:
                log_text += "\n".join(death_lines) + "\n"

            log_text = trim_log(log_text)
            try:
                await call.message.edit_text(log_text, parse_mode="Markdown")
            except Exception:
                pass
            await asyncio.sleep(1.2)

            if is_dead or att["cur_hp"] <= 0 or dfn["cur_hp"] <= 0:
                break

        if p1["cur_hp"] <= 0 or p2["cur_hp"] <= 0:
            break

    p1_alive = p1["cur_hp"] > 0
    p2_alive = p2["cur_hp"] > 0

    if p1_alive and not p2_alive:
        winner_text = f"🏆 **ПОБЕДИЛ: {p1['title']}!**"
        result = "win"
    elif p2_alive and not p1_alive:
        winner_text = f"🏆 **ПОБЕДИЛ: {p2['title']}!**"
        result = "lose"
    else:
        if p1["cur_hp"] >= p2["cur_hp"]:
            winner_text = f"🏆 **ПОБЕДИЛ: {p1['title']}!**"
            result = "win"
        else:
            winner_text = f"🏆 **ПОБЕДИЛ: {p2['title']}!**"
            result = "lose"

    log_text += f"\n{winner_text}"
    try:
        await call.message.edit_text(log_text, parse_mode="Markdown")
    except Exception:
        pass

    update_stats(call.from_user.id, call.from_user.first_name or "Игрок", result)

    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сразиться снова", callback_data="again")
    kb.adjust(1)
    try:
        await call.message.edit_reply_markup(reply_markup=kb.as_markup())
    except Exception:
        pass
    await call.answer()


@dp.callback_query(lambda c: c.data == "again")
async def again_action(call: types.CallbackQuery):
    await start_cmd(call.message)
    await call.answer()


async def set_commands():
    commands = [
        BotCommand(command="start", description="Начать бой"),
        BotCommand(command="chicken", description="Мой петух"),
        BotCommand(command="shop", description="Магазин петухов"),
        BotCommand(command="duel", description="Вызвать игрока (в группе, ответом)"),
        BotCommand(command="profile", description="Профиль"),
        BotCommand(command="top", description="Топ игроков"),
    ]
    await bot.set_my_commands(commands)


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
