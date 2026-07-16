from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserBase(BaseModel):
    username: str
    email: Optional[str] = None


class UserCreate(UserBase):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=4)
    password_confirm: str = Field(min_length=4)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.password_confirm:
            raise ValueError("Пароли не совпадают")
        return self


class UserOut(UserBase):
    id: int
    created_at: datetime
    is_admin: bool = False


class ThemeOut(BaseModel):
    id: int
    title_ru: str
    description: Optional[str] = None
    sample_image_url: Optional[str] = None
    icon_emoji: Optional[str] = None
    title_tt: Optional[str] = None


class WordOut(BaseModel):
    id: int
    text_tt: str
    text_ru: str
    image_url: Optional[str] = None
    audio_url: Optional[str] = None
    theme_id: int
    emoji: Optional[str] = None
    tts_url: Optional[str] = None


class StudyItem(BaseModel):
    word: WordOut


class QuizOption(BaseModel):
    id: int
    image_url: Optional[str] = None
    emoji: Optional[str] = None


class QuizItem(BaseModel):
    word_id: int
    text_tt: str
    audio_url: Optional[str] = None
    options: list[QuizOption]


class AnswerIn(BaseModel):
    word_id: int
    is_correct: bool


class StatsTheme(BaseModel):
    theme_id: int
    title_ru: str
    total_words: int
    learned_words: int
    mistakes: int


class StatsOut(BaseModel):
    total_words: int
    learned_words: int
    mistakes_total: int
    themes: list[StatsTheme]
