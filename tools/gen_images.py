# -*- coding: utf-8 -*-
"""Генерация детских иллюстраций для слов без картинок.

Провайдеры:
  pollinations — БЕСПЛАТНО и БЕЗ КЛЮЧА (flux), image.pollinations.ai. Дефолт.
  fusionbrain  — Kandinsky от Сбера, БЕСПЛАТНЫЙ ключ: https://fusionbrain.ai/docs/
                 env: FB_KEY, FB_SECRET
  openai       — gpt-image-1, платный. env: OPENAI_API_KEY

Скрипт берёт слова без картинок через API приложения и загружает готовые
изображения обратно через /admin/word_image/{id} — работает и с локальным,
и с боевым сервером.

Примеры:
  python tools/gen_images.py --app http://127.0.0.1:8001 --password admin217 --dry-run
  FB_KEY=... FB_SECRET=... python tools/gen_images.py --app http://127.0.0.1:8001 --password ... --limit 20
"""
import argparse
import base64
import io
import json
import os
import sys
import time

import httpx

# Flux плохо понимает русский («свинья» рисовал собакой, «лев» — тигром),
# поэтому промпт строится на английском по словарю EN_GLOSS.
PROMPT_EN = (
    "cute children's book flat illustration: {en}. "
    "single subject centered, plain light background, bright saturated colors, "
    "friendly cartoon style, no text, no letters"
)
PROMPT_RU_FALLBACK = (
    "Яркая плоская иллюстрация для детской обучающей игры: {ru}. "
    "Один крупный объект по центру, простой светлый фон, добрый стиль детской книги, "
    "насыщенные цвета, без текста и букв."
)

