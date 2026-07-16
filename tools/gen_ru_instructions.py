# -*- coding: utf-8 -*-
"""Озвучка русских инструкций через Сбер SaluteSpeech (SmartSpeech).

Ключи: env SALUTE_AUTH_KEYS — один или несколько авторизационных ключей через запятую
(ключи ротируются по кругу, при 429/401 — переключение на следующий).

Использование:
  SALUTE_AUTH_KEYS=key1,key2,key3 python tools/gen_ru_instructions.py --out static/voice/ru

Файлы кладутся в <out>/<key>.wav — имена согласованы с INSTR_AUDIO в exercises.js.
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="static/voice/ru")
    args = ap.parse_args()

    raw = os.getenv("SALUTE_AUTH_KEYS") or os.getenv("SALUTE_AUTH_KEY") or ""
    keys = [k.strip() for k in raw.split(",") if k.strip()]
    if not keys:
        sys.exit("Нужен env SALUTE_AUTH_KEYS (один или несколько ключей через запятую)")
    print(f"Ключей: {len(keys)}, голос: {VOICE}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    tts = SaluteTTS(keys)
    for name, text in INSTRUCTIONS.items():
        target = out / f"{name}.wav"
        if target.exists():
            print(f"skip {name} (есть)")
            continue
        target.write_bytes(tts.synth(text))
        print(f"ok   {name}: «{text}»")
        time.sleep(0.3)
    print("Готово:", out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
