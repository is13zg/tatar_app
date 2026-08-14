from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, ForeignKey, DateTime, UniqueConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(120), unique=False, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    progress: Mapped[list["UserProgress"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    mistakes: Mapped[list["UserMistake"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Theme(Base):
    __tablename__ = "themes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title_ru: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title_tt: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    icon_emoji: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    # ручная приёмка: заполняется, когда владелец сам прошёл тему в приложении
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checked_note: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    words: Mapped[list["Word"]] = relationship(back_populates="theme", cascade="all, delete-orphan")


class Word(Base):
    __tablename__ = "words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    text_tt: Mapped[str] = mapped_column(String(120), index=True)
    text_ru: Mapped[str] = mapped_column(String(120))
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audio_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    emoji: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    tts_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_flag: Mapped[int] = mapped_column(Integer, default=0)  # 1 = картинка помечена как неудачная
    image_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # последний промпт генерации
    sentence_tt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sentence_ru: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sentence_audio_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    theme: Mapped[Theme] = relationship(back_populates="words")
    progress: Mapped[list["UserProgress"]] = relationship(back_populates="word", cascade="all, delete-orphan")
    mistakes: Mapped[list["UserMistake"]] = relationship(back_populates="word", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("theme_id", "text_tt", name="uq_theme_word_tt"),
    )


class UserProgress(Base):
    __tablename__ = "user_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    learned: Mapped[bool] = mapped_column(default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    strength: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship(back_populates="progress")
    word: Mapped[Word] = relationship(back_populates="progress")

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
    )


class UnitProgress(Base):
    __tablename__ = "unit_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    stars: Mapped[int] = mapped_column(Integer, default=0)
    lessons_done: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "theme_id", name="uq_user_theme_unit"),
    )


class LessonResult(Base):
    __tablename__ = "lesson_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    theme_id: Mapped[int] = mapped_column(ForeignKey("themes.id", ondelete="CASCADE"))
    lesson_no: Mapped[int] = mapped_column(Integer)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "theme_id", "lesson_no", name="uq_user_lesson_result"),
    )


class DailyLesson(Base):
    __tablename__ = "daily_lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    date: Mapped[str] = mapped_column(String(10), index=True)  # YYYY-MM-DD
    items_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    stars: Mapped[int] = mapped_column(Integer, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_daily_date"),
    )


class UserSticker(Base):
    __tablename__ = "user_stickers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    sticker: Mapped[str] = mapped_column(String(16))
    earned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("user_id", "sticker", name="uq_user_sticker"),
    )


class UserMistake(Base):
    __tablename__ = "user_mistakes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"))
    count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="mistakes")
    word: Mapped[Word] = relationship(back_populates="mistakes")

    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_mistake"),
    )


class PhraseImage(Base):
    """Картинка, привязанная к точной татарской фразе.

    Ключ — сама строка, как в кэше озвучки: фраза живёт в tools/stories.py и в
    PLACE_SCENES, у неё нет своего id в базе, а картинка нужна именно на
    ситуацию («кот РЯДОМ с кроватью» против «кот ПОД кроватью»)."""

    __tablename__ = "phrase_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    phrase: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    image_url: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class StudySession(Base):
    """Одно занятие: что проходили, когда начали, сколько длилось.

    lesson_results хранит ЛУЧШИЙ результат по уроку и перезаписывается, поэтому
    по нему нельзя сказать, когда ребёнок занимался и сколько раз. Здесь строка
    на каждое пройденное занятие и ничего не перезаписывается."""

    __tablename__ = "study_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(16))            # unit | daily | review
    theme_id: Mapped[Optional[int]] = mapped_column(ForeignKey("themes.id", ondelete="SET NULL"), nullable=True)
    lesson_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[int] = mapped_column(Integer, default=0)
    stars: Mapped[int] = mapped_column(Integer, default=0)
    seconds: Mapped[int] = mapped_column(Integer, default=0)  # присылает клиент: сервер знает только момент финиша
    started_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
