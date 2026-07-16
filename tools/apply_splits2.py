# -*- coding: utf-8 -*-
"""Разбивка «Знакомства» на 3 фразовых блока и «Тела» на 2 юнита (по методисту).

Использование: python tools/apply_splits2.py <путь_к_app.db>
"""
import sys
import sqlite3

SPLITS = [
    {
        "parent": "Знакомство и общение",
        "rename": ("Привет и пока", "Исәнләшү", "👋"),
        "children": [
            ("Давай знакомиться", "Танышабыз", "🤝",
             ["исемең ничек?", "минем исемем", "сиңа ничә яшь?", "миңа биш яшь",
              "миңа алты яшь", "миңа җиде яшь", "син кайдан?", "мин Казаннан",
              "бу кем?", "бу нәрсә?"]),
            ("Вежливые слова", "Әдәпле сүзләр", "💛",
             ["зинһар", "гафу итегез", "хәлләр ничек?", "яхшы", "начар",
              "бик шатмын", "тәбрик итәм", "ярдәм ит"]),
        ],
        # существительные-люди уходят в «Семья и наш дом» — там им место и картинки работают
        "move_out": {
            "Семья и наш дом": ["малай", "кыз", "бала", "балалар", "дус", "дус кыз"],
        },
    },
    {
        "parent": "Человек и тело",
        "rename": ("Моё тело", "Минем тәнем", "🧍"),
        "children": [
            ("Лицо и голова", "Йөз һәм баш", "🙂",
             ["баш", "чәч", "күз", "күзләр", "борын", "авыз", "теш", "тел",
              "колак", "колаклар", "муен", "тавыш", "көлү", "күз яшьләре",
              "елмаю", "бит", "ирен"]),
        ],
        "move_out": {},
    },
]

ORDER = {
    "Животные: дома и во дворе": 1, "Семья и наш дом": 2, "Привет и пока": 3,
    "Цифры": 4, "Местоимения": 5, "Давай знакомиться": 6, "Цвета и формы": 7,
    "Животные: в лесу и зоопарке": 8, "Вещи в доме": 9, "Продукты и напитки": 10,
    "Фрукты/ягоды": 11, "Вежливые слова": 12, "Одежда и обувь": 13,
    "Птицы, рыбки, букашки": 14, "Овощи": 15, "Действия: движемся": 16,
    "Блюда и вкусы": 17, "Лицо и голова": 18, "Действия: говорим и думаем": 19,
    "Дни недели": 20, "Время и сезоны": 21, "Моё тело": 22,
    "Действия: играем и мастерим": 23, "Числа (10–19)": 24, "Десятки": 25,
    "Школа и урок": 26, "Пенал и рюкзак": 27,
}


def theme_id(cur, title):
    row = cur.execute("select id from themes where title_ru=?", (title,)).fetchone()
    return row[0] if row else None


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    for sp in SPLITS:
        pid = theme_id(cur, sp["parent"])
        if not pid:
            print(f"SKIP (нет темы): {sp['parent']}")
            continue
        new_title, new_tt, new_icon = sp["rename"]
        cur.execute("update themes set title_ru=?, title_tt=?, icon_emoji=? where id=?",
                    (new_title, new_tt, new_icon, pid))
        print(f"RENAME {sp['parent']} -> {new_title}")
        for child_title, child_tt, child_icon, tts in sp["children"]:
            cid = theme_id(cur, child_title)
            if not cid:
                cur.execute("insert into themes (title_ru, title_tt, icon_emoji, order_index) values (?,?,?,99)",
                            (child_title, child_tt, child_icon))
                cid = cur.lastrowid
            moved = 0
            for tt in tts:
                cur.execute("update words set theme_id=? where theme_id=? and text_tt=?", (cid, pid, tt))
                moved += cur.rowcount
            print(f"  CHILD {child_title}: {moved}/{len(tts)}")
        for target, tts in sp["move_out"].items():
            tid = theme_id(cur, target)
            moved = 0
            for tt in tts:
                cur.execute("update words set theme_id=? where theme_id=? and text_tt=?", (tid, pid, tt))
                moved += cur.rowcount
            print(f"  MOVE -> {target}: {moved}/{len(tts)}")

    for title, order in ORDER.items():
        cur.execute("update themes set order_index=? where title_ru=?", (order, title))
    con.commit()

    print("Тем:", cur.execute("select count(*) from themes").fetchone()[0])
    for r in cur.execute("select order_index, icon_emoji, title_ru, (select count(*) from words w where w.theme_id=t.id) from themes t order by order_index"):
        print(f"  {r[0]:>2}. {r[1]} {r[2]} ({r[3]})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
