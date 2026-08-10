# -*- coding: utf-8 -*-
"""Юнит «Уенчыклар — Игрушки» — самая близкая ребёнку 5–7 лет лексика.

По материалам курса (ts_13/ts_14 «Уенчыклар»): туп, курчак, машина — ядро темы,
вокруг которого в учебнике строится вопрос «Бу нәрсә?» и множественное число
(туп — тупЛАР, курчак — курчакЛАР). Игрушки-животные из PDF (аю, куян, песи,
эт, тычкан) НЕ дублируются — они уже есть в темах про животных, как и само
слово «уенчык» (тема «Вещи в доме»).

Примеры построены только на уже пройденной лексике: түгәрәк, матур, кызыл,
сары, озын, зур, нәни, яңа, җиңел, көчле, оча, йөзә, бара, бии.

Идемпотентно. Запуск: python tools/seed_toys.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Игрушки"
THEME_TT = "Уенчыклар"
ICON = "🧸"

# Порядок — по рекомендации носителя: сначала четыре игрушки, которые есть
# в каждом доме и с которых начинается учебник (урок 1), затем всё, что едет
# и летит (урок 2), потом то, что звучит и крутится (урок 3), и напоследок
# зимние и «строительные» игрушки (урок 4).
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — первые игрушки, ядро темы из учебника
    ("туп", "мяч", "⚽", "Туп түгәрәк.", "Мяч круглый.",
     "a single bright colorful toy ball lying on a plain light background, children's book illustration, one object centered, no text"),
    ("курчак", "кукла", "🪆", "Курчак матур.", "Кукла красивая.",
     "a single cute rag doll with braids in a red dress, standing on a plain light background, children's book illustration, one object centered, no text"),
    ("машина", "машинка", "🚗", "Машина кызыл.", "Машинка красная.",
     "a single red toy car, wooden children's toy, on a plain light background, one object centered, no text"),
    ("кубик", "кубик", "🧱", "Кубик сары.", "Кубик жёлтый.",
     "a single yellow wooden building block cube on a plain light background, children's toy, one object centered, no text"),
    # урок 2 — то, что едет, плывёт и летит
    ("поезд", "поезд", "🚂", "Поезд озын.", "Поезд длинный.",
     "a long colorful toy train with three wagons on a plain light background, children's book illustration, one object centered, no text"),
    ("очкыч", "самолёт", "✈️", "Очкыч оча.", "Самолёт летит.",
     "a single small toy airplane flying in a clear blue sky, children's book illustration, one object centered, no text"),
    ("кораб", "кораблик", "⛵", "Кораб йөзә.", "Кораблик плывёт.",
     "a single small toy sailboat floating on calm blue water, children's book illustration, one object centered, no text"),
    ("велосипед", "велосипед", "🚲", "Велосипед яңа.", "Велосипед новый.",
     "a single small children's bicycle with training wheels on a plain light background, one object centered, no text"),
    # урок 3 — то, что звучит и крутится
    ("барабан", "барабан", "🥁", "Барабан зур.", "Барабан большой.",
     "a single colorful toy drum with two wooden drumsticks on a plain light background, one object centered, no text"),
    ("сыбызгы", "свисток, дудочка", "🎺", "Сыбызгы нәни.", "Свисток маленький.",
     "a single small wooden whistle pipe toy on a plain light background, children's book illustration, one object centered, no text"),
    ("юла", "юла, волчок", "🌀", "Юла бии.", "Юла танцует.",
     "a single colorful spinning top toy spinning on a plain light background, motion blur at the tip, one object centered, no text"),
    ("шар", "воздушный шарик", "🎈", "Шар җиңел.", "Шарик лёгкий.",
     "a single red helium balloon with a string floating in the air, plain light background, one object centered, no text"),
    # урок 4 — зимний двор и стройка
    ("чана", "санки", "🛷", "Чана бара.", "Санки едут.",
     "a single wooden sled sliding down a snowy hill, winter, children's book illustration, one object centered, no text"),
    ("конструктор", "конструктор", "🧩", "Конструктор яңа.", "Конструктор новый.",
     "a small pile of colorful plastic building bricks with a half-built tower, plain light background, one object centered, no text"),
    ("робот", "робот", "🤖", "Робот көчле.", "Робот сильный.",
     "a single friendly blue toy robot standing on a plain light background, children's book illustration, one object centered, no text"),
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
             "Игрушки: туп, курчак, машина, кубик, поезд, барабан и другие"),
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
