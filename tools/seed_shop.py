# -*- coding: utf-8 -*-
"""Юнит «Кибеттә / В магазине».

Порядок: сам магазин и люди в нём, потом деньги, потом то, что стоит
внутри зала, и напоследок типы магазинов — их учим последними, когда
слово «кибет» уже узнаётся на слух.

Слово «сатучы» (продавец) живёт в теме «Профессии», здесь не дублируется.

Идемпотентно. Запуск: python tools/seed_shop.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "В магазине"
THEME_TT = "Кибеттә"
ICON = "🛒"

# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
# в промптах явный запрет надписей: витрины и ценники иначе рисуются с текстом
WORDS = [
    ("кибет", "магазин", "🏪", "Кибет зур.", "Магазин большой.",
     "a small friendly neighborhood shop building with an awning and big windows, no text, no signs"),
    ("сатып алучы", "покупатель", "🛍️", "Сатып алучы көтә.", "Покупатель ждёт.",
     "a customer holding a shopping basket and paper bags at a shop counter, no text, no signs"),
    ("акча", "деньги", "💰", "Әти акча бирә.", "Папа даёт деньги.",
     "a small pile of coins and paper money, no numbers, no text"),
    ("сум", "рубль", "🪙", "Алма биш сум.", "Яблоко пять рублей.",
     "a single shiny coin held between two fingers, no numbers, no text"),
    ("касса", "касса", "🧾", "Касса яңа.", "Касса новая.",
     "a cash register machine on a shop counter, no text, no numbers"),
    ("кәрзин", "корзина", "🧺", "Кәрзин авыр.", "Корзина тяжёлая.",
     "a shopping basket full of groceries, no text"),
    ("киштә", "полка", "🗄", "Киштәдә китап.", "На полке книга.",
     "a shop shelf with a few books and boxes on it, no text, no lettering"),
    ("үлчәү", "весы", "⚖️", "Үлчәү өстәлдә.", "Весы на столе.",
     "a simple kitchen scale with apples on it, no numbers, no text"),
    ("ашамлыклар кибете", "продуктовый магазин", "🥖", "Әни ашамлыклар кибетенә бара.",
     "Мама идёт в продуктовый магазин.",
     "a grocery shop stall with bread, milk and vegetables, no text, no signs"),
    ("киемнәр кибете", "магазин одежды", "👗", "Бу — киемнәр кибете.", "Это магазин одежды.",
     "a clothing shop rack with dresses and shirts on hangers, no text, no signs"),
    ("уенчыклар кибете", "магазин игрушек", "🧸", "Уенчыклар кибете матур.",
     "Магазин игрушек красивый.",
     "a toy shop shelf with teddy bears, balls and toy cars, no text, no signs"),
    ("җиһаз кибете", "мебельный магазин", "🛋", "Җиһаз кибетендә шкаф.", "В мебельном магазине шкаф.",
     "a furniture shop showroom with a wardrobe, sofa and table, no text, no signs"),
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
            (THEME_RU, THEME_TT, ICON, max_order + 1, "Магазин: кто там, за что платят, какие бывают"),
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