EN_GLOSS = {
    # животные
    "свинья": "a pink pig", "волк": "a grey wolf", "белка": "a red squirrel with fluffy tail",
    "лев": "a lion with big mane", "тигр": "a striped tiger", "слон": "an elephant",
    "обезьяна": "a monkey", "воробей": "a small sparrow bird", "ворона": "a black crow",
    "голубь": "a grey pigeon", "попугай": "a colorful parrot", "петух": "a rooster",
    "лягушка": "a green frog", "бабочка": "a butterfly", "муха": "a housefly",
    "комар": "a mosquito", "муравей": "an ant", "пчела": "a bee",
    "хвост": "a fluffy fox tail, close-up", "лапа": "an animal paw print and a puppy paw",
    "лес": "a forest with trees", "зоопарк": "a zoo entrance with animals", "нора": "an animal burrow hole in the ground",
    # цвета и формы
    "белый": "a big white circle of paint", "черный": "a big black circle of paint",
    "красный": "a big red circle of paint", "синий": "a big blue circle of paint",
    "зеленый": "a big green circle of paint", "желтый": "a big yellow circle of paint",
    "коричневый": "a big brown circle of paint", "розовый": "a big pink circle of paint",
    "оранжевый": "a big orange circle of paint", "фиолетовый": "a big purple circle of paint",
    "серый": "a big grey circle of paint", "голубой": "a big light blue circle of paint",
    "круг": "a circle shape", "квадрат": "a square shape", "линия": "a straight line drawn with pencil",
    "большой": "a big elephant next to a tiny mouse", "маленький": "a tiny mouse next to a big elephant",
    "длинный": "a long train", "короткий": "a short pencil stub",
    # семья и дом
    "семья": "a happy family: mom, dad and a child together", "мама": "a mom hugging her child",
    "папа": "a dad holding his child's hand", "бабушка": "a kind elderly grandmother with grey hair and headscarf",
    "дедушка": "a kind elderly grandfather with grey beard", "дядя": "a friendly adult man waving",
    "тетя": "a friendly adult woman waving", "родители": "mom and dad together",
    "дом": "a cozy house", "квартира": "an apartment building", "комната": "a children's room interior",
    "кухня": "a kitchen interior", "ванная": "a bathroom with a bathtub", "прихожая": "a hallway with coat rack",
    "стена": "a brick wall", "пол": "a wooden floor in a room", "потолок": "a room ceiling with a lamp, view up",
    "крыша": "a red house roof", "кровать": "a bed", "шкаф": "a wardrobe", "диван": "a sofa",
    "кресло": "an armchair", "телевизор": "a television", "ковер": "an ornamental carpet",
    "зеркало": "a mirror", "часы": "a round wall clock", "лампа": "a table lamp",
    "посуда": "dishes: plates and cups", "тарелка": "a plate", "чашка": "a tea cup",
    "ложка": "a spoon", "вилка": "a fork", "нож": "a kitchen knife", "чайник": "a teapot",
    "кастрюля": "a cooking pot", "игрушка": "a teddy bear toy", "ключ": "a golden key",
    "телефон": "a smartphone", "подушка": "a pillow",
    # еда
    "сыр": "a piece of cheese with holes", "колбаса": "a sausage", "котлета": "a meat patty on a plate",
    "макароны": "a plate of pasta", "рис": "a bowl of rice", "сок": "a glass of orange juice",
    "компот": "a glass of fruit compote drink with berries", "пирог": "a homemade pie",
    "блины": "a stack of pancakes", "варенье": "a jar of berry jam", "конфета": "a wrapped candy",
    "шоколад": "a chocolate bar", "мороженое": "an ice cream cone", "торт": "a birthday cake",
    "печенье": "cookies", "фрукты": "a bowl of fruits", "вкусный": "a happy child enjoying tasty food",
    "невкусный": "a child making yuck face at food", "сладкий": "sweet candies and honey",
    "кислый": "a sour lemon and a puckered face", "горячий": "a hot steaming soup bowl",
    "холодный": "a cold ice cube", "пить": "a child drinking water from a glass",
    "кыстыбый": "kystyby, Tatar soft flatbread folded over mashed potato filling",
    "эчпочмак (пирожок)": "echpochmak, Tatar triangular baked pastry",
    # человек и тело
    "человек": "a friendly person standing, full height", "голова": "a child's head, portrait",
    "волосы": "hair on a child's head", "глаз": "a big friendly eye", "глаза": "two friendly eyes",
    "нос": "a nose on a friendly face", "рот": "a smiling open mouth", "зуб": "a white tooth",
    "язык": "a child playfully showing tongue", "ухо": "an ear", "уши": "ears on a child's head",
    "шея": "a giraffe with a long neck highlighted", "плечо": "a child's shoulder with hand on it",
    "рука": "a child's hand waving", "палец": "a pointing finger", "спина": "a child seen from behind, back",
    "живот": "a happy child holding tummy", "сердце": "a red heart", "кровь": "a red blood drop and a bandage",
    "одежда": "clothes on hangers", "обувь": "pairs of shoes", "слезы": "a crying face with tears",
    "улыбка": "a big happy smile on a face", "нога": "a child's leg and foot",
    # одежда
    "рубашка": "a buttoned shirt", "брюки": "trousers", "юбка": "a skirt", "кофта": "a knitted cardigan",
    "свитер": "a warm sweater", "футболка": "a t-shirt", "шорты": "shorts", "куртка": "a jacket",
    "пальто": "a winter coat", "шапка": "a warm knitted hat", "шарф": "a scarf", "варежки": "mittens",
    "носки": "a pair of socks", "колготки": "children's tights", "туфли": "a pair of shoes",
    "ботинки": "a pair of boots", "сапоги": "tall winter boots", "кроссовки": "sneakers",
    "тапочки": "cozy slippers", "ремень": "a leather belt", "карман": "a pocket on jeans",
    "пуговица": "a big button", "молния": "a zipper on a jacket", "платок": "a headscarf",
    "костюм": "a child's suit", "пижама": "pajamas", "зонт": "an umbrella",
    "тюбетейка": "tubeteika, Tatar embroidered skullcap", "калфак": "kalfak, Tatar women's embroidered headdress",
    # действия (ребёнок делает)
    "стоять": "a child standing", "садиться": "a child sitting down on a chair",
    "лежать": "a child lying on a bed", "считать": "a child counting on fingers",
    "рисовать": "a child drawing with crayons", "слушать": "a child listening, hand to ear",
    "смотреть": "a child looking through binoculars", "говорить": "a child talking, speech bubble",
    "играть": "a child playing with toys", "петь": "a child singing", "танцевать": "a child dancing",
    "спать": "a child sleeping in bed", "просыпаться": "a child waking up and stretching in bed",
    "любить": "a child hugging a big red heart", "помогать": "a child helping to carry a box",
    "спрашивать": "a child raising hand to ask", "отвечать": "a child answering at the blackboard",
    "открывать": "a child opening a door", "закрывать": "a child closing a door",
    "искать": "a child searching with a magnifying glass", "найти": "a happy child who found a treasure",
    "сделать": "a child proudly finished a block tower", "жить": "a family in front of their house",
    "плакать": "a crying child", "мыть": "a child washing hands with soap",
    "одеваться": "a child getting dressed", "гулять": "a child walking in the park",
    "прыгать": "a child jumping", "лететь": "an airplane flying in the sky",
    "покупать": "a child with a shopping basket in a store", "приходить": "a child arriving and waving at the door",
    "уходить": "a child leaving and waving goodbye", "сказать": "a child saying something, speech bubble",
    "показывать": "a child pointing at something", "повторять": "a child repeating after the teacher",
    "болеть": "a sick child in bed with a thermometer", "сидеть тихо": "a child sitting quietly, finger on lips",
    "встать": "a child standing up from a chair", "вырезать": "a child cutting paper with scissors",
    "клеить": "a child gluing colored paper", "раскрашивать": "a child coloring a picture",
    "чистить": "a child brushing teeth",
    # время и сезоны
    "день": "a bright sunny day landscape", "утро": "a sunrise morning with rooster",
    "ночь": "a night sky with moon and stars", "осень": "autumn trees with falling yellow leaves",
    "зима": "winter landscape with a snowman", "весна": "spring flowers and green leaves",
    "лето": "sunny summer meadow", "праздник": "a celebration with balloons and flags",
    "день рождения": "a birthday cake with candles and balloons", "новый год": "a decorated new year tree with presents",
    "каникулы": "happy children on school holidays outdoors",
    "сабантуй": "Sabantuy, Tatar summer festival with belt wrestling and a tall pole",
    # школа
    "школа": "a school building", "класс": "a classroom interior", "урок": "a lesson in a classroom",
    "учитель": "a friendly teacher at the blackboard", "ученик": "a schoolkid with a backpack",
    "перемена": "children playing in a school corridor", "парта": "a school desk", "стул": "a chair",
    "стол": "a table", "доска": "a green school chalkboard", "мел": "white chalk pieces",
    "тетрадь": "a school notebook", "книга": "an open book", "учебник": "a textbook",
    "дневник": "a school record book", "портфель": "a school backpack", "пенал": "a pencil case",
    "ручка": "a pen", "карандаш": "a pencil", "цветные карандаши": "colored pencils",
    "линейка": "a ruler", "ластик": "an eraser", "точилка": "a pencil sharpener",
    "краски": "watercolor paints with brush", "кисточка": "a paintbrush", "альбом": "a sketchbook",
    "клей": "a glue stick", "ножницы": "scissors", "бумага": "a sheet of paper",
    "пластилин": "colorful modeling clay", "пятерка": "a big number five with a golden star",
    "четверка": "a big number four", "тройка": "a big number three", "задание": "a homework worksheet",
    "звонок": "a ringing school bell", "окно": "a window", "дверь": "a door",
    "кабинет": "a school classroom with a door sign", "библиотека": "a library with bookshelves",
    "спортивный зал": "a school gym with balls", "столовая": "a school canteen", "компьютер": "a computer",
}

