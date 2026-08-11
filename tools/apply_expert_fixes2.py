# -*- coding: utf-8 -*-
"""Правки по ВТОРОЙ ревизии эксперта по татарскому (2026-07-16).

Ключи — (тема, слово). Использование:
  python tools/apply_expert_fixes2.py <путь_к_app.db>
"""
import sys
import sqlite3

# (тема, text_ru) -> новый text_tt
UPDATE_TT = {
    ("Фрукты/ягоды", "черника"): "кара җиләк",
    ("Одежда и обувь", "носки"): "оекбашлар",
    ("Школа и класс", "цветные карандаши"): "төсле карандашлар",
}

# (тема, text_ru) -> (новый text_ru, новый text_tt|None)
UPDATE_RU = {
    ("Овощи", "овощи"): ("овощ", None),
    ("Семья и дом", "прихожая"): ("коридор", None),
    ("Знакомство и общение", "пожалуйста"): ("пожалуйста (просьба)", None),
    ("Семья и дом", "дядя"): ("старший брат / дядя", None),
    ("Семья и дом", "тетя"): ("старшая сестра / тётя", None),
    ("Знакомство и общение", "я из казани"): ("я из Казани", "мин Казаннан"),
}

# удалить: (тема, text_ru)
DELETE_RU = [
    ("Еда и напитки", "фрукты"),        # дубль темы «Фрукты/ягоды»
]
# удалить по (тема, text_tt)
DELETE_TT = [
    ("Числа (10–19)", "ун"),            # дубль «ун» из «Десятков»
]

# перенести слово в другую тему: (тема_откуда, text_tt) -> тема_куда
MOVE = {
    ("Человек и тело", "кием"): "Одежда и обувь",
    ("Человек и тело", "аяк киеме"): "Одежда и обувь",
}

# (тема, text_ru) -> emoji
UPDATE_EMOJI = {
    ("Время и сезоны", "день рождения"): "🎂",
    ("Время и сезоны", "выходной"): "🛋️",
    ("Время и сезоны", "каникулы"): "🏖️",
    ("Время и сезоны", "сабантуй"): "🤼",
    ("Животные", "насекомое"): "🐛",
    ("Животные", "дикий"): "🐗",
    ("Животные", "животное"): "🐾",
    ("Человек и тело", "язык"): "👅",
    ("Человек и тело", "кровь"): "🩸",
    ("Человек и тело", "шея"): "🦒",
    ("Человек и тело", "спина"): "🦴",
    ("Человек и тело", "живот"): "🎈",
    ("Человек и тело", "смех"): "😂",
    ("Человек и тело", "улыбка"): "😊",
    ("Человек и тело", "слезы"): "😢",
    ("Человек и тело", "голос"): "🎤",
    ("Человек и тело", "ум"): "🧠",
    ("Человек и тело", "сила"): "🏋️",
    ("Человек и тело", "рост"): "📏",
    ("Семья и дом", "чашка"): "☕",
    ("Семья и дом", "кастрюля"): "🍲",
    ("Семья и дом", "игрушка"): "🧸",
    ("Семья и дом", "стена"): "🧱",
    ("Семья и дом", "тарелка"): "🥣",
    ("Семья и дом", "посуда"): "🍽️",
    ("Цвета и формы", "светлый"): "🌕",
    ("Цвета и формы", "темный"): "🌑",
    ("Цвета и формы", "большой"): "🐘",
    ("Цвета и формы", "маленький"): "🐜",
    ("Цвета и формы", "длинный"): "🦒",
    ("Цвета и формы", "короткий"): "🐁",
    ("Действия", "садиться"): "🪑",
    ("Действия", "считать"): "🔢",
    ("Действия", "понимать"): "💡",
    ("Действия", "просыпаться"): "⏰",
    ("Действия", "болеть"): "🤒",
    ("Действия", "встать"): "⬆️",
    ("Действия", "вырезать"): "✂️",
    ("Действия", "раскрашивать"): "🖍️",
    ("Действия", "чистить"): "🪥",
    ("Школа и класс", "библиотека"): "📚",
    ("Школа и класс", "столовая"): "🍽️",
    ("Школа и класс", "спортивный зал"): "⚽",
    ("Школа и класс", "место"): "📍",
    ("Школа и класс", "кабинет"): "🗝️",
    ("Школа и класс", "пенал"): "👝",
    ("Школа и класс", "мел"): "⚪",
    ("Школа и класс", "перемена"): "🤸",
}

# добавить: (тема, text_ru, text_tt, emoji)
ADDITIONS = [
    ("Семья и дом", "младший брат", "эне", "👦"),
    ("Семья и дом", "младшая сестра", "сеңел", "👧"),
    ("Человек и тело", "лицо", "бит", "🙂"),
    ("Человек и тело", "губы", "ирен", "👄"),
    ("Человек и тело", "колено", "тез", "🧎"),
    ("Знакомство и общение", "мне пять лет", "миңа биш яшь", "5️⃣"),
    ("Знакомство и общение", "мне шесть лет", "миңа алты яшь", "6️⃣"),
]

