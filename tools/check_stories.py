# -*- coding: utf-8 -*-
"""Проверка мини-историй по базе: каждое слово должно быть пройдено.

Считает для каждой истории минимальную позицию юнита, раньше которой её
показывать нельзя, и ловит три ошибки, которые на глаз не видны:
слово вообще не из курса, подлежащие разного одушевления (вопрос «Кем?»
тогда сам выдаёт ответ) и отсутствие картинки у подлежащего.

  python tools/check_stories.py [путь_к_БД]
"""
import re
import sqlite3
import sys

sys.path.insert(0, ".")
from tools.stories import STORIES  # noqa: E402

# служебные слова: связки и вопросительные, они звучат в каждом уроке
FUNCTION_WORDS = {"кем", "нәрсә", "бу", "һәм"}
# одушевлённость — по темам, как в движке (ANIMATE_THEMES)
ANIMATE_THEMES = {"Животные: дома и во дворе", "Животные: в лесу и зоопарке",
                  "Птицы, рыбки, букашки", "Семья и наш дом", "Профессии"}


def main() -> None:
    db = sys.argv[1] if len(sys.argv) > 1 else "app.db"
    con = sqlite3.connect(db)
    known = {}
    for tt, order, theme, img in con.execute(
        "select lower(w.text_tt), t.order_index, t.title_ru, w.image_url "
        "from words w join themes t on t.id=w.theme_id"
    ):
        # слово может встречаться в нескольких темах — берём самое раннее появление
        if tt not in known or order < known[tt][0]:
            known[tt] = (order, theme, img)

    # 66 записей курса состоят из двух слов («басып тора», «бал корты») — их надо
    # вычёркивать из фразы целиком, иначе токенизатор режет их пополам
    multi = sorted((w for w in known if " " in w), key=len, reverse=True)

    def tokens(text: str) -> list[str]:
        low = text.lower()
        found = []
        for m in multi:
            if m in low:
                found.append(m)
                low = low.replace(m, " ")
        return found + [w for w in re.split(r"[^\wәөүҗңһӘӨҮҖҢҺ-]+", low) if w]

    problems = 0
    print("%-16s %-5s %s" % ("история", "юнит", "замечания"))
    for st in STORIES:
        words = []
        for tt_s, _ru, _subj in st["parts"]:
            words += tokens(tt_s)
        for q in st["questions"]:
            words += tokens(q["tt"])
        words = [w for w in words if w and w not in FUNCTION_WORDS]

        notes, unit = [], 0
        for w in words:
            if w not in known:
                notes.append("НЕТ В КУРСЕ: " + w)
                problems += 1
            else:
                unit = max(unit, known[w][0])

        subjects = [s for _tt, _ru, s in st["parts"]]
        answers = [q["answer"] for q in st["questions"]]
        for a in answers:
            if a not in subjects:
                notes.append("ответ не среди подлежащих: " + a)
                problems += 1
        if len(set(answers)) < len(answers):
            notes.append("оба вопроса про одного героя — второй не добавляет нагрузки")
            problems += 1
        kinds, tiles = set(), set()
        for s in subjects:
            if s.lower() not in known:
                notes.append("подлежащее не из курса: " + s)
                problems += 1
                continue
            _o, theme, img = known[s.lower()]
            kinds.add(theme in ANIMATE_THEMES)
            tiles.add(bool(img and "noimg" not in img))
        if len(kinds) > 1:
            notes.append("подлежащие разного одушевления — вопрос выдаёт ответ")
            problems += 1
        if len(tiles) > 1:
            notes.append("часть подлежащих фото, часть эмодзи — ответ виден по виду плитки")
            problems += 1

        print("%-16s %-5d %s" % (st["key"], unit, "; ".join(notes) if notes else "ок"))

    print("\nисторий: %d, проблем: %d" % (len(STORIES), problems))
    by_unit = {}
    for st in STORIES:
        words = []
        for tt_s, _ru, _s in st["parts"]:
            words += tokens(tt_s)
        u = max((known[w][0] for w in words if w in known), default=0)
        by_unit.setdefault(u, []).append(st["key"])
    print("доступность по пути:")
    for u in sorted(by_unit):
        print("   с юнита %-3d %s" % (u, ", ".join(by_unit[u])))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