# Не генерируем: фразы и абстракции — картинка для них бессмысленна/вводит в заблуждение
SKIP_THEMES = {"Знакомство и общение"}
SKIP_RU = {
    "время", "минута", "ум", "здоровье", "сила", "рост", "имя", "фамилия", "голос",
    "смех", "родина", "место", "дикий", "светлый", "темный", "тёмный", "разноцветный",
    "понимать", "знать", "думать", "помнить", "забыть", "животное", "насекомое",
    "цвет", "форма", "сегодня", "вчера", "завтра", "год", "месяц", "неделя",
    "время года", "выходной", "оценка", "ответ", "вопрос", "приятного аппетита!",
}


def login(app: str, user: str, password: str) -> dict:
    r = httpx.post(f"{app}/auth/login", data={"username": user, "password": password}, timeout=30)
    r.raise_for_status()
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def words_without_images(app: str, headers: dict, theme_filter: int | None, redo_uploads: bool = False) -> list[dict]:
    themes = httpx.get(f"{app}/themes", headers=headers, timeout=30).json()
    result = []
    for t in themes:
        if theme_filter and t["id"] != theme_filter:
            continue
        if t["title_ru"] in SKIP_THEMES:
            continue
        words = httpx.get(f"{app}/themes/{t['id']}/words", headers=headers, timeout=30).json()
        for w in words:
            if w["text_ru"].lower() in SKIP_RU:
                continue
            img = w.get("image_url") or ""
            needs = (not img) or ("noimg" in img) or (redo_uploads and "/uploads/" in img)
            if needs:
                w["theme_title"] = t["title_ru"]
                result.append(w)
    return result


# ---------- Pollinations (flux, без ключа) ----------

class Pollinations:
    def __init__(self) -> None:
        self.client = httpx.Client(timeout=120, follow_redirects=True)

    def generate(self, prompt: str) -> bytes:
        from urllib.parse import quote
        url = f"https://image.pollinations.ai/prompt/{quote(prompt)}"
        last_err = None
        for attempt in range(5):
            try:
                r = self.client.get(url, params={"width": 512, "height": 512, "nologo": "true", "seed": attempt * 7 + 1})
                if r.status_code == 429:
                    # анонимный тариф: один одновременный запрос на IP — терпеливо ждём
                    wait = 30 * (attempt + 1)
                    print(f"    429, жду {wait}с…")
                    time.sleep(wait)
                    last_err = RuntimeError("429 Too Many Requests")
                    continue
                r.raise_for_status()
                if not r.headers.get("content-type", "").startswith("image/"):
                    raise RuntimeError(f"не картинка: {r.headers.get('content-type')}")
                return r.content
            except Exception as e:
                last_err = e
                time.sleep(10 * (attempt + 1))
        raise RuntimeError(f"Pollinations не ответил: {last_err}")