# ---- разбиение больших тем ----
# parent: (новое имя, title_tt, emoji); children: [(имя, title_tt, emoji, [text_tt слов])]
SPLITS = [
    {
        "parent": "Животные",
        "rename": ("Животные: дома и во дворе", "Йорт хайваннары", "🐄"),
        "children": [
            ("Животные: в лесу и зоопарке", "Урманда һәм зоопаркта", "🦁",
             ["куян", "аю", "төлке", "бурсык", "керпе", "бүре", "тиен", "арыслан",
              "юлбарыс", "фил", "маймыл", "урман", "зоопарк", "кыргый", "өн"]),
            ("Птицы, рыбки, букашки", "Кошлар, балыклар, бөҗәкләр", "🐝",
             ["кош", "чыпчык", "карга", "күгәрчен", "тутый кош", "бака", "балык",
              "бөҗәк", "күбәләк", "чебен", "черки", "кырмыска", "бал корты"]),
        ],
    },
    {
        "parent": "Семья и дом",
        "rename": ("Семья и наш дом", "Гаилә һәм өй", "👨‍👩‍👧‍👦"),
        "children": [
            ("Вещи в доме", "Өйдәге әйберләр", "🛋️",
             ["карават", "шкаф", "диван", "кәнәфи", "телевизор", "келәм", "көзге",
              "сәгать", "лампа", "мендәр", "уенчык", "ачкыч", "телефон", "савыт-саба",
              "тәлинкә", "чынаяк", "кашык", "чәнечке", "пычак", "чәйнек", "кәстрүл"]),
        ],
    },
    {
        "parent": "Еда и напитки",
        "rename": ("Продукты и напитки", "Ризыклар һәм эчемлекләр", "🥛"),
        "children": [
            ("Блюда и вкусы", "Ашлар һәм тәмнәр", "🥧",
             ["токмач", "пылау", "өчпочмак", "чәк-чәк", "кыстыбый", "бәлеш", "коймак",
              "кайнатма", "кәнфит", "шоколад", "туңдырма", "торт", "печенье",
              "иртәнге аш", "төшке аш", "кичке аш", "ашамлык", "тәмле", "тәмсез",
              "татлы", "әче", "кайнар", "салкын", "тәмле булсын!"]),
        ],
    },
    {
        "parent": "Школа и класс",
        "rename": ("Школа и урок", "Мәктәп һәм дәрес", "🏫"),
        "children": [
            ("Пенал и рюкзак", "Пенал һәм букча", "✏️",
             ["букча", "пенал", "каләм", "карандаш", "төсле карандашлар", "сызгыч",
              "бетергеч", "очлагыч", "бур", "буяулар", "пумала", "альбом", "дәфтәр",
              "китап", "дәреслек", "көндәлек", "җилем", "кайчы", "кәгазь", "пластилин"]),
        ],
    },
    {
        "parent": "Действия",
        "rename": ("Действия: движемся", "Хәрәкәтләнәбез", "🏃"),
        "children": [
            ("Действия: говорим и думаем", "Сөйлибез һәм уйлыйбыз", "💬",
             ["укый", "яза", "уйлый", "санау", "тыңлау", "карау", "сөйләү", "әйтү",
              "белү", "аңлау", "сорау", "җавап бирү", "күрсәтү", "кабатлау", "оныту",
              "хәтерләү", "эзләү", "табу", "ярату", "ярдәм итү"]),
            ("Действия: играем и мастерим", "Уйныйбыз һәм ясыйбыз", "🧩",
             ["ашый", "җыя", "уйнау", "җырлау", "бию", "йоклау", "уяну", "елау",
              "авыру", "юу", "киенү", "ачу", "ябу", "ясау", "рәсем ясау", "буяу",
              "кисү", "ябыштыру", "чистарту", "сатып алу", "яшәү"]),
        ],
    },
]

# итоговый порядок карты (24 юнита)
REORDER = {
    "Животные: дома и во дворе": 1, "Цифры": 2, "Знакомство и общение": 3,
    "Животные: в лесу и зоопарке": 4, "Цвета и формы": 5, "Семья и наш дом": 6,
    "Вещи в доме": 7, "Продукты и напитки": 8, "Фрукты/ягоды": 9, "Овощи": 10,
    "Блюда и вкусы": 11, "Птицы, рыбки, букашки": 12, "Человек и тело": 13,
    "Одежда и обувь": 14, "Действия: движемся": 15, "Действия: говорим и думаем": 16,
    "Действия: играем и мастерим": 17, "Дни недели": 18, "Время и сезоны": 19,
    "Числа (10–19)": 20, "Десятки": 21, "Школа и урок": 22, "Пенал и рюкзак": 23,
    "Местоимения": 24,
}


