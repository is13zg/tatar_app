# -*- coding: utf-8 -*-
"""Юнит «Чей? Кому? У кого?» — падежные формы личных местоимений (мин/син/ул).

Идемпотентно: тема ищется по title_ru, слова — по text_tt внутри темы.
Запуск: python tools/seed_pronoun_cases.py [путь_к_БД]  (по умолчанию app.db)
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Чей? Кому? У кого?"
THEME_TT = "Алмашлыклар: килешләр"
ICON = "🫵"

# порядок — по лицам: сначала весь ряд «про меня», потом «про тебя», потом «про него»
WORDS = [
    # text_tt, text_ru, emoji, sentence_tt, sentence_ru
    ("минем", "мой", "🙋🎒", "Минем китабым өстәлдә.", "Моя книга на столе."),
    ("миңа", "мне", "🙋🎁", "Миңа китап бир.", "Дай мне книгу."),
    ("мине", "меня", "🙋🤗", "Әни мине чакыра.", "Мама зовёт меня."),
    ("миннән", "от меня", "🙋📬", "Миннән сора.", "Спроси у меня."),
    ("миндә", "у меня", "🙋🏠", "Миндә китап бар.", "У меня есть книга."),
    ("синең", "твой", "🫵🎒", "Синең исемең ничек?", "Как твоё имя?"),
    ("сиңа", "тебе", "🫵🎁", "Сиңа бүләк бар.", "Для тебя есть подарок."),
    ("сине", "тебя", "🫵🤗", "Мин сине күрдем.", "Я увидел тебя."),
    ("синнән", "от тебя", "🫵📬", "Синнән хат килде.", "От тебя пришло письмо."),
    ("синдә", "у тебя", "🫵🏠", "Синдә ручка бармы?", "У тебя есть ручка?"),
    ("аның", "его, её", "👤🎒", "Аның машинасы яңа.", "Его машина новая."),
    ("аңа", "ему, ей", "👤🎁", "Аңа ярдәм кирәк.", "Ему нужна помощь."),
    ("аны", "его, её", "👤🤗", "Без аны көтәбез.", "Мы ждём его."),
    ("аннан", "от него, от неё", "👤📬", "Аннан курыкма!", "Не бойся его!"),
    ("анда", "у него, там", "👤🏠", "Анда телефон бар.", "У него есть телефон."),
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
             "Падежные формы местоимений: минем, миңа, миндә…"),
        )
        theme_id = cur.lastrowid
        print(f"создана тема id={theme_id}, order={max_order + 1}")

    added = skipped = 0
    for tt, ru, emoji, s_tt, s_ru in WORDS:
        ex = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                         (theme_id, tt)).fetchone()
        if ex:
            skipped += 1
            continue
        con.execute(
            "insert into words (theme_id, text_tt, text_ru, emoji, sentence_tt, sentence_ru) "
            "values (?,?,?,?,?,?)",
            (theme_id, tt, ru, emoji, s_tt, s_ru),
        )
        added += 1
    con.commit()
    n = con.execute("select count(*) from words where theme_id=?", (theme_id,)).fetchone()[0]
    print(f"слов добавлено: {added}, пропущено (были): {skipped}, всего в теме: {n}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
