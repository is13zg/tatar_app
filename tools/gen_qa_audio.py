# -*- coding: utf-8 -*-
"""Озвучка связок «вопрос → пауза → ответ» для темы вопросительных слов.

Движок tat-tts не делает паузу на знаках препинания: «Бу кем? Бу — малай.»
звучит сплошным потоком за 1.5 с, и нечитающий ребёнок не отделяет вопрос
от ответа. Поэтому вопрос и ответ синтезируются раздельно и склеиваются
с тишиной посередине.

Запуск в контейнере:
  docker exec tatar_app python tools/gen_qa_audio.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import io
import os
import sqlite3
import sys
import time
import wave

sys.path.insert(0, os.getcwd())

from app.config import STATIC_DIR  # noqa: E402
from app.tts import synthesize_to_file  # noqa: E402
from tools.seed_question_words import THEME_RU, WORDS  # noqa: E402

PAUSE_SEC = 0.7


def _read(path: str):
    with wave.open(path) as w:
        return w.getparams(), w.readframes(w.getnframes())


def _url_to_path(url: str) -> str:
    return os.path.join(STATIC_DIR, url.replace("/static/", "", 1).split("?")[0])


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="app.db")
    args = ap.parse_args()

    con = sqlite3.connect(args.db)
    con.row_factory = sqlite3.Row
    theme = con.execute("select id from themes where title_ru=?", (THEME_RU,)).fetchone()
    if not theme:
        sys.exit(f"тема «{THEME_RU}» не найдена")

    out_dir = os.path.join(STATIC_DIR, "voice", "uploads")
    os.makedirs(out_dir, exist_ok=True)
    done = 0
    for tt, ru, emoji, q_tt, a_tt, s_ru in WORDS:
        row = con.execute("select id from words where theme_id=? and lower(text_tt)=lower(?)",
                          (theme["id"], tt)).fetchone()
        if not row:
            print(f"пропуск {tt}: нет в БД")
            continue
        q_url = await synthesize_to_file(q_tt)
        a_url = await synthesize_to_file(a_tt)
        (params, q_frames) = _read(_url_to_path(q_url))
        (_, a_frames) = _read(_url_to_path(a_url))
        silence = b"\x00" * int(params.framerate * params.sampwidth * params.nchannels * PAUSE_SEC)

        target = os.path.join(out_dir, f"sentence_{row['id']}.wav")
        with wave.open(target, "wb") as w:
            w.setparams(params)
            w.writeframes(q_frames + silence + a_frames)
        url = f"/static/voice/uploads/sentence_{row['id']}.wav?v={int(time.time())}"
        con.execute("update words set sentence_audio_url=? where id=?", (url, row["id"]))
        done += 1
        print(f"ok {tt}: «{q_tt}» + пауза {PAUSE_SEC}с + «{a_tt}»")
        await asyncio.sleep(0.2)
    con.commit()
    print(f"готово: {done} связок")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
