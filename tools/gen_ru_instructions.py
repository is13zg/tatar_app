# -*- coding: utf-8 -*-
"""Озвучка русских инструкций через Сбер SaluteSpeech (SmartSpeech).

Нужен авторизационный ключ (Authorization key из личного кабинета developers.sber.ru,
проект SaluteSpeech): env SALUTE_AUTH_KEY (base64-строка для Basic).

Использование:
  SALUTE_AUTH_KEY=... python tools/gen_ru_instructions.py            # локально в static/voice/ru/
  SALUTE_AUTH_KEY=... python tools/gen_ru_instructions.py --out /root/tatar_files/static/voice/ru

Файлы кладутся в <out>/<key>.mp3 — имена согласованы с INSTR_AUDIO в exercises.js.
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
    "povtori_za_diktorom": "Повтори за диктором",
    "molodec": "Молодец!",
    "molodec_otlichno": "Молодец! Отлично!",
}


def get_token(auth_key: str) -> str:
    r = httpx.post(
        OAUTH_URL,
        headers={
            "Authorization": f"Basic {auth_key}",
            "RqUID": str(uuid.uuid4()),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"scope": "SALUTE_SPEECH_PERS"},
        verify=False,  # цепочка НУЦ Минцифры может отсутствовать в системе
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def synth(token: str, text: str) -> bytes:
    r = httpx.post(
        TTS_URL,
        params={"format": "mp3", "voice": VOICE},
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/text"},
        content=text.encode("utf-8"),
        verify=False,
        timeout=60,
    )
    r.raise_for_status()
    return r.content


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="static/voice/ru")
    args = ap.parse_args()

    key = os.getenv("SALUTE_AUTH_KEY")
    if not key:
        sys.exit("Нужен env SALUTE_AUTH_KEY (Authorization key из кабинета SaluteSpeech)")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    token = get_token(key)
    for name, text in INSTRUCTIONS.items():
        target = out / f"{name}.mp3"
        if target.exists():
            print(f"skip {name} (есть)")
            continue
        target.write_bytes(synth(token, text))
        print(f"ok   {name}: «{text}»")
        time.sleep(0.4)
    print("Готово:", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
