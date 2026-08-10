# -*- coding: utf-8 -*-
"""Предозвучка тренажёра отрицания: «Ул йөзәме?», «Әйе, ул йөзә.», «Юк, ул йөзми.»

Формы берутся из app/forms.py (выверены носителем). Движок использует
только те фразы, что уже лежат в кэше TTS.

Запуск в контейнере:
  docker exec tatar_app python tools/gen_negation_tts.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

from app.forms import NEGATIVE_TT  # noqa: E402
from app.qneg import question_particle  # noqa: E402
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    have = {r[0].lower() for r in con.execute(
        "select text_tt from words where image_url is not null and image_url not like '%noimg%'")}

    phrases = []
    for verb, neg in NEGATIVE_TT.items():
        if verb not in have:
            continue  # без картинки упражнение всё равно не соберётся
        phrases += [f"Ул {verb}{question_particle(verb)}?", f"Әйе, ул {verb}.", f"Юк, ул {neg}."]

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
    print(f"готово: новых {done}, в кэше {skip}, ошибок {err} (глаголов с картинкой: {len(phrases)//3})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
