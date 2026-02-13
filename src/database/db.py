"""База данных SQLite"""
from contextlib import contextmanager
from datetime import datetime
from typing import List
from typing import Optional

from sqlalchemy import JSON
from sqlalchemy import BigInteger
from sqlalchemy import Boolean
from sqlalchemy import Column
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import Index
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import sessionmaker

from ..utils.config import Config
from ..utils.logger import logger

Base = declarative_base()


class User(Base):
    """Пользователь"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
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
    goal_type = Column(String, nullable=True)  # race / weight_loss / endurance / trail
    goal_distance_km = Column(Integer, nullable=True)  # для забега
    goal_date = Column(Date, nullable=True)  # дата забега
    goal_elevation_gain = Column(Integer, nullable=True)  # набор высоты в метрах (для трейла)
    goal_aid_stations = Column(Integer, nullable=True)  # количество пунктов питания (для трейла)
    experience_level = Column(String, nullable=True)  # beginner / intermediate / advanced
    include_strength = Column(Boolean, nullable=True)  # силовые да/нет
    training_days = Column(JSON, nullable=True)  # ["mon", "wed", "fri"]
    training_time = Column(String, nullable=True)  # "07:00" или "evening" (deprecated)
    training_time_min = Column(Integer, nullable=True)  # Время на тренировку в минутах
    fitness_level = Column(String, nullable=True)  # beginner / intermediate / advanced (явно выбранный)
    start_time_weekday = Column(String, nullable=True)  # Время старта в будни "07:00"
    start_time_weekend = Column(String, nullable=True)  # Время старта в выходные "09:00"
    onboarding_completed = Column(Boolean, default=False)  # прошёл ли онбординг
    # Персонализация тренировок (из Garmin)
    lthr = Column(Integer, nullable=True)  # Lactate Threshold Heart Rate
    vdot = Column(Float, nullable=True)  # VDOT индекс (Jack Daniels)
    vdot_source = Column(String, nullable=True)  # Источник VDOT: "5k", "10k", "half", "marathon"
    vdot_time_seconds = Column(Integer, nullable=True)  # Время результата в секундах
    garmin_synced_at = Column(DateTime, nullable=True)  # Когда последний раз синхронизировали
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
    goal = Column(String, nullable=True)  # Цель тренировки
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

    # Session RPE: training_rating × duration_min (Foster et al.)
    srpe = Column(Integer)  # sRPE в arbitrary units (AU)

    # Recovery Index
    rhr = Column(Integer)  # Resting Heart Rate (утренний пульс покоя)
    hrv = Column(Integer)  # Heart Rate Variability (вариабельность пульса)

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


class PersonalRecord(Base):
    """Персональные рекорды пользователя"""
    __tablename__ = "personal_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    record_type = Column(String, nullable=False)  # longest_run, fastest_5k, fastest_10k, etc.
    value = Column(Float, nullable=False)  # Значение рекорда (км, мин/км, км/нед)
    training_id = Column(Integer)  # ID тренировки, где был установлен рекорд
    date_achieved = Column(Date, nullable=False)
    details = Column(JSON)  # Дополнительные детали (темп, пульс и т.д.)

    __table_args__ = (
        Index('ix_pr_user_type', 'user_id', 'record_type'),
    )


class VdotHistory(Base):
    """История изменения VDOT пользователя"""
    __tablename__ = "vdot_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    vdot = Column(Float, nullable=False)
    source = Column(String, nullable=False)  # "5k", "10k", "half", "marathon", "manual", "auto"
    time_seconds = Column(Integer)  # Время результата в секундах (для race источников)
    training_id = Column(Integer)  # ID тренировки, на основе которой рассчитан VDOT
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('ix_vdot_user_date', 'user_id', 'date'),
    )


class Reminder(Base):
    """Напоминания о тренировках (для умного удаления)"""
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, nullable=False, index=True)
    date = Column(Date, nullable=False)  # дата тренировки
    type = Column(String, nullable=False)  # "morning" / "pre_workout" / "sync"
    message_id = Column(Integer, nullable=False)  # Telegram message_id
    sent_at = Column(DateTime, default=datetime.utcnow)  # когда отправлено
    deleted_at = Column(DateTime, nullable=True)  # когда удалено

    __table_args__ = (
        Index('ix_reminder_user_date', 'user_id', 'date'),
    )


class Database:
    """Менеджер базы данных"""

    def __init__(self, db_path: str = None, db_url: str = None):
        """
        Инициализация БД

        Args:
            db_path: Путь к файлу SQLite БД (по умолчанию из Config.DATABASE_PATH)
            db_url: URL PostgreSQL БД (приоритет над db_path, по умолчанию из Config.DATABASE_URL)
        """
        # Приоритет: db_url > Config.DATABASE_URL > db_path > Config.DATABASE_PATH
        if db_url:
            database_url = db_url
            self.is_postgres = True
        elif Config.DATABASE_URL:
            database_url = Config.DATABASE_URL
            self.is_postgres = True
        else:
            if db_path is None:
                db_path = Config.DATABASE_PATH
            database_url = f"sqlite:///{db_path}"
            self.is_postgres = False

        # Конвертация URL для psycopg3
        if self.is_postgres and database_url.startswith("postgresql://"):
            database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)

        db_type = "PostgreSQL" if self.is_postgres else "SQLite"
        logger.info(f"База данных подключена: {db_type}")

    def create_tables(self):
        """Создание всех таблиц"""
        Base.metadata.create_all(self.engine)
        logger.info("Таблицы созданы")

        # Применяем миграции для существующих таблиц
        logger.info("🔄 Проверка необходимости миграции БД...")
        self._migrate_existing_tables()
        logger.info("✅ Проверка миграции завершена")

    def _migrate_postgres_types(self):
        """Миграция типов колонок для PostgreSQL"""
        try:
            with self.engine.begin() as conn:
                # Проверяем тип колонки telegram_id
                result = conn.execute(text("""
                    SELECT data_type
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                    AND column_name = 'telegram_id'
                """))
                row = result.fetchone()

                if row and row[0] == 'integer':
                    logger.info("➕ Изменяю тип telegram_id: INTEGER → BIGINT")
                    conn.execute(text("ALTER TABLE users ALTER COLUMN telegram_id TYPE BIGINT"))
                    logger.info("✅ Миграция типа telegram_id выполнена")
                else:
                    logger.debug("✅ Тип telegram_id актуален (BIGINT)")

        except Exception as e:
            logger.error(f"❌ Ошибка при миграции типов PostgreSQL: {e}")
            # Не падаем - возможно таблица ещё не создана

    def _migrate_existing_tables(self):
        """Миграция существующих таблиц (добавление новых полей)"""
        # Для PostgreSQL - только изменение типов колонок
        if self.is_postgres:
            self._migrate_postgres_types()
            return

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

            # Новые поля для времени тренировки и уровня подготовки
            if 'training_time_min' not in columns:
                logger.info("➕ Добавляю поле training_time_min в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN training_time_min INTEGER")
                needs_migration = True

            if 'fitness_level' not in columns:
                logger.info("➕ Добавляю поле fitness_level в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN fitness_level VARCHAR")
                needs_migration = True

            # Поля для персонализации тренировок (VDOT, LTHR)
            if 'lthr' not in columns:
                logger.info("➕ Добавляю поля персонализации (lthr, vdot) в таблицу users")
                cursor.execute("ALTER TABLE users ADD COLUMN lthr INTEGER")
                cursor.execute("ALTER TABLE users ADD COLUMN vdot REAL")
                cursor.execute("ALTER TABLE users ADD COLUMN vdot_source VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN vdot_time_seconds INTEGER")
                cursor.execute("ALTER TABLE users ADD COLUMN garmin_synced_at DATETIME")
                needs_migration = True

            # Поля для времени старта тренировок
            if 'start_time_weekday' not in columns:
                logger.info("➕ Добавляю поля времени старта (start_time_weekday, start_time_weekend)")
                cursor.execute("ALTER TABLE users ADD COLUMN start_time_weekday VARCHAR")
                cursor.execute("ALTER TABLE users ADD COLUMN start_time_weekend VARCHAR")
                needs_migration = True

            # Поля для трейл-забегов
            if 'goal_elevation_gain' not in columns:
                logger.info("➕ Добавляю поля для трейл-забегов (elevation_gain, aid_stations)")
                cursor.execute("ALTER TABLE users ADD COLUMN goal_elevation_gain INTEGER")
                cursor.execute("ALTER TABLE users ADD COLUMN goal_aid_stations INTEGER")
                needs_migration = True

            # Проверяем таблицу training_plan
            cursor.execute("PRAGMA table_info(training_plan)")
            plan_columns = [col[1] for col in cursor.fetchall()]

            if plan_columns and 'goal' not in plan_columns:
                logger.info("➕ Добавляю поле goal в таблицу training_plan")
                cursor.execute("ALTER TABLE training_plan ADD COLUMN goal VARCHAR")
                needs_migration = True

            # Проверяем таблицу wellness_surveys (Recovery Index)
            cursor.execute("PRAGMA table_info(wellness_surveys)")
            wellness_columns = [col[1] for col in cursor.fetchall()]

            if wellness_columns and 'rhr' not in wellness_columns:
                logger.info("➕ Добавляю поля Recovery Index (rhr, hrv) в таблицу wellness_surveys")
                cursor.execute("ALTER TABLE wellness_surveys ADD COLUMN rhr INTEGER")
                cursor.execute("ALTER TABLE wellness_surveys ADD COLUMN hrv INTEGER")
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
                    type=training_data.get('type') or training_data.get('workout_type', 'easy'),
                    distance_km=training_data.get('distance_km'),
                    duration_min=training_data.get('duration_min'),
                    target_zone=training_data.get('target_zone'),
                    description=training_data.get('description', ''),
                    goal=training_data.get('goal'),
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

    def get_user_trainings(self, user_id: int, limit: int = 60) -> List[Training]:
        """
        Получить последние тренировки пользователя

        Args:
            user_id: ID пользователя
            limit: Максимальное количество тренировок

        Returns:
            Список тренировок
        """
        with self.get_session() as session:
            trainings = session.query(Training).filter_by(
                user_id=user_id,
                type='actual'
            ).order_by(Training.date.desc()).limit(limit).all()

            # Загружаем атрибуты перед отсоединением
            result = []
            for t in trainings:
                _ = (t.id, t.date, t.distance_km, t.duration_min,
                     t.avg_hr, t.max_hr, t.hr_zones, t.avg_pace, t.elevation_m)
                session.expunge(t)
                result.append(t)

            return result

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

    def get_trainings_for_period(self, user_id: int, start_date, end_date) -> List[Training]:
        """
        Получить фактические тренировки за период

        Args:
            user_id: ID пользователя
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Список фактических тренировок
        """
        with self.get_session() as session:
            trainings = session.query(Training).filter(
                Training.user_id == user_id,
                Training.date >= start_date,
                Training.date <= end_date
            ).order_by(Training.date).all()

            # Загружаем атрибуты
            for t in trainings:
                _ = (t.id, t.date, t.type, t.distance_km, t.duration_min,
                     t.avg_pace, t.avg_hr, t.max_hr, t.elevation_m, t.hr_zones)

            session.expunge_all()
            return trainings

    def get_wellness_for_period(self, user_id: int, start_date, end_date) -> List[WellnessSurvey]:
        """
        Получить опросы самочувствия за период

        Args:
            user_id: ID пользователя
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Список опросов самочувствия
        """
        with self.get_session() as session:
            surveys = session.query(WellnessSurvey).filter(
                WellnessSurvey.user_id == user_id,
                WellnessSurvey.date >= start_date,
                WellnessSurvey.date <= end_date
            ).order_by(WellnessSurvey.date).all()

            # Загружаем атрибуты
            for s in surveys:
                _ = (s.id, s.date, s.training_rating, s.wellness_rating,
                     s.pain_reported, s.pain_location, s.sleep_quality, s.rhr, s.hrv)

            session.expunge_all()
            return surveys

    def save_vdot_history(self, user_id: int, vdot: float, source: str,
                          date=None, time_seconds=None, training_id=None):
        """
        Сохранить запись в истории VDOT

        Args:
            user_id: ID пользователя
            vdot: Значение VDOT
            source: Источник ("5k", "10k", "half", "marathon", "manual", "auto")
            date: Дата (по умолчанию сегодня)
            time_seconds: Время результата в секундах
            training_id: ID тренировки
        """
        if date is None:
            from datetime import date as date_class
            date = date_class.today()

        with self.get_session() as session:
            history = VdotHistory(
                user_id=user_id,
                date=date,
                vdot=vdot,
                source=source,
                time_seconds=time_seconds,
                training_id=training_id
            )
            session.add(history)
            session.commit()
            logger.info(f"VDOT history saved: user={user_id}, vdot={vdot}, source={source}")

    def get_vdot_history(self, user_id: int, start_date=None, end_date=None) -> List:
        """
        Получить историю VDOT пользователя

        Args:
            user_id: ID пользователя
            start_date: Начало периода (опционально)
            end_date: Конец периода (опционально)

        Returns:
            Список записей VdotHistory
        """
        with self.get_session() as session:
            query = session.query(VdotHistory).filter(VdotHistory.user_id == user_id)

            if start_date:
                query = query.filter(VdotHistory.date >= start_date)
            if end_date:
                query = query.filter(VdotHistory.date <= end_date)

            history = query.order_by(VdotHistory.date.desc()).all()

            # Загружаем атрибуты
            for h in history:
                _ = (h.id, h.date, h.vdot, h.source, h.time_seconds, h.training_id)

            session.expunge_all()
            return history

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

    def get_latest_wellness(self, user_id: int):
        """
        Получить последний опрос самочувствия

        Args:
            user_id: ID пользователя

        Returns:
            WellnessSurvey или None
        """
        with self.get_session() as session:
            return session.query(WellnessSurvey).filter_by(
                user_id=user_id
            ).order_by(WellnessSurvey.date.desc()).first()

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

    def save_user_goal(self, user_id: int, goal_type: str = None, goal_distance_km: int = None,
                       goal_date=None, goal_elevation_gain: int = None, goal_aid_stations: int = None,
                       experience_level: str = None, include_strength: bool = None, training_days: list = None,
                       training_time: str = None, training_time_min: int = None,
                       fitness_level: str = None,
                       start_time_weekday: str = None, start_time_weekend: str = None) -> bool:
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

            if goal_type is not None:
                user.goal_type = goal_type
            if goal_distance_km is not None:
                user.goal_distance_km = goal_distance_km
            if goal_date is not None:
                user.goal_date = goal_date
            if goal_elevation_gain is not None:
                user.goal_elevation_gain = goal_elevation_gain
            if goal_aid_stations is not None:
                user.goal_aid_stations = goal_aid_stations
            if experience_level is not None:
                user.experience_level = experience_level
            if include_strength is not None:
                user.include_strength = include_strength
            if training_days is not None:
                user.training_days = training_days
            if training_time is not None:
                user.training_time = training_time
            if training_time_min is not None:
                user.training_time_min = training_time_min
            if fitness_level is not None:
                user.fitness_level = fitness_level
            if start_time_weekday is not None:
                user.start_time_weekday = start_time_weekday
            if start_time_weekend is not None:
                user.start_time_weekend = start_time_weekend
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
                'training_time_min': user.training_time_min,
                'fitness_level': user.fitness_level,
                'start_time_weekday': user.start_time_weekday,
                'start_time_weekend': user.start_time_weekend,
                'onboarding_completed': user.onboarding_completed,
                'lthr': user.lthr,
                'vdot': user.vdot,
                'vdot_source': user.vdot_source,
                'vdot_time_seconds': user.vdot_time_seconds,
                'garmin_synced_at': user.garmin_synced_at
            }

    def save_user_physiology(self, user_id: int, lthr: int = None, vdot: float = None,
                               vdot_source: str = None, vdot_time_seconds: int = None) -> bool:
        """
        Сохранить физиологические данные пользователя (LTHR, VDOT)

        Args:
            user_id: ID пользователя
            lthr: Lactate Threshold Heart Rate
            vdot: VDOT индекс
            vdot_source: Источник VDOT ("5k", "10k", "half", "marathon")
            vdot_time_seconds: Время результата в секундах

        Returns:
            True если успешно
        """
        with self.get_session() as session:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                return False

            if lthr is not None:
                user.lthr = lthr
            if vdot is not None:
                user.vdot = vdot
            if vdot_source is not None:
                user.vdot_source = vdot_source
            if vdot_time_seconds is not None:
                user.vdot_time_seconds = vdot_time_seconds
            user.garmin_synced_at = datetime.utcnow()

            logger.info(f"Сохранены физиологические данные для user_id={user_id}: LTHR={lthr}, VDOT={vdot}")
            return True

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

            # Удаляем все связанные данные
            deleted_trainings = session.query(Training).filter_by(user_id=user.id).delete()
            deleted_plans = session.query(TrainingPlan).filter_by(user_id=user.id).delete()
            deleted_wellness = session.query(WellnessSurvey).filter_by(user_id=user.id).delete()
            deleted_goals = session.query(Goal).filter_by(user_id=user.id).delete()
            deleted_records = session.query(PersonalRecord).filter_by(user_id=user.id).delete()
            deleted_reminders = session.query(Reminder).filter_by(user_id=user.id).delete()

            # Сбрасываем всё кроме telegram_id и Garmin credentials (для тестирования)
            # user.garmin_email = None  # СОХРАНЯЕМ для удобства тестирования
            # user.garmin_password = None  # СОХРАНЯЕМ для удобства тестирования
            user.strava_access_token = None
            user.strava_refresh_token = None
            user.strava_token_expires = None
            user.google_refresh_token = None
            user.calendar_token = None
            user.goal_type = None
            user.goal_distance_km = None
            user.goal_date = None
            user.experience_level = None
            user.include_strength = None
            user.training_days = None
            user.training_time = None
            user.training_time_min = None
            user.fitness_level = None
            user.start_time_weekday = None
            user.start_time_weekend = None
            user.lthr = None
            user.vdot = None
            user.vdot_source = None
            user.vdot_time_seconds = None
            user.garmin_synced_at = None
            user.onboarding_completed = False

            logger.info(
                f"Пользователь {telegram_id} полностью сброшен: "
                f"trainings={deleted_trainings}, plans={deleted_plans}, "
                f"wellness={deleted_wellness}, goals={deleted_goals}, records={deleted_records}, "
                f"reminders={deleted_reminders}"
            )
            return True

    def save_reminder(self, user_id: int, date, reminder_type: str, message_id: int) -> bool:
        """
        Сохранить напоминание с message_id для последующего удаления

        Args:
            user_id: ID пользователя
            date: Дата тренировки
            reminder_type: Тип напоминания ("morning" / "pre_workout" / "sync")
            message_id: Telegram message_id

        Returns:
            True если успешно
        """
        try:
            with self.get_session() as session:
                reminder = Reminder(
                    user_id=user_id,
                    date=date,
                    type=reminder_type,
                    message_id=message_id
                )
                session.add(reminder)
            logger.info(f"Сохранено напоминание {reminder_type} для user_id={user_id}, message_id={message_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения напоминания: {e}")
            return False

    def get_reminders_to_delete(self, user_id: int, date, reminder_type: str = None) -> List[Reminder]:
        """
        Получить напоминания для удаления

        Args:
            user_id: ID пользователя
            date: Дата тренировки
            reminder_type: Тип напоминания (опционально)

        Returns:
            Список напоминаний
        """
        try:
            with self.get_session() as session:
                query = session.query(Reminder).filter(
                    Reminder.user_id == user_id,
                    Reminder.date == date,
                    Reminder.deleted_at.is_(None)
                )

                if reminder_type:
                    query = query.filter(Reminder.type == reminder_type)

                return query.all()
        except Exception as e:
            logger.error(f"Ошибка получения напоминаний: {e}")
            return []

    def mark_reminder_deleted(self, reminder_id: int) -> bool:
        """
        Отметить напоминание как удалённое

        Args:
            reminder_id: ID напоминания

        Returns:
            True если успешно
        """
        try:
            with self.get_session() as session:
                reminder = session.query(Reminder).filter_by(id=reminder_id).first()
                if reminder:
                    reminder.deleted_at = datetime.utcnow()
                    logger.info(f"Напоминание {reminder_id} отмечено как удалённое")
                    return True
                return False
        except Exception as e:
            logger.error(f"Ошибка отметки удаления напоминания: {e}")
            return False

    def get_admin_stats(self) -> dict:
        """
        Получить статистику для админки

        Returns:
            dict с полями:
            - total_users: всего пользователей
            - users_with_garmin: с Garmin credentials
            - active_last_week: активных за неделю (синхронизировали или смотрели статистику)
        """
        from datetime import datetime, timedelta
        week_ago = datetime.now() - timedelta(days=7)

        with self.get_session() as session:
            # Всего пользователей
            total_users = session.query(User).count()

            # С Garmin credentials
            users_with_garmin = session.query(User).filter(
                User.garmin_email.isnot(None),
                User.garmin_password.isnot(None)
            ).count()

            # Активные за неделю (есть тренировки за последние 7 дней)
            active_user_ids = session.query(Training.user_id).filter(
                Training.date >= week_ago.date()
            ).distinct().count()

            # Завершили онбординг
            onboarded_users = session.query(User).filter(
                User.onboarding_completed == True
            ).count()

            return {
                "total_users": total_users,
                "users_with_garmin": users_with_garmin,
                "active_last_week": active_user_ids,
                "onboarded_users": onboarded_users
            }


# Глобальный экземпляр БД
db = Database()
