# -*- coding: utf-8 -*-
"""Юнит «Нинди? Какой предмет» — прилагательные-признаки.

Без них невозможен вопрос «Нинди?», на котором держится половина диалогов
курса. Пять пар — антонимы (см. OPPOSITES_TT в lessons.py), поэтому тема
сразу работает с готовой игрой «Найди наоборот».

Примеры построены только на уже пройденной лексике (китап, дәфтәр, уенчык,
кул, аяк, карават, каләм, чәй, мендәр, аю, күлмәк, алма, кишер).

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
    # урок 1 — смотрим глазами
    ("чиста", "чистый", "🧼", "Кул чиста.", "Руки чистые.",
     "clean freshly washed child hands with soap foam"),
    ("пычрак", "грязный", "🦶", "Аяк пычрак.", "Ноги грязные.",
     "child bare feet covered in brown mud"),
    ("яңа", "новый", "✨", "Уенчык яңа.", "Игрушка новая.",
     "a brand new shiny toy car, sparkling clean, bright colors"),
    ("иске", "старый", "🧸", "Уенчык иске.", "Игрушка старая.",
     "an old shabby worn toy car, faded paint, scratched, no people"),
    # урок 2 — трогаем руками
    ("йомшак", "мягкий", "🧸", "Мендәр йомшак.", "Подушка мягкая.",
     "a very soft fluffy squishy pillow on a bed, cozy and puffy"),
    ("каты", "твёрдый", "🥕", "Кишер каты.", "Морковь твёрдая.",
     "a hard raw carrot, a child biting it with effort, crunchy"),
    ("юеш", "мокрый", "💧", "Чәч юеш.", "Волосы мокрые.",
     "wet hair strands with shiny water droplets dripping down, close up, no face"),
    ("коры", "сухой", "🌾", "Күлмәк коры.", "Рубашка сухая.",
     "a dry clean shirt hanging on a hanger, no water"),
    # урок 3 — взвешиваем и сравниваем
    ("авыр", "тяжёлый", "🎒", "Сумка авыр.", "Сумка тяжёлая.",
     "a child struggling to lift a very heavy school bag with both hands, strain on face"),
    ("җиңел", "лёгкий", "✏️", "Каләм җиңел.", "Ручка лёгкая.",
     "a light thin pen balanced on one finger, floating feeling"),
    ("калын", "толстый", "📗", "Китап калын.", "Книга толстая.",
     "a very thick heavy closed book, seen from the side to show its thickness"),
    ("юка", "тонкий", "📄", "Дәфтәр юка.", "Тетрадь тонкая.",
     "a single very thin school notebook, seen from the side to show it is thin"),
    # урок 4 — оценка и качество
    ("җылы", "тёплый", "☕", "Чәй җылы.", "Чай тёплый.",
     "a child calmly drinking from a cup of tea, cozy, no steam"),
    ("матур", "красивый", "🌸", "Кыз матур.", "Девочка красивая.",
     "a beautiful smiling girl with flowers in her hair"),
    ("көчле", "сильный", "💪", "Аю көчле.", "Медведь сильный.",
     "a strong bear flexing its muscular arms"),
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
