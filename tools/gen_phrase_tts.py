# -*- coding: utf-8 -*-
"""Предозвучка служебных татарских фраз, которые движок берёт только из кэша:

  • «Кем юк?» / «Нәрсә юк?» и ответы «X юк.» — игра «кто убежал»;
  • «Нәрсә белән яза?» и ответы «Каләм белән.» — упражнение «чем это делают».

Запуск в контейнере:
  docker exec tatar_app python tools/gen_phrase_tts.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

from app.routers.lessons import WITH_WHAT  # noqa: E402
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    args = ap.parse_args()

    phrases = ["Кем юк?", "Нәрсә юк?"]
    con = sqlite3.connect(args.db)
    # «X юк.» для всех слов с картинкой — фраза звучит после верного ответа
    for (tt,) in con.execute(
        "select text_tt from words where image_url is not null and image_url not like '%noimg%'"
    ):
        phrases.append(f"{tt} юк.")
    for verb, tool in WITH_WHAT.items():
        phrases.append(f"Нәрсә белән {verb}?")
        phrases.append(f"{tool.capitalize()} белән.")

    done = skip = err = 0
    for p in phrases:
        if cached_tts_url(p):
            skip += 1
            continue
        try:
            await synthesize_to_file(p)
            done += 1
            if done % 25 == 0:
                print(f"...{done}")
            await asyncio.sleep(0.25)
        except Exception as e:
            err += 1
            print(f"ERR {p!r}: {e}")
            if err >= 10:
                sys.exit("слишком много ошибок TTS")
            await asyncio.sleep(3)
    print(f"готово: новых {done}, в кэше {skip}, ошибок {err}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