# ---------- FusionBrain (Kandinsky) ----------

FB_URL = "https://api-key.fusionbrain.ai"


class FusionBrain:
    def __init__(self) -> None:
        key, secret = os.getenv("FB_KEY"), os.getenv("FB_SECRET")
        if not key or not secret:
            sys.exit("Нужны env-переменные FB_KEY и FB_SECRET (бесплатно: https://fusionbrain.ai/docs/)")
        self.headers = {"X-Key": f"Key {key}", "X-Secret": f"Secret {secret}"}
        pipelines = httpx.get(f"{FB_URL}/key/api/v1/pipelines", headers=self.headers, timeout=30).json()
        self.pipeline_id = pipelines[0]["id"]

    def generate(self, prompt: str) -> bytes:
        params = {
            "type": "GENERATE",
            "numImages": 1,
            "width": 512,
            "height": 512,
            "generateParams": {"query": prompt},
        }
        files = {
            "pipeline_id": (None, self.pipeline_id),
            "params": (None, json.dumps(params), "application/json"),
        }
        r = httpx.post(f"{FB_URL}/key/api/v1/pipeline/run", headers=self.headers, files=files, timeout=60)
        r.raise_for_status()
        uuid = r.json()["uuid"]
        for _ in range(60):
            time.sleep(3)
            st = httpx.get(f"{FB_URL}/key/api/v1/pipeline/status/{uuid}", headers=self.headers, timeout=30).json()
            if st.get("status") == "DONE":
                return base64.b64decode(st["result"]["files"][0])
            if st.get("status") == "FAIL":
                raise RuntimeError(f"FusionBrain FAIL: {st}")
        raise TimeoutError("FusionBrain: генерация не завершилась за 3 минуты")


# ---------- OpenAI ----------

class OpenAIImages:
    def __init__(self) -> None:
        self.key = os.getenv("OPENAI_API_KEY")
        if not self.key:
            sys.exit("Нужна env-переменная OPENAI_API_KEY")

    def generate(self, prompt: str) -> bytes:
        r = httpx.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {self.key}"},
            json={"model": "gpt-image-1", "prompt": prompt, "size": "1024x1024", "quality": "low"},
            timeout=120,
        )
        r.raise_for_status()
        return base64.b64decode(r.json()["data"][0]["b64_json"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="http://127.0.0.1:8001")
    ap.add_argument("--user", default="admin")
    ap.add_argument("--password", required=True)
    ap.add_argument("--provider", choices=["pollinations", "fusionbrain", "openai"], default="pollinations")
    ap.add_argument("--theme", type=int, help="только одна тема (id)")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--delay", type=float, default=1.0, help="пауза между генерациями, сек")
    ap.add_argument("--dry-run", action="store_true", help="только показать, что будет сгенерировано")
    ap.add_argument("--redo-uploads", action="store_true", help="перегенерировать и ранее сгенерированные (uploads)")
    args = ap.parse_args()

    headers = login(args.app, args.user, args.password)
    todo = words_without_images(args.app, headers, args.theme, redo_uploads=args.redo_uploads)[: args.limit]
    print(f"Слов без картинок: {len(todo)}")
    if args.dry_run:
        for w in todo[:30]:
            print(f"  [{w['theme_title']}] {w['text_ru']} — {w['text_tt']}")
        return

    providers = {"pollinations": Pollinations, "fusionbrain": FusionBrain, "openai": OpenAIImages}
    provider = providers[args.provider]()
    ok, fail = 0, 0
    for i, w in enumerate(todo, 1):
        en = EN_GLOSS.get(w["text_ru"].lower())
        if en:
            prompt = PROMPT_EN.format(en=en)
        else:
            print(f"  (нет EN-глоссы: {w['text_ru']} — русский промпт)")
            prompt = PROMPT_RU_FALLBACK.format(ru=w["text_ru"])
        try:
            png = provider.generate(prompt)
            files = {"file": (f"word_{w['id']}.png", io.BytesIO(png), "image/png")}
            r = httpx.post(f"{args.app}/admin/word_image/{w['id']}", headers=headers, files=files, timeout=60)
            r.raise_for_status()
            ok += 1
            print(f"[{i}/{len(todo)}] ✅ {w['text_ru']} — {w['text_tt']}")
            fail = 0  # успех сбрасывает счётчик подряд идущих ошибок
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(todo)}] ❌ {w['text_ru']}: {e}")
            if fail >= 8:
                print("Слишком много ошибок подряд — останавливаюсь.")
                break
        time.sleep(args.delay)
    print(f"Готово: {ok} ок, {fail} ошибок")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
