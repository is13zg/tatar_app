# -*- coding: utf-8 -*-
"""Озвучка связок «вопрос → пауза → ответ» для темы вопросительных слов.

Движок tat-tts не делает паузу на знаках препинания: «Бу кем? Бу — малай.»
звучит сплошным потоком за 1.5 с, и нечитающий ребёнок не отделяет вопрос
от ответа. Поэтому вопрос и ответ синтезируются раздельно и склеиваются
с тишиной посередине.

Склейка идёт по СЕМПЛАМ (audioop), а не по сырым байтам: побайтовая
конкатенация давала сдвиг и характерный треск. Результат нормализуется
до 0.89 пика с мягкими фейдами — без клиппинга.

Запуск в контейнере:
  docker exec tatar_app python tools/gen_qa_audio.py --db /usr/src/app/data/app.db
"""
import argparse
import asyncio
import audioop
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
TARGET_PEAK = 0.89
FADE_MS = 8


def _url_to_path(url: str) -> str:
    return os.path.join(STATIC_DIR, url.replace("/static/", "", 1).split("?")[0])


def _read(path: str) -> tuple[bytes, int, int, int]:
    with wave.open(path) as w:
        if w.getsampwidth() != 2:
            raise RuntimeError(f"{path}: ожидается 16 бит")
        frames = w.readframes(w.getnframes())
        if w.getnchannels() == 2:
            frames = audioop.tomono(frames, 2, 0.5, 0.5)
        return frames, w.getframerate(), 2, 1


def _fade(data: bytes, rate: int) -> bytes:
    """Мягкие края, чтобы стык не давал щелчка."""
    n = min(int(rate * FADE_MS / 1000), len(data) // 4)
    if n <= 0:
        return data
    out = bytearray(data)
    for i in range(n):
        k = i / n
        for pos, mul in ((i * 2, k), (len(data) - (i + 1) * 2, k)):
            sample = int.from_bytes(out[pos:pos + 2], "little", signed=True)
            out[pos:pos + 2] = int(sample * mul).to_bytes(2, "little", signed=True)
    return bytes(out)


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
        q_frames, rate, sw, ch = _read(_url_to_path(await synthesize_to_file(q_tt)))
        a_frames, rate_a, _, _ = _read(_url_to_path(await synthesize_to_file(a_tt)))
        if rate_a != rate:
            a_frames = audioop.ratecv(a_frames, 2, 1, rate_a, rate, None)[0]

        silence = b"\x00\x00" * int(rate * PAUSE_SEC)          # ровно по семплам, без байтового сдвига
        merged = _fade(q_frames, rate) + silence + _fade(a_frames, rate)

        peak = audioop.max(merged, 2)
        if peak:
            gain = min(TARGET_PEAK * 32767 / peak, 4.0)
            merged = audioop.mul(merged, 2, gain)              # снимаем клиппинг и выравниваем громкость
        merged = audioop.bias(merged, 2, -int(audioop.avg(merged, 2)))  # убираем постоянную составляющую

        target = os.path.join(out_dir, f"sentence_{row['id']}.wav")
        with wave.open(target, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(merged)
        con.execute("update words set sentence_audio_url=? where id=?",
                    (f"/static/voice/uploads/sentence_{row['id']}.wav?v={int(time.time())}", row["id"]))
        done += 1
        print(f"ok {tt}: «{q_tt}» + {PAUSE_SEC}с + «{a_tt}» "
              f"({len(merged) // 2 / rate:.2f}с, пик {audioop.max(merged, 2)})")
        await asyncio.sleep(0.2)
    con.commit()
    print(f"готово: {done} связок")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    asyncio.run(main())
