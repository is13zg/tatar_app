import json
import math
import random
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user
from ..database import get_db
from ..models import (
    User, Theme, Word, UserProgress, UserMistake,
    UnitProgress, DailyLesson, UserSticker,
)

router = APIRouter(prefix="/lesson", tags=["lessons"])

NEW_WORDS_PER_LESSON = 4
SRS_INTERVALS_DAYS = [0, 1, 2, 4, 7, 14]  # индекс = strength
MAX_STRENGTH = len(SRS_INTERVALS_DAYS) - 1
KAZAN_UTC_OFFSET = timedelta(hours=3)
STREAK_STICKERS = {3: "🔥", 7: "⭐", 14: "🏆", 30: "👑"}


def now_utc() -> datetime:
    return datetime.utcnow()


def today_str() -> str:
    return (now_utc() + KAZAN_UTC_OFFSET).date().isoformat()


def word_dto(w: Word) -> dict:
    return {
        "id": w.id,
        "text_tt": w.text_tt,
        "text_ru": w.text_ru,
        "image_url": w.image_url,
        "emoji": w.emoji,
        "audio_url": w.audio_url or w.tts_url,
    }


def lessons_total_for(word_count: int) -> int:
    return max(1, math.ceil(word_count / NEW_WORDS_PER_LESSON)) + 1  # + босс


async def get_ordered_units(db: AsyncSession) -> list[Theme]:
    return (await db.execute(select(Theme).order_by(Theme.order_index, Theme.id))).scalars().all()


async def unit_words(db: AsyncSession, theme_id: int) -> list[Word]:
    return (await db.execute(select(Word).where(Word.theme_id == theme_id).order_by(Word.id))).scalars().all()


# ---------- генераторы упражнений ----------

def ex_card(w: dict) -> dict:
    return {"type": "card", "word": w}


def ex_pick_image(target: dict, pool: list[dict]) -> Optional[dict]:
    distractors = [p for p in pool if p["id"] != target["id"]]
    if len(distractors) < 3:
        return None
    options = random.sample(distractors, 3) + [target]
    random.shuffle(options)
    return {
        "type": "pick_image",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "options": [{"id": o["id"], "image_url": o["image_url"], "emoji": o["emoji"]} for o in options],
    }


def ex_yes_no(target: dict, pool: list[dict]) -> Optional[dict]:
    is_match = random.random() < 0.5
    shown = target
    if not is_match:
        others = [p for p in pool if p["id"] != target["id"]]
        if not others:
            return None
        shown = random.choice(others)
    return {
        "type": "yes_no",
        "word_id": target["id"],
        "text_tt": target["text_tt"],
        "audio_url": target["audio_url"],
        "shown": {"id": shown["id"], "image_url": shown["image_url"], "emoji": shown["emoji"]},
        "is_match": is_match,
    }


def ex_memory(words: list[dict]) -> Optional[dict]:
    if len(words) < 3:
        return None
    pairs = random.sample(words, 3)
    return {"type": "memory", "pairs": [
        {"word_id": p["id"], "text_tt": p["text_tt"], "audio_url": p["audio_url"],
         "image_url": p["image_url"], "emoji": p["emoji"]} for p in pairs
    ]}


def ex_pick_word_audio(target: dict, pool: list[dict]) -> Optional[dict]:
    distractors = [p for p in pool if p["id"] != target["id"] and p["audio_url"]]
    if not target["audio_url"] or len(distractors) < 2:
        return None
    options = random.sample(distractors, 2) + [target]
    random.shuffle(options)
    return {
        "type": "pick_word_audio",
        "word_id": target["id"],
        "shown": {"image_url": target["image_url"], "emoji": target["emoji"], "text_ru": target["text_ru"]},
        "options": [{"id": o["id"], "audio_url": o["audio_url"], "text_tt": o["text_tt"]} for o in options],
    }