def theme_id(cur, title):
    row = cur.execute("select id from themes where title_ru=?", (title,)).fetchone()
    return row[0] if row else None


def word_id_by_ru(cur, theme, ru):
    row = cur.execute(
        "select w.id from words w join themes t on t.id=w.theme_id where t.title_ru=? and lower(w.text_ru)=lower(?)",
        (theme, ru)).fetchone()
    return row[0] if row else None


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    con = sqlite3.connect(db_path)
    con.execute("PRAGMA foreign_keys=ON")
    cur = con.cursor()

    for (theme, ru), tt in UPDATE_TT.items():
        wid = word_id_by_ru(cur, theme, ru)
        if wid is None:
            print(f"SKIP tt (нет): {theme}/{ru}"); continue
        cur.execute("update words set text_tt=?, tts_url=NULL where id=? and text_tt<>?", (tt, wid, tt))
        if cur.rowcount: print(f"TT   {ru} -> {tt}")

    for (theme, ru), (new_ru, new_tt) in UPDATE_RU.items():
        wid = word_id_by_ru(cur, theme, ru)
        if wid is None:
            print(f"SKIP ru (нет): {theme}/{ru}"); continue
        if new_tt:
            cur.execute("update words set text_ru=?, text_tt=?, tts_url=NULL where id=?", (new_ru, new_tt, wid))
        else:
            cur.execute("update words set text_ru=? where id=?", (new_ru, wid))
        print(f"RU   {ru} -> {new_ru}")

    for theme, ru in DELETE_RU:
        wid = word_id_by_ru(cur, theme, ru)
        if wid is None:
            print(f"SKIP del (нет): {theme}/{ru}"); continue
        cur.execute("delete from words where id=?", (wid,))
        print(f"DEL  {theme}/{ru}")

    for theme, tt in DELETE_TT:
        tid = theme_id(cur, theme)
        cur.execute("delete from words where theme_id=? and text_tt=?", (tid, tt))
        if cur.rowcount: print(f"DEL  {theme}/{tt}")

    for (theme_from, tt), theme_to in MOVE.items():
        tid_from, tid_to = theme_id(cur, theme_from), theme_id(cur, theme_to)
        if not tid_from or not tid_to:
            print(f"SKIP move: {theme_from}->{theme_to}"); continue
        cur.execute("update words set theme_id=? where theme_id=? and text_tt=?", (tid_to, tid_from, tt))
        if cur.rowcount: print(f"MOVE {tt}: {theme_from} -> {theme_to}")

    for (theme, ru), emoji in UPDATE_EMOJI.items():
        wid = word_id_by_ru(cur, theme, ru)
        if wid is None:
            print(f"SKIP emo (нет): {theme}/{ru}"); continue
        cur.execute("update words set emoji=? where id=?", (emoji, wid))
    print("эмодзи обновлены")

    for theme, ru, tt, emoji in ADDITIONS:
        tid = theme_id(cur, theme)
        if not tid:
            print(f"SKIP add (нет темы): {theme}"); continue
        exists = cur.execute("select 1 from words where theme_id=? and lower(text_tt)=lower(?)", (tid, tt)).fetchone()
        if exists:
            print(f"SKIP add (есть): {ru}"); continue
        cur.execute("insert into words (theme_id, text_ru, text_tt, emoji) values (?,?,?,?)", (tid, ru, tt, emoji))
        print(f"ADD  {theme}/{ru} — {tt}")

    # --- сплиты ---
    for sp in SPLITS:
        pid = theme_id(cur, sp["parent"])
        if not pid:
            print(f"SKIP split (нет темы): {sp['parent']}"); continue
        new_title, new_tt, new_icon = sp["rename"]
        cur.execute("update themes set title_ru=?, title_tt=?, icon_emoji=? where id=?",
                    (new_title, new_tt, new_icon, pid))
        print(f"RENAME {sp['parent']} -> {new_title}")
        for child_title, child_tt, child_icon, tts in sp["children"]:
            cid = theme_id(cur, child_title)
            if not cid:
                cur.execute("insert into themes (title_ru, title_tt, icon_emoji, order_index) values (?,?,?,99)",
                            (child_title, child_tt, child_icon))
                cid = cur.lastrowid
            moved = 0
            for tt in tts:
                cur.execute("update words set theme_id=? where theme_id=? and text_tt=?", (cid, pid, tt))
                moved += cur.rowcount
            print(f"  CHILD {child_title}: перенесено {moved}/{len(tts)}")

    for title, order in REORDER.items():
        cur.execute("update themes set order_index=? where title_ru=?", (order, title))

    con.commit()
    print("Итог тем:", cur.execute("select count(*) from themes").fetchone()[0],
          "| слов:", cur.execute("select count(*) from words").fetchone()[0])
    for r in cur.execute("select order_index, title_ru, icon_emoji, (select count(*) from words w where w.theme_id=t.id) from themes t order by order_index"):
        print(f"  {r[0]:>2}. {r[2]} {r[1]} ({r[3]})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
