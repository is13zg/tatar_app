# -*- coding: utf-8 -*-
"""Озвучка русских инструкций.

ВАЖНО (2026-08): Сбер закрыл Freemium для физлиц с 15.07.2026 — старые ключи
отдают 402 и не восстановятся. Новый движок по умолчанию — Яндекс SpeechKit
(голос marina, амплуа friendly). Уже озвученные Сбером файлы не трогаем:
скрипт пропускает всё, для чего файл уже существует.

ВНИМАНИЕ: в репозитории лежат только файлы, озвученные Яндексом. Старые
сберовские инструкции живут ТОЛЬКО на проде — если прогнать этот скрипт на
чистой копии, он озвучит их заново и голос на проде поедет. Заливать на
сервер поимённо то, что действительно новое, а не всю папку.

Ключ Яндекса: env YANDEX_API_KEY или строка YANDEX_API_KEY=... в yandex.env
в корне проекта (в git не хранится).

Нюанс амплуа: у marina есть neutral / whisper / friendly. Значения good и evil
API принимает молча, но откатывает в нейтральный — «дружелюбно» это именно
emotion=friendly (проверено сравнением байтов ответа).

Использование:
  python tools/gen_ru_instructions.py --out static/voice/ru
  SALUTE_AUTH_KEYS=... python tools/gen_ru_instructions.py --engine sber   # legacy
"""
import argparse
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

OAUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
TTS_URL = "https://smartspeech.sber.ru/rest/v1/text:synthesize"
VOICE = "May_24000"  # тёплый женский голос

# ключ файла -> текст (ключи должны совпадать с INSTR_AUDIO в static/exercises.js)
INSTRUCTIONS = {
    "novoe_slovo": "Новое слово!",
    "najdi_kartinku": "Послушай и найди картинку",
    "pravilnaya_kartinka": "Это правильная картинка?",
    "najdi_pary": "Найди пары",
    "razlozhi_po_korzinkam": "Разложи по корзинкам",
    "vyberi_knopku": "Выбери кнопку со словом с картинки",
    "soberi_slovo": "Собери слово из букв",
    "soberi_predlozhenie": "Собери предложение из слов",
    "chto_v_korobke": "Что в коробке? Нажми!",
    "kto_v_teni": "Кто прячется в тени? Нажми!",
    "raskras_kartinku": "Раскрась картинку! Нажимай!",
    "pomogi_vyrasti": "Помоги вырасти! Нажимай!",
    "lopni_puzyr": "Лопни пузырь со словом!",
    "pokormi_akbaya": "Покорми Акбая!",
    "zapomni_kto": "Запомни, кто здесь!",
    "kto_ubezhal": "Кто убежал? Найди!",
    "lovi_tolko": "Лови только то, что я называю!",
    "otkryvaj_okoshki": "Открывай окошки и запоминай!",
    "posveti_fonarikom": "Посвети! Кто прячется в темноте?",
    "povtori_cepochku": "Повтори цепочку!",
    "chto_lishnee": "Что здесь лишнее?",
    "najdi_naoborot": "Найди наоборот!",
    "otvet_na_vopros": "Ответь на вопрос!",
    "vyberi_kakoy": "Выбери: какой?",
    "chem_delayut": "Чем это делают?",
    "odin_ili_mnogo": "Один или много?",
    "oden_marata": "Одень Марата по погоде!",
    "gde_koshka": "Где кошка?",
    "seychas_ili_uzhe": "Сейчас или уже?",
    "skolko_predmetov": "Сколько предметов?",
    "pochemu_kakoy": "Почему? Выбери, какой он",
    "povtori_za_diktorom": "Повтори за диктором",
    "molodec": "Молодец!",
    "molodec_otlichno": "Молодец! Отлично!",
}