def ex_build_word(target: dict) -> Optional[dict]:
    word = target["text_tt"].strip().lower()
    if not (3 <= len(word) <= 6) or " " in word or "-" in word or "?" in word:
        return None
    letters = list(word)
    random.shuffle(letters)
    return {
        "type": "build_word",
        "word_id": target["id"],
        "text_tt": word,
        "audio_url": target["audio_url"],
        "image_url": target["image_url"],
        "emoji": target["emoji"],
        "letters": letters,
    }


def ex_repeat_after(target: dict) -> dict:
    return {"type": "repeat_after", "word": target}


def ex_sort_baskets(theme_a: Theme, words_a: list[dict], theme_b: Theme, words_b: list[dict]) -> Optional[dict]:
    if len(words_a) < 2 or len(words_b) < 2:
        return None
    pick_a = random.sample(words_a, 2)
    pick_b = random.sample(words_b, 2)
    items = [
        {"word_id": w["id"], "text_tt": w["text_tt"], "audio_url": w["audio_url"],
         "image_url": w["image_url"], "emoji": w["emoji"], "basket": t.id}
        for t, ws in ((theme_a, pick_a), (theme_b, pick_b)) for w in ws
    ]
    random.shuffle(items)
    return {
        "type": "sort_baskets",
        "baskets": [
            {"id": theme_a.id, "title_ru": theme_a.title_ru, "icon_emoji": theme_a.icon_emoji or "📦"},
            {"id": theme_b.id, "title_ru": theme_b.title_ru, "icon_emoji": theme_b.icon_emoji or "📦"},
        ],
        "items": items,
    }


def build_exercises(new_words: list[dict], pool: list[dict], review_words: list[dict],
                    sort_payload: Optional[dict] = None) -> list[dict]:
    """Стандартный набор упражнений урока: подача + разнообразная практика."""
    items: list[dict] = [ex_card(w) for w in new_words]

    practice: list[dict] = []
    for w in new_words:
        e = ex_pick_image(w, pool)
        if e:
            practice.append(e)
    for w in random.sample(new_words, min(2, len(new_words))):
        e = ex_yes_no(w, pool)
        if e:
            practice.append(e)
    e = ex_memory(new_words if len(new_words) >= 3 else pool)
    if e:
        practice.append(e)
    for w in random.sample(new_words, min(2, len(new_words))):
        e = ex_pick_word_audio(w, pool)
        if e:
            practice.append(e)
    built = 0
    for w in new_words:
        if built >= 1:
            break
        e = ex_build_word(w)
        if e:
            practice.append(e)
            built += 1
    if new_words:
        practice.append(ex_repeat_after(random.choice(new_words)))
    if sort_payload:
        practice.append(sort_payload)

    # повторение прошлых слов вперемешку
    for w in review_words:
        e = ex_pick_image(w, pool + review_words) or ex_yes_no(w, pool + review_words)
        if e:
            e["review"] = True
            practice.append(e)

    random.shuffle(practice)
    return items + practice


# ---------- вспомогательные выборки ----------

async def due_review_words(db: AsyncSession, user: User, limit: int, exclude_theme: Optional[int] = None) -> list[dict]:
    q = (
        select(Word)
        .join(UserProgress, UserProgress.word_id == Word.id)
        .where(
            UserProgress.user_id == user.id,
            UserProgress.strength > 0,
            UserProgress.due_at.is_not(None),
            UserProgress.due_at <= now_utc(),
        )
        .order_by(UserProgress.due_at)
        .limit(limit * 2)
    )
    words = (await db.execute(q)).scalars().all()
    result = [word_dto(w) for w in words if exclude_theme is None or w.theme_id != exclude_theme]
    return result[:limit]


async def unit_progress_map(db: AsyncSession, user: User) -> dict[int, UnitProgress]:
    rows = (await db.execute(select(UnitProgress).where(UnitProgress.user_id == user.id))).scalars().all()
    return {r.theme_id: r for r in rows}


