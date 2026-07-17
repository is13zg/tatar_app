# -*- coding: utf-8 -*-
"""Предозвучка вопросов и отрицаний: «Бу песиме?», «Бу песи түгел.», плитки «песиме»,
служебные «бу»/«түгел»/«Әйе!»/«Юк!». Кэш — app.tts (alsu), движок ищет те же строки.

Запуск в контейнере: docker exec tatar_app python tools/gen_qneg_tts.py
"""
import asyncio
import os
import sqlite3
import sys

sys.path.insert(0, os.getcwd())

from app.qneg import (AYE, BU, QNEG_EXCLUDE, QUESTION_THEMES, TUGEL, YUK,  # noqa: E402
                      negation_phrase, qneg_eligible, question_phrase, question_word)
from app.tts import cached_tts_url, synthesize_to_file  # noqa: E402

DB = os.environ.get("QNEG_DB", "/usr/src/app/data/app.db")


async def main() -> None:
    con = sqlite3.connect(DB)
    rows = con.execute(
        "select w.text_tt from words w join themes t on t.id = w.theme_id "
        "where t.title_ru in ({})".format(",".join("?" * len(QUESTION_THEMES))),
        list(QUESTION_THEMES),
    ).fetchall()
    words = [r[0] for r in rows if qneg_eligible(r[0])]
    print(f"слов: {len(words)} (исключено: {len(rows) - len(words)})")

    texts = [AYE, YUK, BU, TUGEL]
    for w in words:
        texts += [question_phrase(w), negation_phrase(w), question_word(w)]

    done = skip = err = 0
    for t in texts:
        if cached_tts_url(t):
            skip += 1
            continue
        try:
            await synthesize_to_file(t)
            done += 1
            if done % 25 == 0:
                print(f"...{done}")
            await asyncio.sleep(0.3)
        except Exception as e:
            err += 1
            print(f"ERR {t!r}: {e}")
            if err >= 10:
                sys.exit("слишком много ошибок TTS — прерываюсь")
            await asyncio.sleep(3)
    print(f"готово: новых {done}, в кэше {skip}, ошибок {err}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
