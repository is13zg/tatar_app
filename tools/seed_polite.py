# -*- coding: utf-8 -*-
"""Юнит «Матур сүзләр — Вежливые фразы по ситуациям» (курс, урок 2).

Отличие от уже существующей темы «Әдәпле сүзләр»: там отдельные слова
(рәхмәт, зинһар, гафу итегез), здесь — ГОТОВАЯ ФОРМУЛА, намертво привязанная
к бытовой сценке. Ребёнок 5–7 лет не читает: он узнаёт картинку («кто-то
чихнул», «гости в дверях», «лёг в кровать») и вспоминает, что говорят.

Все восемь взяты из стихов Ленара Шәеха в ts_02 — каждая строфа там и есть
готовая сценка:
  чихнул                → Сәламәт бул!
  разбил чашку          → Гафу ит! / Ачуланма!
  пришли апа-абыйлар    → Рәхим итегез!
  уезжает из деревни    → Хуш! / Хәерле юл!
  лёг спать             → Тыныч йокы! / Тәмле төшләр!

Из ситуаций урока в тему НЕ вошли те, чьи формулы уже есть в базе:
«поел → Рәхмәт», «гости уходят → Сау булыгыз!», «утро → Хәерле иртә!,
Исәнмесез!». «Зинһар өчен» (велосипедист просит дорогу) пропущено: это то же
самое слово, что уже стоит карточкой «зинһар», плюс служебная частица.
«Исән-сау бул!» пропущено как второй перевод «будь здоров» — на слух не
отличается от «Сәламәт бул!».

Форма ВЕЗДЕ детская, на «ты» (Гафу ит, Ачуланма, Сәламәт бул, Хуш).
Единственное исключение — «Рәхим итегез!»: формула обращена к пришедшим
гостям, то есть к нескольким людям, и в этом виде она застыла в языке
(так и в стихотворении). Ту же логику держат sentence_tt.

8 фраз = ровно 2 урока по NEW_WORDS_PER_LESSON=4.

Примеры построены только на уже пройденной лексике (әни, әти, әби, бабай,
дуслар, кыз) и на имени Булат из стихотворения урока.

Идемпотентно. Запуск: python tools/seed_polite.py [путь_к_БД]
"""
import sys

sys.exit("Этот seed устарел: тема «Вежливые фразы» перестроена в «Добрые пожелания»\n"
         "скриптом tools/restructure_polite.py (2026-08-15). Повторный прогон старого\n"
         "seed создал бы тему-дубль со старым названием и вернул бы слова, которые\n"
         "переехали в «Волшебные слова».")

import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Вежливые фразы"
THEME_TT = "Матур сүзләр"
ICON = "🌸"

# Порядок — по времени детского дня: сначала то, что случается днём дома и
# требует ответа сразу (урок 1), потом проводы и вечер, когда фраза говорится
# последней (урок 2). Пары «Гафу ит! — Ачуланма!» и «Тыныч йокы! — Тәмле
# төшләр!» стоят рядом: в стихотворении они звучат в одной строфе.
# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    # урок 1 — днём дома: что-то случилось, надо ответить
    ("Сәламәт бул!", "будь здоров!", "🤧", "Сәламәт бул, Булат!",
     "Будь здоров, Булат! (мальчик чихнул)",
     "a small boy sneezing into his elbow while his grandmother gently pats his shoulder and smiles at him, "
     "cosy home room, children's book illustration, no text, no lettering"),
    ("Гафу ит!", "извини!", "🙏", "Гафу ит, әни!",
     "Извини, мама! (разбил чашку)",
     "a guilty looking child standing next to a broken cup on the kitchen floor, "
     "mother kneeling beside him calmly, children's book illustration, no text, no lettering"),
    ("Ачуланма!", "не сердись!", "🥺", "Ачуланма, әти!",
     "Не сердись, папа! (пролил молоко)",
     "a child looking up apologetically at his frowning father next to a spilled glass of milk on the table, "
     "children's book illustration, no text, no lettering"),
    ("Рәхим итегез!", "добро пожаловать!", "🚪", "Рәхим итегез, дуслар!",
     "Добро пожаловать, друзья! (гости пришли, стоят в дверях)",
     "a smiling child opening the front door wide for two grown-up guests standing on the doorstep with a gift, "
     "children's book illustration, no text, no lettering"),
    # урок 2 — проводы и вечер: фраза говорится последней
    ("Хуш!", "прощай!", "👋", "Хуш, әби!",
     "Прощай, бабушка! (уезжает из деревни домой)",
     "a child waving goodbye with one hand from an open car window, a village house and an old woman "
     "waving back in the background, children's book illustration, no text, no lettering"),
    ("Хәерле юл!", "счастливого пути!", "🚂", "Хәерле юл, бабай!",
     "Счастливого пути, дедушка! (машет вслед уезжающему)",
     "a child on a small station platform waving after a departing train, seen from behind, "
     "children's book illustration, no text, no lettering"),
    ("Тыныч йокы!", "спокойной ночи!", "🌙", "Тыныч йокы, әни!",
     "Спокойной ночи, мама! (лёг в кровать)",
     "a child lying in bed hugging a teddy bear, night window with the moon and stars, warm lamp light, "
     "children's book illustration, no text, no lettering"),
    ("Тәмле төшләр!", "сладких снов!", "💤", "Тәмле төшләр, кызым!",
     "Сладких снов, доченька! (мама укрывает одеялом)",
     "a mother tucking a blanket around a sleepy smiling girl in bed, dim cosy night room, "
     "children's book illustration, no text, no lettering"),
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
             "Вежливые фразы по ситуациям: Сәламәт бул!, Гафу ит!, Рәхим итегез!, Тыныч йокы!"),
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
