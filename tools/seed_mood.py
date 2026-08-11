# -*- coding: utf-8 -*-
"""Юнит «Кәеф ничек? Настроения» — состояния человека.

Эмоций в базе не было почти совсем (одно «елый»). Тема нужна не ради восьми
слов, а ради формата «почему»: звучит причина («Ул ашамады»), ребёнок
выбирает состояние («ач»). Это первое задание на связь события и состояния,
а не на называние предмета.

Картинки не нужны и даже вредны: у эмоций эмодзи — канонический рисунок,
AI-лица получаются одинаковыми (ровно этим больна тема «Здоровье»).

Идемпотентно. Запуск: python tools/seed_mood.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Кәеф ничек? Настроения"
THEME_TT = "Кәеф ничек?"
ICON = "🙂"

# Порядок: сначала два полюса (рад / грустен), потом то, что видно на лице,
# и в конце телесные состояния, у которых есть понятная ребёнку причина.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru
WORDS = [
    ("шат", "радостный", "😀", "Малай шат.", "Мальчик радостный."),
    ("моңсу", "грустный", "😢", "Кыз моңсу.", "Девочка грустная."),
    ("ачулы", "сердитый", "😠", "Абый ачулы.", "Брат сердитый."),
    ("курка", "боится", "😨", "Бала курка.", "Ребёнок боится."),
    ("көлә", "смеётся", "😄", "Бала көлә.", "Ребёнок смеётся."),
    ("арган", "усталый", "🥱", "Әти арган.", "Папа усталый."),
    ("ач", "голодный", "🍽", "Песи ач.", "Кошка голодная."),
    ("сусаган", "хочет пить", "💧", "Эт сусаган.", "Собака хочет пить."),
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
             "Настроения и состояния: шат, моңсу, ачулы, курка, арган, ач"),
        )
        theme_id = cur.lastrowid
        print(f"создана тема id={theme_id}, order={max_order + 1}")

    added = updated = 0
    for tt, ru, emoji, s_tt, s_ru in WORDS:
        ex = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                         (theme_id, tt)).fetchone()
        if ex:  # фразу не трогаем — она может быть правлена вручную
            con.execute("update words set text_ru=?, emoji=? where id=?", (ru, emoji, ex["id"]))
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
