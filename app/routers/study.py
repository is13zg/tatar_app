from typing import Annotated
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..deps import get_current_user
from ..database import get_db
from ..models import User, Theme, Word, UserProgress, UserMistake
from ..schemas import StudyItem, QuizItem, QuizOption, AnswerIn

router = APIRouter(prefix="/modes", tags=["modes"])


@router.get("/study/{theme_id}", response_model=list[StudyItem])
async def mode_study(theme_id: int, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    theme = (await db.execute(select(Theme).where(Theme.id == theme_id))).scalar_one_or_none()
    if not theme:
        raise HTTPException(status_code=404, detail="Тема не найдена")
    words = (await db.execute(select(Word).where(Word.theme_id == theme_id))).scalars().all()
    return [{"word": {"id": w.id, "text_tt": w.text_tt, "text_ru": w.text_ru, "image_url": w.image_url, "audio_url": w.audio_url or w.tts_url, "theme_id": w.theme_id}} for w in words]


@router.get("/repeat/{theme_id}", response_model=list[QuizItem])
async def mode_repeat(theme_id: int, db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    words = (await db.execute(select(Word).where(Word.theme_id == theme_id))).scalars().all()
    if len(words) < 4:
        raise HTTPException(status_code=400, detail="Для режима повторения нужно минимум 4 слова в теме")

    quiz_items: list[QuizItem] = []
    for w in words:
        wrong_options = [x for x in words if x.id != w.id]
        options = random.sample(wrong_options, 3) + [w]
        random.shuffle(options)
        quiz_items.append(
            QuizItem(
                word_id=w.id,
                text_tt=w.text_tt,
                audio_url=w.audio_url or w.tts_url,
                options=[QuizOption(id=o.id, image_url=o.image_url) for o in options],
            )
        )
    random.shuffle(quiz_items)
    return quiz_items


@router.post("/answer", response_model=None)
async def submit_answer(
    answer: AnswerIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
):
    # Update progress and mistakes
    progress = (await db.execute(select(UserProgress).where(UserProgress.user_id == user.id, UserProgress.word_id == answer.word_id))).scalar_one_or_none()
    if not progress:
        progress = UserProgress(user_id=user.id, word_id=answer.word_id, learned=False)
        db.add(progress)
    if answer.is_correct:
        progress.learned = True
        # reset mistake counter when correct
        mistake = (await db.execute(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.word_id == answer.word_id))).scalar_one_or_none()
        if mistake:
            mistake.count = 0
    else:
        mistake = (await db.execute(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.word_id == answer.word_id))).scalar_one_or_none()
        if not mistake:
            mistake = UserMistake(user_id=user.id, word_id=answer.word_id, count=0)
            db.add(mistake)
        mistake.count += 1
    await db.commit()


@router.get("/mistakes", response_model=list[QuizItem])
async def mode_mistakes(db: Annotated[AsyncSession, Depends(get_db)], user: Annotated[User, Depends(get_current_user)]):
    mistakes = (await db.execute(select(UserMistake).where(UserMistake.user_id == user.id, UserMistake.count > 0))).scalars().all()
    if not mistakes:
        return []
    word_ids = [m.word_id for m in mistakes]
    words = (await db.execute(select(Word).where(Word.id.in_(word_ids)))).scalars().all()

    # Build quiz items with options from corresponding themes
    items: list[QuizItem] = []
    theme_id_to_words: dict[int, list[Word]] = {}
    for w in words:
        if w.theme_id not in theme_id_to_words:
            theme_words = (await db.execute(select(Word).where(Word.theme_id == w.theme_id))).scalars().all()
            theme_id_to_words[w.theme_id] = theme_words
        pool = theme_id_to_words[w.theme_id]
        wrong_options = [x for x in pool if x.id != w.id]
        if len(wrong_options) < 3:
            continue
        options = random.sample(wrong_options, 3) + [w]
        random.shuffle(options)
        items.append(QuizItem(word_id=w.id, text_tt=w.text_tt, audio_url=w.audio_url or w.tts_url, options=[QuizOption(id=o.id, image_url=o.image_url) for o in options]))
    random.shuffle(items)
    return items
