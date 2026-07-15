# -*- coding: utf-8 -*-
"""Правки контента по отчёту эксперта по татарскому языку (июль 2026).

Ключи — (тема, слово), а не id: локальная и боевая базы имеют разные id.
Использование:  python tools/apply_expert_fixes.py <путь_к_app.db> [--cleanup-tests]
--cleanup-tests: удалить qa-пользователей тестирования и осиротевшие записи прогресса.
"""
import sys
import sqlite3

# (тема, text_ru) -> новый text_tt
UPDATE_TT = {
    ("Знакомство и общение", "добрый вечер"): "хәерле кич",       # «кичә» = вчера!
    ("Знакомство и общение", "сколько тебе лет?"): "сиңа ничә яшь?",
    ("Знакомство и общение", "подруга"): "дус кыз",
    ("Знакомство и общение", "пожалуйста"): "зинһар",
    ("Одежда и обувь", "ремень"): "каеш",                          # пута — путы для лошади
    ("Одежда и обувь", "тапочки"): "чүәкләр",
    ("Школа и класс", "портфель"): "букча",
    ("Школа и класс", "точилка"): "очлагыч",
    ("Семья и дом", "чашка"): "чынаяк",
    ("Семья и дом", "кресло"): "кәнәфи",
    ("Семья и дом", "квартира"): "фатир",
    ("Животные", "лапа"): "тәпи",
    ("Животные", "нора"): "өн",
    ("Цвета и формы", "голубой"): "ачык зәңгәр",
    ("Цвета и формы", "темный"): "куе",
    ("Цвета и формы", "розовый"): "алсу",
    ("Человек и тело", "живот"): "эч",
    ("Действия", "встать"): "торып басу",
}

# (тема, text_ru) -> (новый text_ru, новый text_tt или None=не менять)
UPDATE_RU = {
    ("Еда и напитки", "треугольник"): ("эчпочмак (пирожок)", None),
    ("Еда и напитки", "аппетит"): ("приятного аппетита!", "тәмле булсын!"),
}

# удалить: (тема, text_ru)
DELETE_RU = [
    ("Еда и напитки", "картошка"),   # дубль «картофель — бәрәңге» из «Овощей»
    ("Цвета и формы", "форма"),      # «рәвеш» = манера/наречие, не геом. форма
    # инфинитивы-дубли 3-го лица в «Действиях» (бара/бару и т.п.)
    ("Действия", "идти"), ("Действия", "бежать"), ("Действия", "учиться"),
    ("Действия", "кушать"), ("Действия", "дать"), ("Действия", "плыть"),
    ("Действия", "взять"), ("Действия", "писать"), ("Действия", "думать"),
    ("Действия", "собрать"),
]

# (тема, text_ru) -> новый emoji (вводившие в заблуждение заглушки)
UPDATE_EMOJI = {
    ("Животные", "свинья"): "🐷",
    ("Животные", "попугай"): "🦜",
    ("Семья и дом", "часы"): "🕐",
    ("Семья и дом", "ложка"): "🥄",
    ("Семья и дом", "вилка"): "🍴",
    ("Семья и дом", "нож"): "🔪",
    ("Семья и дом", "чайник"): "🫖",
    ("Семья и дом", "тетя"): "👩‍🦰",
    ("Школа и класс", "компьютер"): "💻",
    ("Одежда и обувь", "зонт"): "☂️",
    ("Еда и напитки", "шоколад"): "🍫",
    ("Время и сезоны", "новый год"): "🎄",
    ("Человек и тело", "голова"): "👤",
    ("Человек и тело", "шея"): None,     # 🦒 — жираф; лучше заглушка темы
    ("Человек и тело", "живот"): None,   # 🫃 — неуместно
    ("Человек и тело", "спина"): None,   # 🔙 — значок BACK
    ("Действия", "сидеть тихо"): "🤫",
    ("Действия", "клеить"): "🧴",
    ("Знакомство и общение", "до свидания"): "🚶",
}

# добавить: (тема, text_ru, text_tt, emoji)
ADDITIONS = [
    ("Еда и напитки", "вкусный", "тәмле", "😋"),
    ("Человек и тело", "нога", "аяк", "🦵"),
    ("Время и сезоны", "ночь", "төн", "🌙"),
    ("Время и сезоны", "сабантуй", "сабантуй", "🎉"),
    ("Одежда и обувь", "тюбетейка", "түбәтәй", "🎩"),
    ("Одежда и обувь", "калфак", "калфак", "👒"),
    ("Еда и напитки", "кыстыбый", "кыстыбый", "🫓"),
]

