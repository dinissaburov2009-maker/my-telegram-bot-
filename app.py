import asyncio
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# -------------------------------------------------------------
# ВСТАВЬ СВОЙ ТОКЕН МЕЖДУ КАВЫЧКАМИ НИЖЕ:
TOKEN = "СЮДА_ВСТАВЬ_ТОКЕН_ОТ_BOTFATHER"
# -------------------------------------------------------------

# База данных птиц с их пассивками
BREEDS = {
    "феникс": {"title": "Феникс", "hp": 13, "dmg": (3, 5), "crit": 0.18, "dodge": 0.10},
    "каратель": {"title": "Каратель", "hp": 13, "dmg": (3, 6), "crit": 0.20, "dodge": 0.10},
    "губка": {"title": "Губка", "hp": 15, "dmg": (2, 4), "crit": 0.10, "dodge": 0.06},
    "вампир": {"title": "Вампир", "hp": 13, "dmg": (3, 5), "crit": 0.17, "dodge": 0.09},
    "бомба": {"title": "Бомба", "hp": 11, "dmg": (3, 5), "crit": 0.16, "dodge": 0.08}
}

bot = Bot(token=TOKEN)
dp = Dispatcher()

def run_fight(p1_key, p2_key):
    p1 = {**BREEDS[p1_key], "cur_hp": BREEDS[p1_key]["hp"], "hits": 0, "revived": False}
    p2 = {**BREEDS[p2_key], "cur_hp": BREEDS[p2_key]["hp"], "hits": 0, "revived": False}
    
    log = [f"⚔️ **БОЙ НАЧАЛСЯ!**\nТвой боец: **{p1['title']}** ({p1['hp']} HP)\nПротивник: **{p2['title']}** ({p2['hp']} HP)\n"]
    
    for _ in range(25):
        for att, dfn in [(p1, p2), (p2, p1)]:
            if att["cur_hp"] <= 0:
                continue

            if random.random() < dfn["dodge"]:
                log.append(f"🌀 {dfn['title']} увернулся!")
                continue

            dmg = random.randint(att["dmg"][0], att["dmg"][1])
            is_crit = random.random() < att["crit"]
            if is_crit:
                dmg = int(dmg * 1.5)
            
            dfn["cur_hp"] -= dmg
            att["hits"] += 1
            crit_txt = " 💥 (КРИТ!)" if is_crit else ""
            log.append(f"👊 {att['title']} нанёс {dmg} урона{crit_txt}. (У {dfn['title']} осталось: {max(0, dfn['cur_hp'])} HP)")

            # Пассивка: Вампиризм
            if att["title"] == "Вампир":
                heal = max(1, int(dmg * 0.25))
                att["cur_hp"] = min(att["hp"], att["cur_hp"] + heal)
                log.append(f"🩸 Вампир восстановил +{heal} HP!")

            # Пассивка: Метка Карателя (-12 урона за 2 удара)
            if att["title"] == "Каратель" and att["hits"] % 2 == 0:
                dfn["cur_hp"] -= 12
                log.append(f"💣 **МЕТКА СДЕТОНИРОВАЛА! -12 УРОНА!**")

            # Пассивка: Феникс восстаёт
            if dfn["cur_hp"] <= 0 and dfn["title"] == "Феникс" and not dfn["revived"]:
                dfn["revived"] = True
                dfn["cur_hp"] = 6
                log.append(f"🔥 **ФЕНИКС ВОСКРЕС С 6 HP!**")

            # Пассивка: Взрыв Бомбы при смерти
            if dfn["cur_hp"] <= 0 and dfn["title"] == "Бомба":
                att["cur_hp"] -= 6
                log.append(f"💥 **БОМБА ВЗОРВАЛАСЬ ПРИ СМЕРТИ (-6 HP)!**")

            if dfn["cur_hp"] <= 0:
                break
        
        if p1["cur_hp"] <= 0 or p2["cur_hp"] <= 0:
            break

    winner = p1["title"] if p1["cur_hp"] > 0 else p2["title"]
    log.append(f"\n🏆 **ПОБЕДИЛ: {winner}!**")
    return "\n".join(log)

@dp.message(Command("start"))
async def start_cmd(msg: types.Message):
    kb = InlineKeyboardBuilder()
    for key, data in BREEDS.items():
        kb.button(text=f"{data['title']} ({data['hp']} HP)", callback_data=f"fight:{key}")
    kb.adjust(1)
    await msg.answer("🐔 **Петушиные бои**\n\nВыбери своего бойца для дуэли:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("fight:"))
async def fight_action(call: types.CallbackQuery):
    my_pick = call.data.split(":")[1]
    enemy_pick = random.choice(list(BREEDS.keys()))
    
    await call.message.edit_text("⏳ *Идёт бой на арене...*", parse_mode="Markdown")
    
    result = run_fight(my_pick, enemy_pick)
    
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Сразиться снова", callback_data="again")
    await call.message.answer(result, reply_markup=kb.as_markup(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(lambda c: c.data == "again")
async def again_action(call: types.CallbackQuery):
    await start_cmd(call.message)
    await call.answer()

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
