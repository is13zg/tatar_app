# -*- coding: utf-8 -*-
"""Юнит «Сәламәтлек / Здоровье».

Порядок: сначала то, что ребёнок чувствует сам (болит, горло, кашляет,
чихает), затем кто и чем помогает, и в конце — «здоров», чтобы тема
закрывалась на позитиве.

Слова «табиб» и «авырый» сюда не входят: первое живёт в теме «Профессии»,
второе уже есть в базе.

Идемпотентно. Запуск: python tools/seed_health.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

THEME_RU = "Здоровье"
THEME_TT = "Сәламәтлек"
ICON = "🩺"

# text_tt, text_ru, emoji, sentence_tt, sentence_ru, en_prompt (для картинки)
WORDS = [
    ("авырта", "болит", "🤕", "Теш авырта.", "Зуб болит.",
     "a sad little boy holding his cheek with both hands because his tooth hurts"),
    ("тамак", "горло", "😣", "Тамак авырта.", "Горло болит.",
     "a small girl touching her sore throat, warm scarf around her neck"),
    ("йөткерә", "кашляет", "😷", "Кыз йөткерә.", "Девочка кашляет.",
     "a little girl coughing into her bent elbow, wrapped in a blanket"),
    ("төчкерә", "чихает", "🤧", "Бала төчкерә.", "Ребёнок чихает.",
     "a small child sneezing into a paper tissue, tissue box nearby"),
    ("дәвалый", "лечит", "👨‍⚕️", "Табиб дәвалый.", "Врач лечит.",
     "a friendly doctor in a white coat listening to a smiling child with a stethoscope"),
    ("хастаханә", "больница", "🏥", "Хастаханә зур.", "Больница большая.",
     "a big friendly hospital building with a red cross, cartoon style"),
    ("дару", "лекарство", "💊", "Әни дару бирә.", "Мама даёт лекарство.",
     "a small bottle of medicine with a spoon next to it"),
    ("даруханә", "аптека", "🏪", "Бу даруханә.", "Это аптека.",
     "a small pharmacy shop front with a green cross, cartoon style"),
    ("градусник", "градусник", "🌡", "Табиб градусник бирә.", "Врач даёт градусник.",
     "a single medical thermometer, simple and clear"),
    ("сәламәт", "здоровый", "💪", "Мин сәламәт.", "Я здоровый.",
     "a happy healthy child jumping with joy, rosy cheeks, full of energy"),
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
            (THEME_RU, THEME_TT, ICON, max_order + 1, "Здоровье: что болит, кто лечит, чем лечат"),
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
