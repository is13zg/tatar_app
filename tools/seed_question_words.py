# -*- coding: utf-8 -*-
"""Юнит «Кто? Что? Какой?» — вопросительные слова татарского языка.

Каркас всех диалогов курса: Бу кем? → Нинди? → Нишли?
Каждое слово подаётся связкой «вопрос + ответ», иначе для нечитающего
ребёнка вопросительное слово — пустой звук.

Идемпотентно: тема ищется по title_ru, слова — по text_tt внутри темы.
Запуск: python tools/seed_question_words.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Кто? Что? Какой?"
THEME_TT = "Сорау сүзләре"
ICON = "❓"

# Порядок — по рекомендации носителя: от «покажи пальцем» (кем/нәрсә) и действия,
# которое можно изобразить телом (нишли), к признаку, месту и выбору из набора (кайсы).
# Уроки по 4 слова разбивают тему ровно на «ядро» и «второй блок».
# Все слова-ответы взяты из уже пройденных тем — новых существительных нет.
# text_tt, text_ru, emoji, question_tt, answer_tt, sentence_ru
WORDS = [
    ("кем", "кто", "❓🧒", "Бу кем?", "Бу — малай.", "Это кто? Это мальчик."),
    ("нәрсә", "что", "❓📦", "Бу нәрсә?", "Бу — китап.", "Это что? Это книга."),
    ("нишли", "что делает", "❓🏃", "Малай нишли?", "Малай йөгерә.", "Мальчик что делает? Мальчик бежит."),
    ("нинди", "какой", "❓🎨", "Алма нинди?", "Алма кызыл.", "Яблоко какое? Яблоко красное."),
    ("кайда", "где", "❓📍", "Песи кайда?", "Песи өйдә.", "Кошка где? Кошка дома."),
    ("кая", "куда", "❓➡️", "Песи кая бара?", "Песи өйгә бара.", "Кошка куда идёт? Кошка идёт домой."),
    ("ничә", "сколько", "❓🔢", "Ничә алма бар?", "Өч алма бар.", "Сколько яблок? Три яблока."),
    ("ничек", "как", "❓💬", "Исемең ничек?", "Минем исемем — Алсу.", "Как тебя зовут? Меня зовут Алсу."),
    ("кайсы", "который из них", "❓👉", "Кайсы алма зур?", "Бу алма зур.", "Которое яблоко большое? Это яблоко большое."),
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
             "Вопросительные слова: кем, нәрсә, нинди, нишли, кайда, ничә, кайсы"),
        )
        theme_id = cur.lastrowid
        print(f"создана тема id={theme_id}, order={max_order + 1}")

    added = updated = 0
    for tt, ru, emoji, q_tt, a_tt, s_ru in WORDS:
        s_tt = f"{q_tt} {a_tt}"  # хранится связкой; аудио склеивается с паузой отдельно
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
