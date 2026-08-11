# -*- coding: utf-8 -*-
"""Юнит «Һава торышы. Погода».

Погода жила в курсе только внутри фраз о временах года («Яңгыр ява.»), а
отдельными словами её не было — ребёнок не мог ответить на вопрос, какая
сегодня погода. Тема сразу стыкуется с готовым «Одень Марата»: сначала
назвал погоду, потом оделся по ней.

Картинки не нужны: у погоды эмодзи — общепринятые значки, их же рисуют
в детских книжках и в прогнозах.

Идемпотентно. Запуск: python tools/seed_weather.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Һава торышы. Погода"
THEME_TT = "Һава торышы"
ICON = "🌦"

# Сначала то, что видно в окно, потом ветер и облака, в конце — как это ощущается.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru
WORDS = [
    ("кояш", "солнце", "☀️", "Кояш яктыра.", "Солнце светит."),
    ("яңгыр", "дождь", "🌧", "Яңгыр ява.", "Идёт дождь."),
    ("кар", "снег", "❄️", "Кар ява.", "Идёт снег."),
    ("җил", "ветер", "💨", "Җил исә.", "Дует ветер."),
    ("болыт", "туча", "☁️", "Болыт зур.", "Туча большая."),
    ("эссе", "жарко", "🥵", "Бүген эссе.", "Сегодня жарко."),
    ("салкын", "холодно", "🥶", "Бүген салкын.", "Сегодня холодно."),
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
             "Погода: кояш, яңгыр, кар, җил, болыт, эссе, салкын"),
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