async def compute_streak(db: AsyncSession, user: User) -> int:
    rows = (await db.execute(
        select(DailyLesson.date).where(DailyLesson.user_id == user.id, DailyLesson.completed_at.is_not(None))
    )).all()
    done = {r[0] for r in rows}
    today = (now_utc() + KAZAN_UTC_OFFSET).date()
    streak = 0
    day = today
    if today.isoformat() not in done:
        day = today - timedelta(days=1)  # серия ещё жива, если вчера выполнено
    while day.isoformat() in done:
        streak += 1
        day -= timedelta(days=1)
    return streak


# ---------- endpoints ----------

@router.get("/path")
async def learning_path(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    result = []
    prev_done = True  # первый юнит открыт всегда
    for t in units:
        words = await unit_words(db, t.id)
        total = lessons_total_for(len(words))
        p = progress.get(t.id)
        stars = p.stars if p else 0
        lessons_done = p.lessons_done if p else 0
        completed = bool(p and p.completed_at)
        if completed:
            state = "done"
        elif prev_done:
            state = "current"
        else:
            state = "locked"
        result.append({
            "theme_id": t.id,
            "title_ru": t.title_ru,
            "title_tt": t.title_tt,
            "icon_emoji": t.icon_emoji or "📚",
            "word_count": len(words),
            "lessons_total": total,
            "lessons_done": min(lessons_done, total),
            "stars": stars,
            "state": state,
        })
        prev_done = completed
    streak = await compute_streak(db, user)
    stickers = (await db.execute(select(UserSticker).where(UserSticker.user_id == user.id))).scalars().all()
    return {"units": result, "streak": streak, "stickers": [s.sticker for s in stickers]}


@router.get("/unit/{theme_id}/{lesson_no}")
async def unit_lesson(theme_id: int, lesson_no: int,
                      db: Annotated[AsyncSession, Depends(get_db)],
                      user: Annotated[User, Depends(get_current_user)]):
    theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    words = await unit_words(db, theme_id)
    if not words:
        raise HTTPException(status_code=400, detail="В теме нет слов")
    total = lessons_total_for(len(words))
    lesson_no = max(1, min(lesson_no, total))
    pool = [word_dto(w) for w in words]
    is_boss = lesson_no == total

    if is_boss:
        sample = random.sample(pool, min(9, len(pool)))
        items: list[dict] = []
        for i, w in enumerate(sample):
            e = None
            kind = i % 4
            if kind == 0:
                e = ex_pick_image(w, pool)
            elif kind == 1:
                e = ex_yes_no(w, pool)
            elif kind == 2:
                e = ex_pick_word_audio(w, pool)
            else:
                e = ex_build_word(w) or ex_pick_image(w, pool)
            if e:
                items.append(e)
        m = ex_memory(pool)
        if m:
            items.append(m)
        random.shuffle(items)
    else:
        start = (lesson_no - 1) * NEW_WORDS_PER_LESSON
        new_words = pool[start:start + NEW_WORDS_PER_LESSON]
        if not new_words:
            new_words = pool[-NEW_WORDS_PER_LESSON:]
        review = await due_review_words(db, user, 3, exclude_theme=theme_id)

        sort_payload = None
        units = await get_ordered_units(db)
        prev_units = [u for u in units if u.order_index < theme.order_index]
        if prev_units and random.random() < 0.5:
            other = random.choice(prev_units)
            other_words = [word_dto(w) for w in await unit_words(db, other.id)]
            sort_payload = ex_sort_baskets(theme, pool, other, other_words)

        items = build_exercises(new_words, pool, review, sort_payload)

    return {
        "theme": {"id": theme.id, "title_ru": theme.title_ru, "icon_emoji": theme.icon_emoji},
        "lesson_no": lesson_no,
        "lessons_total": total,
        "is_boss": is_boss,
        "items": items,
    }


@router.get("/daily")
async def daily_lesson(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    date = today_str()
    existing = (await db.execute(
        select(DailyLesson).where(DailyLesson.user_id == user.id, DailyLesson.date == date)
    )).scalar_one_or_none()
    if existing and existing.completed_at:
        return {"completed": True, "stars": existing.stars, "date": date,
                "streak": await compute_streak(db, user)}
    if existing and existing.items_json:
        return {"completed": False, "date": date, "items": json.loads(existing.items_json)}

    # новое задание дня: повторение (до 8 слов) + немного нового из текущего юнита
    review = await due_review_words(db, user, 8)

    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    current_unit: Optional[Theme] = None
    prev_done = True
    for t in units:
        p = progress.get(t.id)
        completed = bool(p and p.completed_at)
        if prev_done and not completed:
            current_unit = t
            break
        prev_done = completed
    if current_unit is None:
        current_unit = units[0] if units else None
    if current_unit is None:
        raise HTTPException(status_code=400, detail="Нет тем")

    pool = [word_dto(w) for w in await unit_words(db, current_unit.id)]
    seen_ids = {
        r[0] for r in (await db.execute(
            select(UserProgress.word_id).where(UserProgress.user_id == user.id)
        )).all()
    }
    fresh = [w for w in pool if w["id"] not in seen_ids][:3]

    items = build_exercises(fresh, pool, review)
    if not items:
        raise HTTPException(status_code=400, detail="Не удалось собрать задание")

    if existing:
        existing.items_json = json.dumps(items, ensure_ascii=False)
    else:
        db.add(DailyLesson(user_id=user.id, date=date, items_json=json.dumps(items, ensure_ascii=False)))
    await db.commit()
    return {"completed": False, "date": date, "items": items}


class LessonAnswer(BaseModel):
    word_id: int
    is_correct: bool
    exercise_type: Optional[str] = None


@router.post("/answer")
async def lesson_answer(answer: LessonAnswer,
                        db: Annotated[AsyncSession, Depends(get_db)],
                        user: Annotated[User, Depends(get_current_user)]):
    progress = (await db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id, UserProgress.word_id == answer.word_id)
    )).scalar_one_or_none()
    if not progress:
        progress = UserProgress(user_id=user.id, word_id=answer.word_id, learned=False, strength=0)
        db.add(progress)
    progress.seen_count = (progress.seen_count or 0) + 1
    progress.last_seen_at = now_utc()
    if answer.is_correct:
        progress.correct_count = (progress.correct_count or 0) + 1
        progress.strength = min(MAX_STRENGTH, (progress.strength or 0) + 1)
        progress.learned = True
    else:
        progress.strength = 1 if (progress.strength or 0) > 1 else (progress.strength or 0)
    progress.due_at = now_utc() + timedelta(days=SRS_INTERVALS_DAYS[progress.strength or 0])

    # зеркалим старый счётчик ошибок, чтобы страница «работа над ошибками» жила
    mistake = (await db.execute(
        select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.word_id == answer.word_id)
    )).scalar_one_or_none()
    if answer.is_correct:
        if mistake:
            mistake.count = 0
    else:
        if not mistake:
            mistake = UserMistake(user_id=user.id, word_id=answer.word_id, count=0)
            db.add(mistake)
        mistake.count += 1
    await db.commit()
    return {"ok": True, "strength": progress.strength}