# новый порядок тем: старт с конкретики, фразы «Знакомства» — третьими
REORDER = {
    "Животные": 1, "Цифры": 2, "Знакомство и общение": 3, "Цвета и формы": 4,
    "Семья и дом": 5, "Еда и напитки": 6, "Фрукты/ягоды": 7, "Овощи": 8,
    "Человек и тело": 9, "Одежда и обувь": 10, "Действия": 11, "Дни недели": 12,
    "Время и сезоны": 13, "Числа (10–19)": 14, "Десятки": 15,
    "Школа и класс": 16, "Местоимения": 17,
}


def word_id(cur, theme: str, ru: str):
    row = cur.execute(
        "select w.id from words w join themes t on t.id=w.theme_id where t.title_ru=? and lower(w.text_ru)=lower(?)",
        (theme, ru)).fetchone()
    return row[0] if row else None


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    cleanup = "--cleanup-tests" in sys.argv
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    for (theme, ru), tt in UPDATE_TT.items():
        wid = word_id(cur, theme, ru)
        if wid is None:
            print(f"SKIP (нет): {theme} / {ru}")
            continue
        cur.execute("update words set text_tt=?, tts_url=NULL where id=? and text_tt<>?", (tt, wid, tt))
        if cur.rowcount:
            print(f"TT  {ru} -> {tt}")

    for (theme, ru), (new_ru, new_tt) in UPDATE_RU.items():
        wid = word_id(cur, theme, ru)
        if wid is None:
            print(f"SKIP (нет): {theme} / {ru}")
            continue
        if new_tt:
            cur.execute("update words set text_ru=?, text_tt=?, tts_url=NULL where id=?", (new_ru, new_tt, wid))
        else:
            cur.execute("update words set text_ru=? where id=?", (new_ru, wid))
        print(f"RU  {ru} -> {new_ru}")

    for theme, ru in DELETE_RU:
        wid = word_id(cur, theme, ru)
        if wid is None:
            print(f"SKIP del (нет): {theme} / {ru}")
            continue
        cur.execute("delete from words where id=?", (wid,))
        print(f"DEL {theme} / {ru}")

    for (theme, ru), emoji in UPDATE_EMOJI.items():
        wid = word_id(cur, theme, ru)
        if wid is None:
            continue
        cur.execute("update words set emoji=? where id=?", (emoji, wid))
        print(f"EMO {ru} -> {emoji or '(тема)'}")

    for theme, ru, tt, emoji in ADDITIONS:
        tid_row = cur.execute("select id from themes where title_ru=?", (theme,)).fetchone()
        if not tid_row:
            print(f"SKIP add (нет темы): {theme}")
            continue
        exists = cur.execute(
            "select 1 from words where theme_id=? and (lower(text_tt)=lower(?) or lower(text_ru)=lower(?))",
            (tid_row[0], tt, ru)).fetchone()
        if exists:
            print(f"SKIP add (есть): {ru}")
            continue
        cur.execute("insert into words (theme_id, text_ru, text_tt, emoji) values (?,?,?,?)",
                    (tid_row[0], ru, tt, emoji))
        print(f"ADD {theme} / {ru} — {tt}")

    for title, order in REORDER.items():
        cur.execute("update themes set order_index=? where title_ru=?", (order, title))

    # осиротевший прогресс (фантомные word_id из тестов)
    cur.execute("delete from user_progress where word_id not in (select id from words)")
    print(f"orphan user_progress удалено: {cur.rowcount}")
    cur.execute("delete from user_mistakes where word_id not in (select id from words)")
    print(f"orphan user_mistakes удалено: {cur.rowcount}")

    if cleanup:
        rows = cur.execute(
            "select id, username from users where username like 'qa\\_%' escape '\\' "
            "or length(username) > 32 or instr(username, char(39)) > 0 or instr(username, '--') > 0"
        ).fetchall()
        for uid, name in rows:
            for table in ("user_progress", "user_mistakes", "unit_progress", "daily_lessons",
                          "user_stickers", "lesson_results"):
                try:
                    cur.execute(f"delete from {table} where user_id=?", (uid,))
                except sqlite3.OperationalError:
                    pass  # таблицы может не быть до первого старта нового кода
            cur.execute("delete from users where id=?", (uid,))
            print(f"USER del: {uid} {name[:40]!r}")

    con.commit()
    words_total = cur.execute("select count(*) from words").fetchone()[0]
    print(f"Готово. Слов в базе: {words_total}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
