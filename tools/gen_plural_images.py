# -*- coding: utf-8 -*-
"""Картинки «много предметов» для тренажёра множественного числа.

У всех слов в базе картинка с ОДНИМ объектом. Чтобы ребёнок мог выбрать между
«песи» и «песиләр» на слух, нужна вторая картинка — с несколькими такими же
объектами. Кладём их отдельно: static/image/plural/word_{id}.png (в БД не
попадают, движок берёт по id).

Запуск: python tools/gen_plural_images.py [--db app.db] [--only песи,эт]
"""
import argparse
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

# только те слова, где «три штуки» рисуются понятно и не сливаются в кашу
PLURAL_PROMPTS = {
    "песи": "exactly three cute cats sitting side by side in a row",
    "эт": "exactly three dogs sitting side by side in a row",
    "ат": "exactly three horses standing side by side",
    "каз": "exactly three white geese standing in a row",
    "куян": "exactly three rabbits sitting side by side",
    "аю": "exactly three brown bears standing side by side",
    "тычкан": "exactly three small grey mice in a row",
    "алма": "exactly three red apples in a row",
    "китап": "exactly three closed books stacked and standing together",
    "дәфтәр": "exactly three school notebooks lying side by side",
    "карандаш": "exactly three colored pencils lying side by side",
    "балык": "exactly three fish swimming side by side",
    "күбәләк": "exactly three butterflies flying together",
    "кишер": "exactly three carrots lying side by side",
    "каләм": "exactly three pens lying side by side",
}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    ap.add_argument("--only")
    ap.add_argument("--delay", type=float, default=3.0)
    args = ap.parse_args()

    if not os.getenv("CF_API_TOKEN") and os.path.exists("cf.env"):
        for line in open("cf.env"):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

    from app.config import STATIC_DIR
    from app.imagegen import PROMPT_EN_CF, generate_cf
    from app.media import optimize_image
    from tools.gen_theme_images import _pollinations

    only = {s.strip().lower() for s in args.only.split(",")} if args.only else None
    con = sqlite3.connect(args.db)
    target_dir = os.path.join(STATIC_DIR, "image", "plural")
    os.makedirs(target_dir, exist_ok=True)

    ok = fail = 0
    for tt, en in PLURAL_PROMPTS.items():
        if only and tt not in only:
            continue
        row = con.execute("select id from words where lower(text_tt)=?", (tt,)).fetchone()
        if not row:
            print(f"пропуск {tt}: нет в базе")
            continue
        dst = os.path.join(target_dir, f"word_{row[0]}.png")
        if os.path.exists(dst):
            print(f"skip {tt} (есть)")
            continue
        prompt = PROMPT_EN_CF.format(en=en)
        try:
            png = await generate_cf(prompt)
        except Exception as e:
            png = await _pollinations(prompt)
            if png is None:
                fail += 1
                print(f"ERR {tt}: {e}")
                await asyncio.sleep(args.delay * 3)
                continue
            print("  (CF недоступен, взял Pollinations)")
        png = optimize_image(png) or png
        with open(dst, "wb") as f:
            f.write(png)
        ok += 1
        print(f"ok {tt} → word_{row[0]}.png ({len(png) // 1024} КБ)")
        await asyncio.sleep(args.delay)
    print(f"готово: {ok} картинок, ошибок {fail}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
