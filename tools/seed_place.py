# -*- coding: utf-8 -*-
"""Юнит «Кайда? Где что лежит» — послелоги места.

Самая большая дыра в курсе: этих слов не было ни одного, а без них ребёнок
не может сказать, ГДЕ предмет — только назвать его. И это первый формат,
где ответ нельзя угадать по предмету: на всех картинках одна и та же кошка
и одна и та же кровать, различается только положение.

Картинки не нужны — сцену рисует фронт из двух эмодзи (см. ex_where).

Идемпотентно. Запуск: python tools/seed_place.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Кайда? Где что лежит"
THEME_TT = "Кайда? Урын"
ICON = "📍"

# Опора — песи и карават: оба из первых юнитов, оба узнаются эмодзи без картинки.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru
WORDS = [
    ("өстендә", "на, сверху", "🔼", "Песи карават өстендә.", "Кошка на кровати."),
    ("астында", "под", "🔽", "Песи карават астында.", "Кошка под кроватью."),
    ("эчендә", "внутри", "📦", "Песи тартма эчендә.", "Кошка внутри коробки."),
    ("янында", "рядом", "↔️", "Песи карават янында.", "Кошка рядом с кроватью."),
    ("артында", "за", "🙈", "Песи карават артында.", "Кошка за кроватью."),
    ("алдында", "перед", "👀", "Песи карават алдында.", "Кошка перед кроватью."),
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
             "Где предмет: өстендә, астында, эчендә, янында, артында, алдында"),
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
