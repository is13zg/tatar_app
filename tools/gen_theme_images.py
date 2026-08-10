# -*- coding: utf-8 -*-
"""Картинки для слов темы через Cloudflare Workers AI (flux-1-schnell).

Промпты берутся из seed-модуля темы: последний элемент кортежа WORDS —
английское описание. Английский обязателен: русские промпты рисуют не то.

  python tools/gen_theme_images.py --seed tools/seed_adjectives.py [--db app.db] [--only калын,юка]
"""
import argparse
import asyncio
import importlib.util
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.getcwd())


async def _pollinations(prompt: str):
    """Запасной генератор: flux без ключа. None — если тоже не вышло."""
    import urllib.parse

    import httpx
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=768&height=768&nologo=true"
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
            r = await c.get(url)
            r.raise_for_status()
            return r.content if r.content[:4] in (b"\x89PNG", b"\xff\xd8\xff\xe0") or len(r.content) > 5000 else None
    except Exception:
        return None


def load_seed(path: str):
    spec = importlib.util.spec_from_file_location("_seed_mod", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True, help="путь к tools/seed_*.py с THEME_RU и WORDS")
    ap.add_argument("--db", default="app.db")
    ap.add_argument("--only", help="через запятую: только эти text_tt")
    ap.add_argument("--delay", type=float, default=3.0)
    args = ap.parse_args()

    # ключи Cloudflare: из окружения или из cf.env в корне (в git не хранится)
    if not os.getenv("CF_API_TOKEN") and os.path.exists("cf.env"):
        for line in open("cf.env"):
            line = line.strip()
            if line and "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k, v)

    from app.config import STATIC_DIR
    from app.imagegen import PROMPT_EN_CF, generate_cf
    from app.media import optimize_image

    seed = load_seed(args.seed)
    only = {s.strip().lower() for s in args.only.split(",")} if args.only else None

    con = sqlite3.connect(args.db)
    theme = con.execute("select id from themes where title_ru=?", (seed.THEME_RU,)).fetchone()
    if not theme:
        sys.exit(f"тема «{seed.THEME_RU}» не найдена — сначала прогоните seed")

    ok = fail = 0
    target_dir = os.path.join(STATIC_DIR, "image", "uploads")
    os.makedirs(target_dir, exist_ok=True)
    for row in seed.WORDS:
        tt, en = row[0], row[-1]
        if only and tt.lower() not in only:
            continue
        w = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                        (theme[0], tt)).fetchone()
        if not w:
            print(f"пропуск {tt}: нет в БД")
            continue
        prompt = PROMPT_EN_CF.format(en=en)
        try:
            png = await generate_cf(prompt)
        except Exception as e:
            # у Cloudflare бывает исчерпание лимита — до Pollinations доходим без ключа
            png = await _pollinations(prompt)
            if png is None:
                fail += 1
                print(f"ERR {tt}: {e}")
                await asyncio.sleep(args.delay * 3)
                continue
            print(f"  (CF недоступен, взял Pollinations)")
        png = optimize_image(png) or png
        with open(os.path.join(target_dir, f"word_{w[0]}.png"), "wb") as f:
            f.write(png)
        con.execute("update words set image_url=?, image_prompt=?, image_flag=0 where id=?",
                    (f"/static/image/uploads/word_{w[0]}.png?v={int(time.time())}", prompt, w[0]))
        con.commit()
        ok += 1
        print(f"ok {tt} ({len(png) // 1024} КБ)")
        await asyncio.sleep(args.delay)
    print(f"готово: {ok} картинок, ошибок {fail}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
