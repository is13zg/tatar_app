# -*- coding: utf-8 -*-
"""Перестановка юнитов на карте пути.

Методист: игрушки — самая близкая пятилетке тема, ей не место в конце; а признаки
предмета («какой?») идут сразу за цветами, потому что цвет — тоже признак.

Прогресс детей не страдает: замок теперь считается от самого дальнего пройденного
юнита, поэтому вставленная в начало тема просто появляется как доступная.

  python tools/reorder_units.py --db app.db [--dry]
"""
import argparse
import sqlite3
import sys

# тема -> позиция, на которую её ставим (1 = самое начало); применяются по порядку
MOVES = [
    ("Игрушки", 4),
    ("Нинди? Какой предмет", 9),
    # Послелоги — сразу за «Вещами в доме»: там живёт карават, на который
    # ставят кошку. Раньше нельзя — не на что ставить, позже незачем: это
    # первая возможность сказать предложение из трёх слов.
    ("Кайда? Где что лежит", 12),
    # Погода — за «Одеждой», чтобы состыковаться с «Одень Марата».
    ("Һава торышы. Погода", 17),
    # Настроения — за «Лицом и головой»: эмоция ложится на выученное лицо.
    ("Кәеф ничек? Настроения", 23),
    # Пожелания — сразу после «Блюд и вкусов»: там только что выучено «тәмле»
    # и «тәмле булсын!», «Тәмле төшләр!» подхватывается без шва. Держать
    # ежевечернее «Тыныч йокы!» на последней позиции карты было нельзя.
    ("Добрые пожелания", 22),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    ap.add_argument("--dry", action="store_true", help="только показать новый порядок")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    order = [r[0] for r in con.execute("select title_ru from themes order by order_index, id")]

    for title, pos in MOVES:
        if title not in order:
            sys.exit(f"тема «{title}» не найдена")
        order.remove(title)
        order.insert(pos - 1, title)

    for i, title in enumerate(order, start=1):
        con.execute("update themes set order_index=? where title_ru=?", (i, title))
        mark = "  <—" if any(title == t for t, _ in MOVES) else ""
        print(f"{i:3} {title}{mark}")
    if args.dry:
        con.rollback()
        print("\n--dry: изменения не сохранены")
    else:
        con.commit()
        print("\nпорядок сохранён")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