class LessonComplete(BaseModel):
    kind: str  # "unit" | "daily"
    theme_id: Optional[int] = None
    lesson_no: Optional[int] = None
    correct: int = 0
    total: int = 0


def stars_for(correct: int, total: int) -> int:
    if total <= 0:
        return 1
    ratio = correct / total
    if ratio >= 0.9:
        return 3
    if ratio >= 0.7:
        return 2
    return 1


@router.post("/complete")
async def lesson_complete(payload: LessonComplete,
                          db: Annotated[AsyncSession, Depends(get_db)],
                          user: Annotated[User, Depends(get_current_user)]):
    stars = stars_for(payload.correct, payload.total)
    sticker: Optional[str] = None

    if payload.kind == "unit":
        if not payload.theme_id or not payload.lesson_no:
            raise HTTPException(status_code=400, detail="Нужны theme_id и lesson_no")
        theme = (await db.execute(select(Theme).where(Theme.id == payload.theme_id))).scalar_one_or_none()
        if not theme:
            raise HTTPException(status_code=404, detail="Тема не найдена")
        words = await unit_words(db, theme.id)
        total_lessons = lessons_total_for(len(words))
        p = (await db.execute(select(UnitProgress).where(
            UnitProgress.user_id == user.id, UnitProgress.theme_id == theme.id
        ))).scalar_one_or_none()
        if not p:
            p = UnitProgress(user_id=user.id, theme_id=theme.id, stars=0, lessons_done=0)
            db.add(p)
        p.lessons_done = max(p.lessons_done or 0, min(payload.lesson_no, total_lessons))
        if payload.lesson_no >= total_lessons:  # босс пройден
            p.stars = max(p.stars or 0, stars)
            if not p.completed_at:
                p.completed_at = now_utc()
                sticker = theme.icon_emoji or "🏅"
    elif payload.kind == "daily":
        date = today_str()
        d = (await db.execute(select(DailyLesson).where(
            DailyLesson.user_id == user.id, DailyLesson.date == date
        ))).scalar_one_or_none()
        if not d:
            d = DailyLesson(user_id=user.id, date=date)
            db.add(d)
        if not d.completed_at:
            d.completed_at = now_utc()
            d.stars = stars
    else:
        raise HTTPException(status_code=400, detail="kind должен быть unit или daily")

    await db.commit()
    streak = await compute_streak(db, user)
    if payload.kind == "daily" and streak in STREAK_STICKERS:
        sticker = STREAK_STICKERS[streak]

    if sticker:
        exists = (await db.execute(select(UserSticker).where(
            UserSticker.user_id == user.id, UserSticker.sticker == sticker
        ))).scalar_one_or_none()
        if exists:
            sticker_awarded = None
        else:
            db.add(UserSticker(user_id=user.id, sticker=sticker))
            await db.commit()
            sticker_awarded = sticker
    else:
        sticker_awarded = None

    return {"stars": stars, "sticker": sticker_awarded, "streak": streak}


