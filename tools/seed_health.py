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
    # четыре первых слова легко срисовать одинаково («грустный ребёнок в шарфе»),
    # поэтому у каждого свой опознавательный знак: зуб, горло, локоть, брызги
    ("авырта", "болит", "🤕", "Теш авырта.", "Зуб болит.",
     "a crying boy with a swollen cheek and a white bandage tied around his head and jaw, "
     "red pain rays around the cheek, one tooth marked with a red spot"),
    ("тамак", "горло", "😣", "Тамак авырта.", "Горло болит.",
     "big close up of a child wide open mouth from the front, the red throat clearly visible inside, "
     "a doctor small flashlight pointing into it"),
    ("йөткерә", "кашляет", "😷", "Кыз йөткерә.", "Девочка кашляет.",
     "a girl coughing hard into her bent elbow, mouth wide open, head down, "
     "big puffs of air and motion lines bursting from her mouth"),
    ("төчкерә", "чихает", "🤧", "Бала төчкерә.", "Ребёнок чихает.",
     "a child sneezing explosively, eyes squeezed shut, head thrown back, "
     "a wide spray of tiny droplets flying out, a paper tissue in one hand"),
    ("дәвалый", "лечит", "👨‍⚕️", "Табиб дәвалый.", "Врач лечит.",
     "a doctor in a white coat with a head mirror pressing a stethoscope to the chest of "
     "a child sitting on an examination couch, side view, only two people"),
    ("хастаханә", "больница", "🏥", "Хастаханә зур.", "Больница большая.",
     "a big friendly hospital building with a red cross, cartoon style"),
    ("дару", "лекарство", "💊", "Әни дару бирә.", "Мама даёт лекарство.",
     "a small bottle of medicine with a spoon next to it"),
    ("даруханә", "аптека", "🏪", "Бу даруханә.", "Это аптека.",
     "a small pharmacy shop front with a green cross, cartoon style"),
    ("градусник", "градусник", "🌡", "Табиб градусник бирә.", "Врач даёт градусник.",
     "one long thin straight stick thermometer standing upright, thin red line inside the glass tube, "
     "silver tip at the bottom, nothing round"),
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
            con.execute("update words set text_ru=?, emoji=?, sentence_tt=?, sentence_ru=?, "
                        "sentence_audio_url = case when sentence_tt=? then sentence_audio_url else null end "
                        "where id=?",
                        (ru, emoji, s_tt, s_ru, s_tt, ex["id"]))
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
