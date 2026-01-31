"""Модели данных приложения"""
from datetime import date
from datetime import datetime
from enum import Enum
from typing import Dict
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class TrainingType(str, Enum):
    """Типы тренировок"""
    PLANNED = "planned"
    ACTUAL = "actual"
    SKIPPED = "skipped"


class WorkoutType(str, Enum):
    """Виды тренировок"""
    EASY = "easy"              # Лёгкая
    TEMPO = "tempo"            # Темповая
    INTERVALS = "intervals"    # Интервалы
    LONG = "long"              # Длительная
    TRAIL = "trail"            # Трейл
    STRENGTH = "strength"      # Силовая


class Training(BaseModel):
    """Тренировка"""
    id: Optional[int] = None
    user_id: int
    date: date
    type: TrainingType
    workout_type: WorkoutType
    distance_km: Optional[float] = None
    duration_min: Optional[int] = None
    avg_pace: Optional[str] = None  # Формат: "6:30"
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    elevation_m: Optional[int] = None
    hr_zones: Optional[Dict[str, int]] = None  # {"z1": 0, "z2": 45, ...}
    notes: Optional[str] = None


class PlannedTraining(BaseModel):
    """Запланированная тренировка"""
    id: Optional[int] = None
    user_id: int
    date: date
    workout_type: WorkoutType
    distance_km: float
    duration_min: Optional[int] = None
    target_zone: str  # "z2", "z3", etc.
    description: str
    is_completed: bool = False


class WellnessSurvey(BaseModel):
    """Опрос самочувствия"""
    id: Optional[int] = None
    user_id: int
    date: date
    training_rating: int = Field(ge=1, le=10)  # 1-10
    wellness_rating: int = Field(ge=1, le=3)   # 1-усталость, 2-норма, 3-отлично
    pain_reported: bool = False
    pain_location: Optional[str] = None
    sleep_quality: str  # "плохой", "норма", "отличный"


class Goal(BaseModel):
    """Цель (забег)"""
    id: Optional[int] = None
    user_id: int
    name: str
    date: date
    distance_km: float
    goal_type: str  # "марафон", "трейл"


class User(BaseModel):
    """Пользователь"""
    id: Optional[int] = None
    telegram_id: int
    created_at: Optional[datetime] = None