@router.get("/home")
async def home_summary(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    date = today_str()
    d = (await db.execute(select(DailyLesson).where(
        DailyLesson.user_id == user.id, DailyLesson.date == date
    ))).scalar_one_or_none()
    daily_done = bool(d and d.completed_at)

    units = await get_ordered_units(db)
    progress = await unit_progress_map(db, user)
    current = None
    prev_done = True
    for t in units:
        p = progress.get(t.id)
        completed = bool(p and p.completed_at)
        if prev_done and not completed:
            lessons_done = p.lessons_done if p else 0
            words = await unit_words(db, t.id)
            current = {
                "theme_id": t.id, "title_ru": t.title_ru, "icon_emoji": t.icon_emoji or "📚",
                "next_lesson": min(lessons_done + 1, lessons_total_for(len(words))),
                "lessons_total": lessons_total_for(len(words)),
            }
            break
        prev_done = completed

    stickers = (await db.execute(select(UserSticker).where(UserSticker.user_id == user.id))).scalars().all()
    total_stars = sum((p.stars or 0) for p in progress.values())
    learned = (await db.execute(
        select(UserProgress).where(UserProgress.user_id == user.id, UserProgress.strength >= 2)
    )).scalars().all()

    return {
        "username": user.username,
        "daily_done": daily_done,
        "streak": await compute_streak(db, user),
        "stickers": [s.sticker for s in stickers],
        "total_stars": total_stars,
        "learned_words": len(learned),
        "current_unit": current,
    }