class SaluteTTS:
    """Синтез с ротацией нескольких авторизационных ключей."""

    def __init__(self, auth_keys: list[str]) -> None:
        self.keys = auth_keys
        self.tokens: dict[int, str] = {}
        self.idx = 0
        # цепочка НУЦ Минцифры обычно не установлена в системе — отключаем проверку
        self.client = httpx.Client(verify=False, timeout=60)

    def _token(self, i: int) -> str:
        if i not in self.tokens:
            r = self.client.post(
                OAUTH_URL,
                headers={
                    "Authorization": f"Basic {self.keys[i]}",
                    "RqUID": str(uuid.uuid4()),
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                data={"scope": "SALUTE_SPEECH_PERS"},
            )
            r.raise_for_status()
            self.tokens[i] = r.json()["access_token"]
        return self.tokens[i]

    def synth(self, text: str) -> bytes:
        last_err: Exception | None = None
        for attempt in range(len(self.keys)):
            i = self.idx % len(self.keys)
            self.idx += 1  # round-robin: каждый запрос — следующий ключ
            try:
                r = self.client.post(
                    TTS_URL,
                    params={"format": "wav16", "voice": VOICE},
                    headers={
                        "Authorization": f"Bearer {self._token(i)}",
                        "Content-Type": "application/text",
                        "X-Request-ID": str(uuid.uuid4()),
                    },
                    content=text.encode("utf-8"),
                )
                if r.status_code in (401, 429):
                    self.tokens.pop(i, None)  # токен протух или лимит — пробуем следующий ключ
                    last_err = RuntimeError(f"ключ #{i + 1}: HTTP {r.status_code}")
                    continue
                r.raise_for_status()
                return r.content
            except Exception as e:
                last_err = e
        raise RuntimeError(f"Все ключи не сработали: {last_err}")


YANDEX_URL = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
YANDEX_VOICE = "marina"
YANDEX_EMOTION = "friendly"   # у marina: neutral / whisper / friendly
YANDEX_RATE = 48000   # 16 кГц срезает всё выше 8 кГц — голос звучит глухо, не как в демо


def _yandex_key() -> str:
    key = os.getenv("YANDEX_API_KEY")
    if key:
        return key
    env = Path(__file__).resolve().parent.parent / "yandex.env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("YANDEX_API_KEY="):
                return line.split("=", 1)[1].strip()
    sys.exit("Нужен YANDEX_API_KEY (env или yandex.env в корне проекта)")


def yandex_wav(text: str, key: str) -> bytes:
    """LPCM от Яндекса + обрезка тишины по краям + WAV-заголовок."""
    import io
    import struct
    import wave

    r = httpx.post(YANDEX_URL, headers={"Authorization": f"Api-Key {key}"}, timeout=90,
                   data={"text": text, "lang": "ru-RU", "voice": YANDEX_VOICE,
                         "emotion": YANDEX_EMOTION, "speed": "1.0",
                         "format": "lpcm", "sampleRateHertz": str(YANDEX_RATE)})
    r.raise_for_status()
    s = list(struct.unpack("<%dh" % (len(r.content) // 2), r.content))
    thr = max(abs(x) for x in s) * 0.02
    a = next(i for i, x in enumerate(s) if abs(x) > thr)
    b = len(s) - next(i for i, x in enumerate(reversed(s)) if abs(x) > thr)
    pad = int(YANDEX_RATE * 0.05)
    s = s[max(0, a - pad):min(len(s), b + pad)]
    buf = io.BytesIO()
    w = wave.open(buf, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(YANDEX_RATE)
    w.writeframes(struct.pack("<%dh" % len(s), *s))
    w.close()
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="static/voice/ru")
    ap.add_argument("--engine", choices=("yandex", "sber"), default="yandex")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    if args.engine == "sber":
        raw = os.getenv("SALUTE_AUTH_KEYS") or os.getenv("SALUTE_AUTH_KEY") or ""
        keys = [k.strip() for k in raw.split(",") if k.strip()]
        if not keys:
            sys.exit("Нужен env SALUTE_AUTH_KEYS (Freemium закрыт с 15.07.2026 — вероятно, вернёт 402)")
        print(f"Сбер, ключей: {len(keys)}, голос: {VOICE}")
        tts = SaluteTTS(keys)
        synth = tts.synth
    else:
        key = _yandex_key()
        print(f"Яндекс SpeechKit, голос: {YANDEX_VOICE}, амплуа: {YANDEX_EMOTION}")
        synth = lambda text: yandex_wav(text, key)  # noqa: E731

    made = skipped = 0
    for name, text in INSTRUCTIONS.items():
        target = out / f"{name}.wav"
        if target.exists():
            skipped += 1  # уже озвученное (в т.ч. старое сберовское) не переписываем
            continue
        target.write_bytes(synth(text))
        made += 1
        print(f"ok   {name}: «{text}»")
        time.sleep(0.3)
    print(f"Готово: {out} — новых {made}, пропущено {skipped}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
