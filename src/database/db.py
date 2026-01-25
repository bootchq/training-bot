"""База данных SQLite"""
from datetime import datetime
from typing import Optional, List
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, Date, DateTime, JSON, Index
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from ..utils.config import Config
from ..utils.logger import logger

Base = declarative_base()


class User(Base):
    """Пользователь"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    garmin_email = Column(String, nullable=True)
    garmin_password = Column(String, nullable=True)
    # Strava OAuth
    strava_access_token = Column(String, nullable=True)
    strava_refresh_token = Column(String, nullable=True)
    strava_token_expires = Column(Integer, nullable=True)  # Unix timestamp
    # Google Calendar OAuth
    google_refresh_token = Column(String, nullable=True)
    # Токен для публичной ICS подписки
    calendar_token = Column(String, nullable=True, unique=True, index=True)
    # Цель и настройки тренировок
    goal_type = Column(String, nullable=True)  # race / weight_loss / endurance
    goal_distance_km = Column(Integer, nullable=True)  # для забега
    goal_date = Column(Date, nullable=True)  # дата забега
    experience_level = Column(String, nullable=True)  # beginner / intermediate / advanced
    include_strength = Column(Boolean, nullable=True)  # силовые да/нет
    training_days = Column(JSON, nullable=True)  # ["mon", "wed", "fri"]
    training_time = Column(String, nullable=True)  # "07:00" или "evening"
    onboarding_completed = Column(Boolean, default=False)  # прошёл ли онбординг
    created_at = Column(DateTime, default=datetime.utcnow)


class Training(Base):
    """Тренировка"""
    __tablename__ = "trainings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(String, nullable=False)  # planned / actual / skipped
    distance_km = Column(Float)
    duration_min = Column(Integer)
    avg_pace = Column(String)
    avg_hr = Column(Integer)
    max_hr = Column(Integer)
    elevation_m = Column(Integer)
    hr_zones = Column(JSON)
    notes = Column(String)

    __table_args__ = (
        Index('ix_trainings_user_date', 'user_id', 'date'),
    )


class TrainingPlan(Base):
    """План тренировок"""
    __tablename__ = "training_plan"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    type = Column(String, nullable=False)
    distance_km = Column(Float)
    duration_min = Column(Integer)
    target_zone = Column(String)
    description = Column(String)
    is_completed = Column(Boolean, default=False)

    __table_args__ = (
        Index('ix_training_plan_user_date', 'user_id', 'date'),
    )


class WellnessSurvey(Base):
    """Опросы самочувствия"""
    __tablename__ = "wellness_surveys"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    training_rating = Column(Integer)
    wellness_rating = Column(Integer)
    pain_reported = Column(Boolean, default=False)
    pain_location = Column(String)
    sleep_quality = Column(String)

    __table_args__ = (
        Index('ix_wellness_user_date', 'user_id', 'date'),
    )


class Goal(Base):
    """Цели (забеги)"""
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    date = Column(Date, nullable=False, index=True)
    distance_km = Column(Float, nullable=False)
    type = Column(String, nullable=False)


class Database:
    """Менеджер базы данных"""

    def __init__(self, db_path: str = None):
        """
        Инициализация БД

        Args:
            db_path: Путь к файлу БД (по умолчанию из Config)
        """
        if db_path is None:
            db_path = Config.DATABASE_PATH

        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        logger.info(f"База данных подключена: {db_path}")

    def create_tables(self):
        """Создание всех таблиц"""
        Base.metadata.create_all(self.engine)
        logger.info("Таблицы созданы")

        # Применяем миграции для существующих таблиц
        logger.info("🔄 Проверка необходимости миграции БД...")
        self._migrate_existing_tables()
        logger.info("✅ Проверка миграции завершена")

    def _migrate_existing_tables(self):
        """Миграция существующих таблиц (добавление новых полей)"""
        import sqlite3

        try:
            # Подключаемся напрямую к SQLite для проверки схемы
            db_path = str(self.engine.url).replace('sqlite:///', '')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Проверяем структуру таблицы users
            cursor.execute("PRAGMA table_info(users)")
            columns = [col[1] for col in cursor.fetchall()]

            needs_migration = False

            # Добавляем garmin_email если отсутствует
            if 'garmin_email' not in columns:
                logger.info("➕ Добавляю поле garmin_email в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN garmin_email VARCHAR")
                needs_migration = True

            # Добавляем garmin_password если отсутствует
            if 'garmin_password' not in columns:
                logger.info("➕ Добавляю поле garmin_password в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN garmin_password VARCHAR")
                needs_migration = True

            # Strava OAuth поля
            if 'strava_access_token' not in columns:
                logger.info("➕ Добавляю поля Strava в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN strava_access_token VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN strava_refresh_token VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN strava_token_expires INTEGER")
                needs_migration = True

            # Google Calendar OAuth
            if 'google_refresh_token' not in columns:
                logger.info("➕ Добавляю поле google_refresh_token в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN google_refresh_token VARCHAR")
                needs_migration = True

            # Токен для ICS подписки
            if 'calendar_token' not in columns:
                logger.info("➕ Добавляю поле calendar_token в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN calendar_token VARCHAR")
                needs_migration = True

            # Поля для цели и настроек тренировок
            if 'goal_type' not in columns:
                logger.info("➕ Добавляю поля цели в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN goal_type VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN goal_distance_km INTEGER")
                cursor.execute("ALTER TABLE users ADD COLUMN goal_date DATE")
                cursor.execute("ALTER TABLE users ADD COLUMN experience_level VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN include_strength BOOLEAN")
                cursor.execute("ALTER TABLE users ADD COLUMN training_days TEXT")  # JSON хранится как TEXT
                cursor.execute("ALTER TABLE users ADD COLUMN training_time VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0")
                needs_migration = True

            if needs_migration:
                conn.commit()
                logger.info("✅ Миграция базы данных успешно применена")
            else:
                logger.debug("✅ Схема базы данных актуальна")

            conn.close()

        except Exception as e:
            logger.error(f"❌ Ошибка при миграции базы данных: {e}")
            # Не падаем, просто логируем - возможно таблица ещё не создана

    @contextmanager
    def get_session(self):
        """Context manager для сессии БД"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_or_create_user(self, telegram_id: int) -> User:
        """
        Получить или создать пользователя

        Args:
            telegram_id: ID пользователя в Telegram

        Returns:
            Объект пользователя
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = User(telegram_id=telegram_id)
                session.add(user)
                session.flush()
                session.refresh(user)
                logger.info(f"Создан новый пользователь: {telegram_id}")

            # Загружаем все атрибуты и отсоединяем от сессии
            user_id = user.id
            user_telegram_id = user.telegram_id
            session.expunge(user)
            return user

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Получить пользователя по ID

        Args:
            user_id: ID пользователя в БД

        Returns:
            Объект пользователя или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if user:
                session.expunge(user)
            return user

    def get_all_onboarded_users(self) -> List[User]:
        """
        Получить всех пользователей с завершенным онбордингом

        Returns:
            Список пользователей
        """
        with self.get_session() as session:
            users = session.query(User).filter_by(onboarding_completed=True).all()
            for user in users:
                session.expunge(user)
            return users

    def load_training_plan(self, user_id: int, trainings: List[dict]) -> int:
        """
        Загрузка плана тренировок в БД

        Args:
            user_id: ID пользователя
            trainings: Список тренировок (из парсера)

        Returns:
            Количество загруженных тренировок
        """
        count = 0

        with self.get_session() as session:
            # Удаляем существующий план пользователя
            session.query(TrainingPlan).filter_by(user_id=user_id).delete()

            for training_data in trainings:
                plan = TrainingPlan(
                    user_id=user_id,
                    date=training_data['date'],
                    type=training_data.get('workout_type', 'easy'),
                    distance_km=training_data.get('distance_km'),
                    duration_min=training_data.get('duration_min'),
                    target_zone=training_data.get('target_zone'),
                    description=training_data.get('description', ''),
                    is_completed=False
                )
                session.add(plan)
                count += 1

            logger.info(f"Загружено {count} тренировок в план")

        return count

    def get_plan_for_date(self, user_id: int, target_date) -> Optional[TrainingPlan]:
        """
        Получить план на конкретную дату

        Args:
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Тренировка из плана или None
        """
        with self.get_session() as session:
            plan = session.query(TrainingPlan).filter_by(
                user_id=user_id,
                date=target_date
            ).first()

            if plan:
                # Загружаем атрибуты перед отсоединением
                _ = (plan.id, plan.date, plan.type, plan.distance_km,
                     plan.duration_min, plan.target_zone, plan.description)
                session.expunge(plan)

            return plan

    def get_plan_for_week(self, user_id: int, start_date) -> List[TrainingPlan]:
        """
        Получить план на неделю

        Args:
            user_id: ID пользователя
            start_date: Начало недели

        Returns:
            Список тренировок на неделю
        """
        from datetime import timedelta

        end_date = start_date + timedelta(days=7)

        with self.get_session() as session:
            plans = session.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.date >= start_date,
                TrainingPlan.date < end_date
            ).order_by(TrainingPlan.date).all()

            # Загружаем все атрибуты перед отсоединением
            for plan in plans:
                _ = (plan.id, plan.date, plan.type, plan.distance_km,
                     plan.duration_min, plan.target_zone, plan.description)

            session.expunge_all()
            return plans

    def get_training_for_date(self, user_id: int, target_date) -> Optional[Training]:
        """
        Получить тренировку за конкретную дату

        Args:
            user_id: ID пользователя
            target_date: Дата

        Returns:
            Последняя тренировка за день или None
        """
        with self.get_session() as session:
            training = session.query(Training).filter_by(
                user_id=user_id,
                date=target_date,
                type='actual'
            ).order_by(Training.id.desc()).first()

            if training:
                # Загружаем атрибуты перед отсоединением
                _ = (training.id, training.date, training.distance_km,
                     training.duration_min, training.avg_hr, training.hr_zones)
                session.expunge(training)

            return training

    def get_latest_training(self, user_id: int) -> Optional[Training]:
        """
        Получить последнюю тренировку пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Последняя тренировка или None
        """
        with self.get_session() as session:
            training = session.query(Training).filter_by(
                user_id=user_id,
                type='actual'
            ).order_by(Training.date.desc(), Training.id.desc()).first()

            if training:
                # Загружаем все атрибуты перед отсоединением
                _ = (training.id, training.date, training.distance_km,
                     training.duration_min, training.avg_hr, training.hr_zones,
                     training.avg_pace, training.max_hr, training.elevation_m, training.notes)
                session.expunge(training)

            return training

    def get_plan_for_period(self, user_id: int, start_date, end_date) -> List[TrainingPlan]:
        """
        Получить план за период

        Args:
            user_id: ID пользователя
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Список тренировок
        """
        with self.get_session() as session:
            plans = session.query(TrainingPlan).filter(
                TrainingPlan.user_id == user_id,
                TrainingPlan.date >= start_date,
                TrainingPlan.date <= end_date
            ).order_by(TrainingPlan.date).all()

            # Загружаем атрибуты
            for plan in plans:
                _ = (plan.id, plan.date, plan.type, plan.distance_km,
                     plan.duration_min, plan.target_zone, plan.description)

            session.expunge_all()
            return plans

    def update_training_plan(self, plan_id: int, **kwargs) -> bool:
        """
        Обновить план тренировки

        Args:
            plan_id: ID плана
            **kwargs: Поля для обновления

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            plan = session.query(TrainingPlan).filter_by(id=plan_id).first()

            if not plan:
                logger.warning(f"План {plan_id} не найден")
                return False

            # Обновляем поля
            for key, value in kwargs.items():
                if hasattr(plan, key):
                    setattr(plan, key, value)

            logger.info(f"Обновлён план {plan_id}: {list(kwargs.keys())}")
            return True

    def save_wellness_survey(self, user_id: int, survey_date, **kwargs) -> bool:
        """
        Сохранить опрос самочувствия

        Args:
            user_id: ID пользователя
            survey_date: Дата опроса
            **kwargs: Данные опроса

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            # Проверяем, есть ли уже опрос за этот день
            existing = session.query(WellnessSurvey).filter_by(
                user_id=user_id,
                date=survey_date
            ).first()

            if existing:
                # Обновляем существующий
                for key, value in kwargs.items():
                    if hasattr(existing, key):
                        setattr(existing, key, value)
            else:
                # Создаём новый
                survey = WellnessSurvey(
                    user_id=user_id,
                    date=survey_date,
                    **kwargs
                )
                session.add(survey)

            logger.info(f"Сохранён опрос самочувствия для пользователя {user_id} на {survey_date}")
            return True

    def save_garmin_credentials(self, telegram_id: int, email: str, password: str) -> bool:
        """
        Сохранить учетные данные Garmin для пользователя

        Args:
            telegram_id: ID пользователя в Telegram
            email: Email от Garmin
            password: Пароль от Garmin

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()

            if not user:
                logger.warning(f"Пользователь {telegram_id} не найден")
                return False

            user.garmin_email = email
            user.garmin_password = password

            logger.info(f"Сохранены учетные данные Garmin для пользователя {telegram_id}")
            return True

    def get_user_garmin_credentials(self, user_id: int) -> Optional[tuple]:
        """
        Получить учетные данные Garmin пользователя

        Args:
            user_id: ID пользователя (внутренний)

        Returns:
            Tuple (email, password) или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()

            if not user or not user.garmin_email:
                return None

            return (user.garmin_email, user.garmin_password)

    def save_user_strava_credentials(self, user_id: int, access_token: str, refresh_token: str, expires_at: int) -> bool:
        """
        Сохранить токены Strava для пользователя

        Args:
            user_id: ID пользователя
            access_token: Access token
            refresh_token: Refresh token
            expires_at: Unix timestamp истечения

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            user.strava_access_token = access_token
            user.strava_refresh_token = refresh_token
            user.strava_token_expires = expires_at

            logger.info(f"Сохранены токены Strava для пользователя {user_id}")
            return True

    def get_user_strava_credentials(self, user_id: int) -> Optional[tuple]:
        """
        Получить токены Strava пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Tuple (access_token, refresh_token, expires_at) или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()

            if not user or not user.strava_refresh_token:
                return None

            return (user.strava_access_token, user.strava_refresh_token, user.strava_token_expires)

    def save_user_google_credentials(self, user_id: int, refresh_token: str) -> bool:
        """
        Сохранить refresh token Google для пользователя

        Args:
            user_id: ID пользователя
            refresh_token: Refresh token

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            user.google_refresh_token = refresh_token

            logger.info(f"Сохранён Google refresh token для пользователя {user_id}")
            return True

    def get_user_google_credentials(self, user_id: int) -> Optional[str]:
        """
        Получить Google refresh token пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Refresh token или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()

            if not user or not user.google_refresh_token:
                return None

            return user.google_refresh_token

    def save_user_goal(self, user_id: int, goal_type: str, goal_distance_km: int = None,
                       goal_date=None, experience_level: str = None,
                       include_strength: bool = None, training_days: list = None,
                       training_time: str = None) -> bool:
        """
        Сохранить цель и настройки тренировок пользователя

        Args:
            user_id: ID пользователя
            goal_type: Тип цели (race / weight_loss / endurance)
            goal_distance_km: Дистанция забега в км
            goal_date: Дата забега
            experience_level: Уровень опыта
            include_strength: Включить силовые
            training_days: Дни тренировок
            training_time: Время тренировок

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            user.goal_type = goal_type
            if goal_distance_km is not None:
                user.goal_distance_km = goal_distance_km
            if goal_date is not None:
                user.goal_date = goal_date
            if experience_level is not None:
                user.experience_level = experience_level
            if include_strength is not None:
                user.include_strength = include_strength
            if training_days is not None:
                user.training_days = training_days
            if training_time is not None:
                user.training_time = training_time
            user.onboarding_completed = True

            logger.info(f"Сохранены настройки цели для пользователя {user_id}: {goal_type}")
            return True

    def get_user_settings(self, user_id: int) -> Optional[dict]:
        """
        Получить настройки пользователя

        Args:
            user_id: ID пользователя

        Returns:
            Словарь с настройками или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()

            if not user:
                return None

            return {
                'goal_type': user.goal_type,
                'goal_distance_km': user.goal_distance_km,
                'goal_date': user.goal_date,
                'experience_level': user.experience_level,
                'include_strength': user.include_strength,
                'training_days': user.training_days,
                'training_time': user.training_time,
                'onboarding_completed': user.onboarding_completed
            }

    def get_or_create_calendar_token(self, user_id: int) -> str:
        """
        Получить или создать токен для ICS подписки

        Args:
            user_id: ID пользователя

        Returns:
            Уникальный токен для URL
        """
        import secrets

        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return None

            if not user.calendar_token:
                # Генерируем уникальный токен (16 байт = 32 hex символа)
                user.calendar_token = secrets.token_hex(16)
                logger.info(f"Создан calendar_token для user_id={user_id}")

            return user.calendar_token

    def get_user_by_calendar_token(self, token: str) -> Optional[User]:
        """
        Найти пользователя по токену календаря

        Args:
            token: Токен из URL

        Returns:
            User или None
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(calendar_token=token).first()
            if user:
                # Возвращаем копию данных
                return User(
                    id=user.id,
                    telegram_id=user.telegram_id,
                    calendar_token=user.calendar_token
                )
            return None

    def reset_user(self, telegram_id: int) -> bool:
        """
        Сбросить данные пользователя для повторного онбординга

        Args:
            telegram_id: Telegram ID

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(telegram_id=telegram_id).first()
            if not user:
                return False

            # Сбрасываем всё кроме telegram_id
            user.garmin_email = None
            user.garmin_password = None
            user.strava_access_token = None
            user.strava_refresh_token = None
            user.strava_token_expires = None
            user.google_refresh_token = None
            user.goal_type = None
            user.goal_distance_km = None
            user.goal_date = None
            user.experience_level = None
            user.include_strength = None
            user.training_days = None
            user.training_time = None
            user.onboarding_completed = False

            logger.info(f"Пользователь {telegram_id} сброшен")
            return True


# Глобальный экземпляр БД
db = Database()
