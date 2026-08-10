# -*- coding: utf-8 -*-
"""Правки по итогам языковой ревизии нового контента (носитель, 2026-08-10).

Ключ — text_tt (id локальной и боевой базы могут расходиться).
После прогона переозвучить изменённые предложения: POST /admin/tts_sentences_all
не поможет (у них уже есть аудио), поэтому скрипт сам сбрасывает
sentence_audio_url у тронутых записей.

Запуск: python tools/apply_review_fixes.py [путь_к_БД]
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "app.db"

# text_tt: {поле: новое значение}
FIXES = {
    # ВНИМАНИЕ: «кайсы?» и «иске» здесь намеренно отсутствуют — их предложения
    # правил владелец вручную через админку, скрипт их больше не трогает.
    # лексика: «делать суп» — калька, готовят «пешерә»
    "пешекче": {"sentence_tt": "Пешекче аш пешерә.", "sentence_ru": "Повар готовит суп."},
    # молоко даёт корова, доярка — доит
    "сыер савучы": {"sentence_tt": "Сыер савучы сыер сава.", "sentence_ru": "Доярка доит корову."},
    # очкыч/очучы на слух почти одинаковы — разводим предложения
    "очучы": {"sentence_tt": "Очучы очкычта.", "sentence_ru": "Лётчик в самолёте."},
    # «прощай» для ребёнка звучит как расставание навсегда
    "Хуш!": {"text_ru": "до свидания!", "sentence_ru": "До свидания, бабушка! (уезжает из деревни)"},
    # число: в татарском парные части тела в ед. ч.
    "чиста": {"sentence_ru": "Рука чистая."},
    "пычрак": {"sentence_ru": "Нога грязная."},
    "тәрбияче": {"sentence_ru": "Воспитатель хороший."},
    # рыбак ловит, а не ищет
    "балыкчы": {"sentence_tt": "Балыкчы балык тота.", "sentence_ru": "Рыбак ловит рыбу."},
    # «бии» о юле — метафора; «бара» о санках — они не едут сами
    "бөтерчек": {"text_ru": "юла, волчок", "sentence_tt": "Бөтерчек әйләнә.", "sentence_ru": "Юла крутится."},
    "чана": {"sentence_tt": "Чана шуа.", "sentence_ru": "Санки катятся."},
    # шар в татарском — геометрический; уменьшительные в переводе сбивают
    "шар": {"text_ru": "шар"},
    "машина": {"text_ru": "машина"},
    "кораб": {"text_ru": "корабль"},
    "сыбызгы": {"text_ru": "свисток"},
    "кирмән": {"text_ru": "кремль"},
    # килә = приближается
    "автобус": {"sentence_ru": "Автобус подъезжает."},
    # нормативное раздельное написание
    "сусипкеч": {"text_tt": "су сипкеч"},
    # именное предложение → с глаголом, естественнее как образец
    "бакча": {"text_ru": "сад", "sentence_tt": "Бакчада алма үсә.", "sentence_ru": "В саду растёт яблоко."},
    "даруханә": {"sentence_tt": "Бу — даруханә."},
    "коры": {"sentence_ru": "Платье сухое."},
}


def main() -> None:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    changed = skipped = 0
    for tt, fields in FIXES.items():
        row = con.execute("select id, text_tt, text_ru, sentence_tt, sentence_ru from words "
                          "where lower(text_tt)=lower(?)", (tt,)).fetchone()
        if not row:
            print(f"пропуск «{tt}»: нет в базе")
            skipped += 1
            continue
        sets, vals = [], []
        for col, val in fields.items():
            if row[col] != val:
                sets.append(f"{col}=?")
                vals.append(val)
        if not sets:
            continue
        # текст предложения изменился — старая озвучка больше не подходит
        if "sentence_tt" in fields:
            sets.append("sentence_audio_url=NULL")
        # изменился сам татарский текст — сбрасываем и озвучку слова
        if "text_tt" in fields:
            sets.append("tts_url=NULL")
            sets.append("audio_url=NULL")
        vals.append(row["id"])
        con.execute(f"update words set {', '.join(sets)} where id=?", vals)
        changed += 1
        print(f"ok  {tt} -> {', '.join(fields)}")
    con.commit()
    print(f"\nизменено записей: {changed}, пропущено: {skipped}")
    print("дальше: POST /admin/tts_all и /admin/tts_sentences_all — они доозвучат сброшенное")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
