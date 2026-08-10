# -*- coding: utf-8 -*-
"""Юнит «Шәһәрдә — В городе» (курс, урок 43).

Город глазами пятилетки: улица под ногами, транспорт, который громко приезжает,
и большие здания, мимо которых его водят за руку. Последний блок — казанские
реалии (мәчет, чиркәү, кирмән, Сөембикә манарасы): это те объекты, которые
ребёнок в Татарстане реально видит с окна автобуса, поэтому они узнаются
раньше абстрактного «шәһәр».

Примеры построены только на уже пройденной лексике (Казан, зур, чиста, апа,
көтә, килә, кызыл, балалар, уйный, ак, матур, иске, әти, рәсем, эт, йөри, озын, бу).

Идемпотентно. Запуск: python tools/seed_city.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "В городе"
THEME_TT = "Шәһәрдә"
ICON = "🏙️"

# Порядок — от близкого к дальнему: под ногами (урок 1), что едет мимо (урок 2),
# куда водят гулять (урок 3), казанские достопримечательности (урок 4).
# Транспорт держим одним блоком: на нём же потом отрабатываются падежи
# «автобусКА утыра / автобусТАН төшә» из урока 43.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — где я стою
    ("шәһәр", "город", "🏙️", "Казан — зур шәһәр.", "Казань — большой город.",
     "a city skyline with many tall colorful houses seen from far away, sunny day, "
     "centered, no text, no signs, no lettering"),
    ("урам", "улица", "🛣️", "Урам чиста.", "Улица чистая.",
     "an empty clean city street with houses on both sides and a sidewalk, "
     "centered, no text, no signs, no lettering"),
    ("күпер", "мост", "🌉", "Күпер озын.", "Мост длинный.",
     "a long bridge over a wide blue river, sunny day, "
     "centered, no text, no signs, no lettering"),
    # урок 2 — что едет мимо
    ("тукталыш", "остановка", "🚏", "Апа тукталышта көтә.", "Тётя ждёт на остановке.",
     "a bus stop shelter with a bench beside a city street, empty, "
     "centered, no text, no signs, no lettering"),
    ("автобус", "автобус", "🚌", "Автобус килә.", "Автобус едет.",
     "a big yellow city bus driving along a street, side view, "
     "centered, no text, no numbers, no lettering"),
    ("трамвай", "трамвай", "🚋", "Трамвай кызыл.", "Трамвай красный.",
     "a red city tram on rails with overhead wires, side view, "
     "centered, no text, no numbers, no lettering"),
    # урок 3 — куда мы ходим
    ("мәйдан", "площадь", "⛲", "Мәйданда балалар уйный.", "На площади дети играют.",
     "a wide open city square with a fountain and paving stones, "
     "centered, no text, no signs, no lettering"),
    ("парк", "парк", "🌳", "Паркта эт йөри.", "В парке гуляет собака.",
     "a green city park with tall trees, a path and a wooden bench, "
     "centered, no text, no signs, no lettering"),
    ("театр", "театр", "🎭", "Әти театрга бара.", "Папа идёт в театр.",
     "a grand theatre building with columns and a red curtain visible in the entrance, "
     "centered, no text, no signs, no lettering"),
    ("музей", "музей", "🏛️", "Музейда рәсем.", "В музее картина.",
     "a museum hall with framed paintings hanging on the wall and a display case, "
     "centered, no text, no signs, no lettering"),
    # урок 4 — Казань, которую видно из окна
    ("мәчет", "мечеть", "🕌", "Мәчет ак.", "Мечеть белая.",
     "a beautiful white mosque with slender minarets and blue domes, sunny sky, "
     "centered, no text, no signs, no lettering"),
    ("чиркәү", "церковь", "⛪", "Чиркәү матур.", "Церковь красивая.",
     "a white orthodox church with golden domes and a cross, sunny sky, "
     "centered, no text, no signs, no lettering"),
    ("кирмән", "кремль, крепость", "🏰", "Кирмән иске.", "Кремль старый.",
     "an old white stone fortress with high walls and round towers on a hill, "
     "centered, no text, no signs, no lettering"),
    ("Сөембикә манарасы", "башня Сююмбике", "🗼", "Бу — Сөембикә манарасы.",
     "Это башня Сююмбике.",
     "a tall red brick step tower with seven narrowing tiers and a green spire, "
     "the leaning Soyembika tower of Kazan, blue sky, "
     "centered, no text, no signs, no lettering"),
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
             "Город: урам, тукталыш, автобус, мәйдан, мәчет, кирмән и другие"),
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
