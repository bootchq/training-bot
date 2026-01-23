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
        self._migrate_existing_tables()

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


# Глобальный экземпляр БД
db = Database()
