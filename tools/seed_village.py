# -*- coding: utf-8 -*-
"""Юнит «Авылда — В деревне» (курс, урок 42).

Деревня у ребёнка — это лето у әби с бабай. Поэтому берём только то, что он там
трогает руками: печь, ворота, забор, колодец, грабли, лейку. Домашних животных
здесь сознательно нет — сарык, каз, сыер, ат, кәҗә, тавык уже прошли в теме
«Йорт хайваннары», и повтор съел бы половину юнита.

Примеры построены только на уже пройденной лексике (әби, яши, җылы, алма, су,
салкын, яшел, коры, яңа, нәни, зәңгәр, озын, килә, бал).

Идемпотентно. Запуск: python tools/seed_village.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "В деревне"
THEME_TT = "Авылда"
ICON = "🏡"

# Порядок — как ребёнка ведут по деревне: сама деревня и дом с печью (урок 1),
# вода и зелень вокруг (урок 2), инструменты, которые дают в руки (урок 3),
# и двор — ворота, забор, улей, гость у калитки (урок 4).
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — деревня и дом
    ("авыл", "деревня", "🏡", "Әби авылда яши.", "Бабушка живёт в деревне.",
     "a small village with a few wooden houses, a dirt road and green hills behind, "
     "centered, no text, no signs, no lettering"),
    ("мич", "печь", "🔥", "Мич җылы.", "Печь тёплая.",
     "a big white washed village stove made of brick with an open fire door and warm flames inside, "
     "centered, no text, no signs, no lettering"),
    ("бакча", "огород, сад", "🌱", "Бакчада алма.", "В огороде яблоко.",
     "a village vegetable garden with neat beds of green plants and an apple tree, "
     "centered, no text, no signs, no lettering"),
    # урок 2 — вода и зелень
    ("кое", "колодец", "🕳️", "Коеда су.", "В колодце вода.",
     "an old wooden village well with a roof, a crank handle and a bucket on a rope, "
     "centered, no text, no signs, no lettering"),
    ("чишмә", "родник", "💧", "Чишмә суы салкын.", "Вода в роднике холодная.",
     "a clear cold spring flowing from a pipe into a small stone basin among grass, "
     "centered, no text, no signs, no lettering"),
    ("үлән", "трава", "🌿", "Үлән яшел.", "Трава зелёная.",
     "a close up patch of fresh green meadow grass with small blades, "
     "centered, no text, no signs, no lettering"),
    ("печән", "сено", "🌾", "Печән коры.", "Сено сухое.",
     "a big round stack of dry golden hay in a field, "
     "centered, no text, no signs, no lettering"),
    # урок 3 — что дают в руки
    ("тырма", "грабли", "🍂", "Тырма яңа.", "Грабли новые.",
     "a garden rake with a wooden handle and metal teeth, standing against a fence, "
     "centered, no text, no signs, no lettering"),
    ("көрәк", "лопата", "🥄", "Көрәк бакчада.", "Лопата в огороде.",
     "a garden spade with a wooden handle stuck into dark soil, "
     "centered, no text, no signs, no lettering"),
    ("сусипкеч", "лейка", "🚿", "Сусипкеч нәни.", "Лейка маленькая.",
     "a small green metal watering can with a spout, standing on the grass, "
     "centered, no text, no signs, no lettering"),
    # урок 4 — двор
    ("капка", "ворота", "🚪", "Капка зәңгәр.", "Ворота синие.",
     "a blue painted wooden village gate with carved patterns, closed, "
     "centered, no text, no signs, no lettering"),
    ("койма", "забор", "🪵", "Койма озын.", "Забор длинный.",
     "a long wooden picket fence made of planks along a village yard, "
     "centered, no text, no signs, no lettering"),
    ("умарта", "улей", "🍯", "Умартада бал.", "В улье мёд.",
     "a wooden beehive box standing in a garden with a few bees flying near it, "
     "centered, no text, no signs, no lettering"),
    ("кунак", "гость", "🎁", "Кунак килә.", "Гость идёт.",
     "a smiling visitor with a gift box and flowers standing at a village gate, "
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
             "Деревня: авыл, мич, бакча, кое, тырма, көрәк, капка и другие"),
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
