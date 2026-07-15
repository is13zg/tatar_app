from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .config import STATIC_DIR
from .database import Base, engine, get_db, AsyncSessionLocal
from .models import User, Theme, Word, UserMistake, UserProgress
from .schemas import UserCreate, UserOut, Token, ThemeOut, WordOut, StatsOut, StatsTheme
from .security import get_password_hash, verify_password, create_access_token
from .routers.study import router as study_router
from .routers.admin import router as admin_router
from .routers.lessons import router as lessons_router
from .seed import seed_if_empty
from .deps import get_current_user
from .migrate import migrate_sqlite

app = FastAPI(title="TT-Learn Kids")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_path = Path(STATIC_DIR)
static_path.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


@app.get("/")
async def root():
    return RedirectResponse(url="/static/pages/login.html")


@app.on_event("startup")
async def on_startup() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # run lightweight migrations
    await migrate_sqlite(engine)
    async with AsyncSessionLocal() as session:
        await seed_if_empty(session)
        # ensure admin exists
        existing_admin = (await session.execute(select(User).where(User.username == "admin"))).scalar_one_or_none()
        if not existing_admin:
            admin = User(username="admin", password_hash=get_password_hash("admin217"), is_admin=True)
            session.add(admin)
            await session.commit()


# Auth
@app.post("/auth/register", response_model=UserOut)
async def register(user_in: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    existing = (await db.execute(select(User).where(User.username == user_in.username))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Имя пользователя занято")
    user = User(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return UserOut(id=user.id, username=user.username, email=user.email, created_at=user.created_at)


@app.post("/auth/login", response_model=Token)
async def login(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: Annotated[AsyncSession, Depends(get_db)]):
    user = (await db.execute(select(User).where(User.username == form_data.username))).scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверные логин или пароль")
    access_token = create_access_token({"sub": user.username})
    return Token(access_token=access_token)


@app.get("/auth/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_user)]):
    return UserOut(id=user.id, username=user.username, email=user.email, created_at=user.created_at)


@app.get("/themes", response_model=list[ThemeOut])
async def list_themes(db: Annotated[AsyncSession, Depends(get_db)]):
    themes = (await db.execute(select(Theme))).scalars().all()
    results: list[ThemeOut] = []
    for t in themes:
        sample = (await db.execute(select(Word.image_url).where(Word.theme_id == t.id, Word.image_url.is_not(None)).limit(1))).first()
        results.append(ThemeOut(id=t.id, title_ru=t.title_ru, description=t.description, sample_image_url=sample[0] if sample else None))
    return results


@app.get("/themes/{theme_id}/words", response_model=list[WordOut])
async def list_words(theme_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    words = (await db.execute(select(Word).where(Word.theme_id == theme_id))).scalars().all()
    return [
        WordOut(
            id=w.id,
            text_tt=w.text_tt,
            text_ru=w.text_ru,
            image_url=w.image_url,
            audio_url=w.audio_url,
            theme_id=w.theme_id,
            emoji=w.emoji,
            tts_url=w.tts_url,
        )
        for w in words
    ]


@app.get("/stats")
async def stats(user: Annotated[User, Depends(get_current_user)], db: Annotated[AsyncSession, Depends(get_db)]):
    total_words = (await db.execute(select(func.count(Word.id)))).scalar_one()
    learned_words = (await db.execute(select(func.count(UserProgress.id)).where(UserProgress.user_id == user.id, UserProgress.learned == True))).scalar_one()
    mistakes_total = (await db.execute(select(func.coalesce(func.sum(UserMistake.count), 0)).where(UserMistake.user_id == user.id))).scalar_one()

    themes = (await db.execute(select(Theme))).scalars().all()
    theme_stats: list[StatsTheme] = []
    for t in themes:
        t_total = (await db.execute(select(func.count(Word.id)).where(Word.theme_id == t.id))).scalar_one()
        t_learned = (await db.execute(select(func.count(UserProgress.id)).where(UserProgress.user_id == user.id, UserProgress.learned == True, UserProgress.word_id.in_(select(Word.id).where(Word.theme_id == t.id))))).scalar_one()
        t_mistakes = (await db.execute(select(func.coalesce(func.sum(UserMistake.count), 0)).where(UserMistake.user_id == user.id, UserMistake.word_id.in_(select(Word.id).where(Word.theme_id == t.id))))).scalar_one()
        theme_stats.append(StatsTheme(theme_id=t.id, title_ru=t.title_ru, total_words=t_total, learned_words=t_learned, mistakes=t_mistakes))

    total_users = (await db.execute(select(func.count(User.id)))).scalar_one()
    leaderboard_rows = await db.execute(
        select(User.username, func.count(UserProgress.id).label('cnt'))
        .join(UserProgress, User.id == UserProgress.user_id)
        .where(UserProgress.learned == True)
        .group_by(User.id)
        .order_by(func.count(UserProgress.id).desc())
        .limit(10)
    )
    leaderboard = [{"username": r[0], "learned": r[1]} for r in leaderboard_rows.all()]

    return {
        "total_words": total_words,
        "learned_words": learned_words,
        "mistakes_total": mistakes_total,
        "themes": [t.model_dump() for t in theme_stats],
        "total_users": total_users,
        "leaderboard": leaderboard,
    }


# include routers
app.include_router(study_router)
app.include_router(admin_router)
app.include_router(lessons_router)
