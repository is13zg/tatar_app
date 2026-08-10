# -*- coding: utf-8 -*-
"""Юнит «Нинди? Какой предмет» — прилагательные-признаки.

Без них невозможен вопрос «Нинди?», на котором держится половина диалогов
курса. Пять пар — антонимы (см. OPPOSITES_TT в lessons.py), поэтому тема
сразу работает с готовой игрой «Найди наоборот».

Картинки в паре нарисованы на ОДНОМ И ТОМ ЖЕ предмете (та же машинка чистая и
грязная, тот же мяч мягкий и твёрдый). Иначе ребёнок выучит не признак, а предмет:
пока «толстый» был книгой, а «тонкий» — тетрадью, различались книга и тетрадь.

Предметы взяты из тем, которые идут раньше по карте (игрушки, животные, цвета).
Исключения — китап, чәй и алма: они появляются позже, но на картинке узнаются
без слов и в заданиях не проверяются.

Идемпотентно. Запуск: python tools/seed_adjectives.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Нинди? Какой предмет"
THEME_TT = "Нинди? Билгеләр"
ICON = "🔎"

# Порядок — по рекомендации носителя: сначала то, что видно глазом (урок 1),
# потом то, что чувствуется рукой (урок 2), затем вес и толщина (урок 3),
# и напоследок оценочные признаки (урок 4). Каждая пара антонимов целиком
# внутри одного урока, иначе игра «Найди наоборот» не запускается.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — смотрим глазами (пара на одной машинке, пара на одной кукле)
    ("чиста", "чистый", "🧼", "Машина чиста.", "Машинка чистая.",
     "a red toy car, freshly washed and shiny, sparkling clean, water drops and soap bubbles around it"),
    ("пычрак", "грязный", "🚗", "Машина пычрак.", "Машинка грязная.",
     "the very same red toy car, now covered all over in brown mud splashes and dirt, dull and muddy"),
    ("яңа", "новый", "✨", "Курчак яңа.", "Кукла новая.",
     "a brand new doll with neat shiny hair and a bright clean dress, sparkles around her"),
    ("иске", "старый", "🪆", "Курчак иске.", "Кукла старая.",
     "the very same doll but old and shabby: messy faded hair, torn patched dress, worn out"),
    # урок 2 — трогаем руками (пара на одном мяче, пара на одной рубашке)
    ("йомшак", "мягкий", "🧸", "Туп йомшак.", "Мяч мягкий.",
     "a soft plush blue ball being squeezed by a child hand, the ball dents deeply under the fingers"),
    ("каты", "твёрдый", "⚽", "Туп каты.", "Мяч твёрдый.",
     "the very same blue ball but hard, a child hand knocking on it, it stays perfectly round, "
     "small impact lines"),
    ("юеш", "мокрый", "💧", "Күлмәк юеш.", "Рубашка мокрая.",
     "a shirt hanging on a hanger, soaking wet and dripping, water drops falling down from it"),
    ("коры", "сухой", "👕", "Күлмәк коры.", "Рубашка сухая.",
     "the very same shirt on the same hanger, completely dry, no water drops at all"),
    # урок 3 — взвешиваем и сравниваем (пара на одном кубике, пара на одной книге)
    ("авыр", "тяжёлый", "🧱", "Кубик авыр.", "Кубик тяжёлый.",
     "a child straining with both hands to lift one big grey stone cube, bent under the weight, "
     "sweat drops"),
    ("җиңел", "лёгкий", "🎈", "Кубик җиңел.", "Кубик лёгкий.",
     "the very same size cube but light as foam, a smiling child holding it up on one open palm"),
    ("калын", "толстый", "📗", "Китап калын.", "Книга толстая.",
     "a very thick closed green book standing upright, seen from the side to show how thick it is"),
    ("юка", "тонкий", "📗", "Китап юка.", "Книга тонкая.",
     "the very same green book but very thin, standing upright, seen from the side to show how thin it is"),
    # урок 4 — оценка и качество
    ("җылы", "тёплый", "☕", "Чәй җылы.", "Чай тёплый.",
     "a child calmly drinking from a cup of tea, cozy, no steam"),
    ("матур", "красивый", "🌸", "Кыз матур.", "Девочка красивая.",
     "a beautiful smiling girl with flowers in her hair"),
    ("көчле", "сильный", "🐴", "Ат көчле.", "Лошадь сильная.",
     "a strong horse pulling a heavy loaded cart, powerful muscles, straining forward"),
    ("татлы", "сладкий", "🍬", "Алма татлы.", "Яблоко сладкое.",
     "a sweet ripe red apple, a happy child biting it, candy-sweet look"),
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
             "Признаки предметов: калын, юка, яңа, иске, чиста, пычрак и другие"),
        )
        theme_id = cur.lastrowid
        print(f"создана тема id={theme_id}, order={max_order + 1}")

    added = updated = 0
    for tt, ru, emoji, s_tt, s_ru, _en in WORDS:
        ex = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                         (theme_id, tt)).fetchone()
        if ex:
            # если фраза поменялась — старая озвучка больше ей не соответствует
            con.execute("update words set text_ru=?, emoji=?, sentence_tt=?, sentence_ru=?, "
                        "sentence_audio_url = case when sentence_tt=? then sentence_audio_url else null end "
                        "where id=?",
                        (ru, emoji, s_tt, s_ru, s_tt, ex["id"]))
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
