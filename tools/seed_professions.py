# -*- coding: utf-8 -*-
"""Юнит «Һөнәрләр — Профессии» — «Бу кем?» и «Ул нишли?».

По материалам курса (ts_45/ts_46 «Һөнәрләр»): балыкчы, гармунчы, тәрбияче,
сатучы, табиб, рәссам, укытучы + глаголы-действия (төзи, чәч ала, сыер сава,
хат ташый, сүндерә, тәрбияли) и «Хәрби ватанны саклый». Взяты те профессии,
которые ребёнок 5–7 лет реально видит и легко узнаёт на картинке.

«Укытучы» здесь НЕ повторяется — слово уже есть в теме «Мәктәп һәм дәрес».
«Нефтьче» из PDF пропущен: на картинке неотличим от рабочего, для этого
возраста не опознаётся.

Примеры построены на уже пройденной лексике: ярдәм итә, яхшы, бирә, алма,
аш, ясый, бара, оча, рәсем ясый, җырлый, уйный, эзли, балык, көчле, өй,
чәч, кисә, килә, йөгерә, сыер, сөт.

Идемпотентно. Запуск: python tools/seed_professions.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Профессии"
THEME_TT = "Һөнәрләр"
ICON = "👷"

# Порядок — по рекомендации носителя: сначала те, кого ребёнок встречает
# каждый день (урок 1), потом те, кто везёт, летит и спешит на помощь
# (урок 2), затем голос и красота (урок 3), и напоследок труд и родная
# земля (урок 4). Пары «профессия — её глагол» (очучы–оча, җырчы–җырлый,
# төзүче–төзи) стоят рядом, чтобы работала догадка по корню слова.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — кого ребёнок видит каждый день
    ("табиб", "врач", "👨‍⚕️", "Табиб ярдәм итә.", "Врач помогает.",
     "a friendly doctor in a white coat with a stethoscope around the neck, standing centered on a plain light background, children's book illustration, one person, no text"),
    ("тәрбияче", "воспитатель", "🧑‍🏫", "Тәрбияче яхшы.", "Воспитательница хорошая.",
     "a kind young kindergarten teacher woman in a simple dress holding a picture book, standing centered on a plain light background, children's book illustration, one person, no text"),
    ("сатучы", "продавец", "🛒", "Сатучы алма бирә.", "Продавец даёт яблоко.",
     "a smiling shop assistant in an apron behind a small counter holding an apple, plain light background, children's book illustration, one person, no text"),
    ("пешекче", "повар", "👨‍🍳", "Пешекче аш ясый.", "Повар готовит суп.",
     "a cheerful cook in a white chef hat and apron stirring a big pot with a ladle, plain light background, children's book illustration, one person, no text"),
    # урок 2 — кто везёт, летит и спешит на помощь
    ("шофёр", "водитель", "🚌", "Шофёр бара.", "Водитель едет.",
     "a friendly bus driver in a cap sitting at the steering wheel of a yellow bus, plain light background, children's book illustration, one person, no text"),
    ("очучы", "лётчик", "👨‍✈️", "Очучы оча.", "Лётчик летит.",
     "a pilot in a blue uniform and cap standing in front of a small airplane, plain light background, children's book illustration, one person, no text"),
    ("хат ташучы", "почтальон", "📮", "Хат ташучы килә.", "Почтальон идёт.",
     "a postman in a blue cap with a big shoulder bag full of letters, holding an envelope, plain light background, children's book illustration, one person, no text"),
    ("янгын сүндерүче", "пожарный", "🧑‍🚒", "Янгын сүндерүче йөгерә.", "Пожарный бежит.",
     "a firefighter in a red helmet and protective suit running with a fire hose, plain light background, children's book illustration, one person, no text"),
    # урок 3 — голос, краски и красота
    ("рәссам", "художник", "👨‍🎨", "Рәссам рәсем ясый.", "Художник рисует картину.",
     "an artist in a beret holding a palette and brush in front of an easel with a colorful painting, plain light background, children's book illustration, one person, no text"),
    ("җырчы", "певец", "🎤", "Җырчы җырлый.", "Певец поёт.",
     "a happy singer in a bright stage costume singing into a microphone, plain light background, children's book illustration, one person, no text"),
    ("гармунчы", "гармонист", "🪗", "Гармунчы уйный.", "Гармонист играет.",
     "a cheerful Tatar musician in an embroidered skullcap playing a small accordion, plain light background, children's book illustration, one person, no text"),
    ("чәчтараш", "парикмахер", "💇", "Чәчтараш чәч кисә.", "Парикмахер стрижёт волосы.",
     "a hairdresser in an apron holding scissors and a comb next to a barber chair, plain light background, children's book illustration, one person, no text"),
    # урок 4 — труд и родная земля
    ("төзүче", "строитель", "👷", "Төзүче өй төзи.", "Строитель строит дом.",
     "a builder in an orange hard hat and work vest holding a trowel in front of a brick wall, plain light background, children's book illustration, one person, no text"),
    ("балыкчы", "рыбак", "🎣", "Балыкчы балык эзли.", "Рыбак ищет рыбу.",
     "a fisherman in rubber boots and a hat holding a fishing rod at the river bank, plain light background, children's book illustration, one person, no text"),
    ("сыер савучы", "доярка", "🐄", "Сыер савучы сөт бирә.", "Доярка даёт молоко.",
     "a smiling milkmaid in a headscarf and apron holding a metal bucket of milk beside a cow, plain light background, children's book illustration, one person, no text"),
    ("хәрби", "военный", "🪖", "Хәрби көчле.", "Военный сильный.",
     "a soldier in a green uniform and helmet standing proudly at attention, plain light background, children's book illustration, one person, no weapons, no text"),
]


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    t = con.execute("select id from themes where title_ru=?", (THEME_RU,)).fetchone()
    if t:
        theme_id = t["id"]
        print(f"тема уже есть: id={theme_id}")
    else:
        max_order = con.execute("select coalesce(max(order_index),0) from themes").fetchone()[0]
        cur = con.execute(
            "insert into themes (title_ru, title_tt, icon_emoji, order_index, description) values (?,?,?,?,?)",
            (THEME_RU, THEME_TT, ICON, max_order + 1,
             "Профессии: табиб, сатучы, пешекче, очучы, төзүче и другие"),
        )
        theme_id = cur.lastrowid
        print(f"создана тема id={theme_id}, order={max_order + 1}")

    added = updated = 0
    for tt, ru, emoji, s_tt, s_ru, _en in WORDS:
        ex = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                         (theme_id, tt)).fetchone()
        if ex:
            con.execute("update words set text_ru=?, emoji=?, sentence_tt=?, sentence_ru=? where id=?",
                        (ru, emoji, s_tt, s_ru, ex["id"]))
            updated += 1
            continue
        con.execute(
            "insert into words (theme_id, text_tt, text_ru, emoji, sentence_tt, sentence_ru) values (?,?,?,?,?,?)",
            (theme_id, tt, ru, emoji, s_tt, s_ru),
        )
        added += 1
    con.commit()
    n = con.execute("select count(*) from words where theme_id=?", (theme_id,)).fetchone()[0]
    print(f"добавлено: {added}, обновлено: {updated}, всего в теме: {n}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
