"""Система персональных рекордов"""
from datetime import date as dt_date
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional

from sqlalchemy import and_

from ..database.db import PersonalRecord
from ..database.db import Training
from ..database.db import db
from ..utils.logger import logger


class RecordsManager:
    """Менеджер персональных рекордов"""

    # Типы рекордов и их названия
    RECORD_TYPES = {
        'longest_run': 'Самая длинная пробежка',
        'fastest_5k': 'Лучший темп на 5 км',
        'fastest_10k': 'Лучший темп на 10 км',
        'fastest_half_marathon': 'Лучший темп на полумарафон',
        'fastest_marathon': 'Лучший темп на марафон',
        'weekly_volume': 'Максимальный недельный объем'
    }

    def __init__(self, user_id: int):
        """
        Инициализация

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id

    def check_training_for_records(self, training: Training) -> List[Dict]:
        """
        Проверить тренировку на новые рекорды

        Args:
            training: Объект тренировки

        Returns:
            Список новых рекордов
        """
        new_records = []

        # Проверяем самую длинную пробежку
        if training.distance_km:
            if self._check_longest_run(training):
                new_records.append({
                    'type': 'longest_run',
                    'name': self.RECORD_TYPES['longest_run'],
                    'value': training.distance_km,
                    'unit': 'км',
                    'training': training
                })

        # Проверяем темп на разных дистанциях
        if training.distance_km and training.avg_pace:
            pace_records = self._check_pace_records(training)
            new_records.extend(pace_records)

        # Проверяем недельный объем
        weekly_record = self._check_weekly_volume(training.date)
        if weekly_record:
            new_records.append(weekly_record)

        return new_records

    def _check_longest_run(self, training: Training) -> bool:
        """Проверить рекорд самой длинной пробежки"""
        with db.get_session() as session:
            current_record = session.query(PersonalRecord).filter(
                and_(
                    PersonalRecord.user_id == self.user_id,
                    PersonalRecord.record_type == 'longest_run'
                )
            ).first()

            if not current_record or training.distance_km > current_record.value:
                # Новый рекорд
                if current_record:
                    session.delete(current_record)

                new_record = PersonalRecord(
                    user_id=self.user_id,
                    record_type='longest_run',
                    value=training.distance_km,
                    training_id=training.id,
                    date_achieved=training.date,
                    details={'pace': training.avg_pace, 'hr': training.avg_hr}
                )
                session.add(new_record)
                logger.info(f"🏆 Новый рекорд longest_run для user={self.user_id}: {training.distance_km} км")
                return True

        return False

    def _check_pace_records(self, training: Training) -> List[Dict]:
        """Проверить рекорды темпа на разных дистанциях"""
        new_records = []

        # Определяем дистанцию тренировки
        distance_km = training.distance_km

        # Преобразуем темп в секунды на км для сравнения
        try:
            pace_sec_per_km = self._pace_to_seconds(training.avg_pace)
        except:
            return new_records

        # Проверяем соответствие дистанциям (с допуском ±10%)
        distance_records = {
            'fastest_5k': (5.0, 0.5),  # 5 км ± 0.5 км
            'fastest_10k': (10.0, 1.0),  # 10 км ± 1 км
            'fastest_half_marathon': (21.1, 2.0),  # 21.1 км ± 2 км
            'fastest_marathon': (42.2, 4.0)  # 42.2 км ± 4 км
        }

        for record_type, (target_distance, tolerance) in distance_records.items():
            if abs(distance_km - target_distance) <= tolerance:
                if self._update_pace_record(record_type, pace_sec_per_km, training):
                    new_records.append({
                        'type': record_type,
                        'name': self.RECORD_TYPES[record_type],
                        'value': training.avg_pace,
                        'unit': 'мин/км',
                        'training': training
                    })

        return new_records

    def _update_pace_record(self, record_type: str, pace_sec_per_km: float, training: Training) -> bool:
        """Обновить рекорд темпа"""
        with db.get_session() as session:
            current_record = session.query(PersonalRecord).filter(
                and_(
                    PersonalRecord.user_id == self.user_id,
                    PersonalRecord.record_type == record_type
                )
            ).first()

            # Меньший темп = лучше
            if not current_record or pace_sec_per_km < current_record.value:
                if current_record:
                    session.delete(current_record)

                new_record = PersonalRecord(
                    user_id=self.user_id,
                    record_type=record_type,
                    value=pace_sec_per_km,
                    training_id=training.id,
                    date_achieved=training.date,
                    details={'pace': training.avg_pace, 'distance': training.distance_km}
                )
                session.add(new_record)
                logger.info(f"🏆 Новый рекорд {record_type} для user={self.user_id}: {training.avg_pace}")
                return True

        return False

    def _check_weekly_volume(self, training_date: dt_date) -> Optional[Dict]:
        """Проверить недельный объем"""
        # Получаем неделю (понедельник - воскресенье)
        start_of_week = training_date - timedelta(days=training_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)

        # Суммируем объем за неделю
        with db.get_session() as session:
            trainings = session.query(Training).filter(
                and_(
                    Training.user_id == self.user_id,
                    Training.date >= start_of_week,
                    Training.date <= end_of_week,
                    Training.type == 'actual'
                )
            ).all()

            weekly_volume = sum(t.distance_km or 0 for t in trainings)

            # Проверяем рекорд
            current_record = session.query(PersonalRecord).filter(
                and_(
                    PersonalRecord.user_id == self.user_id,
                    PersonalRecord.record_type == 'weekly_volume'
                )
            ).first()

            if weekly_volume > 0 and (not current_record or weekly_volume > current_record.value):
                if current_record:
                    session.delete(current_record)

                new_record = PersonalRecord(
                    user_id=self.user_id,
                    record_type='weekly_volume',
                    value=weekly_volume,
                    date_achieved=end_of_week,
                    details={'start_date': str(start_of_week), 'end_date': str(end_of_week)}
                )
                session.add(new_record)
                logger.info(f"🏆 Новый рекорд weekly_volume для user={self.user_id}: {weekly_volume} км")

                return {
                    'type': 'weekly_volume',
                    'name': self.RECORD_TYPES['weekly_volume'],
                    'value': weekly_volume,
                    'unit': 'км',
                    'training': None
                }

        return None

    def get_all_records(self) -> Dict[str, Dict]:
        """Получить все рекорды пользователя"""
        with db.get_session() as session:
            records = session.query(PersonalRecord).filter(
                PersonalRecord.user_id == self.user_id
            ).all()

            result = {}
            for record in records:
                result[record.record_type] = {
                    'value': record.value,
                    'date': record.date_achieved,
                    'details': record.details or {}
                }

            return result

    def format_records_message(self) -> str:
        """Форматировать сообщение со всеми рекордами"""
        records = self.get_all_records()

        if not records:
            return "🏆 Персональные рекорды\n\nПока нет рекордов. Тренируйся регулярно, и они обязательно появятся!"

        message = "🏆 Твои персональные рекорды:\n\n"

        # Самая длинная пробежка
        if 'longest_run' in records:
            rec = records['longest_run']
            message += f"🏃 {self.RECORD_TYPES['longest_run']}: {rec['value']:.2f} км\n"
            message += f"   Дата: {rec['date'].strftime('%d.%m.%Y')}\n\n"

        # Темп на дистанциях
        pace_types = ['fastest_5k', 'fastest_10k', 'fastest_half_marathon', 'fastest_marathon']
        for rec_type in pace_types:
            if rec_type in records:
                rec = records[rec_type]
                pace = self._seconds_to_pace(rec['value'])
                message += f"⚡️ {self.RECORD_TYPES[rec_type]}: {pace} мин/км\n"
                message += f"   Дата: {rec['date'].strftime('%d.%m.%Y')}\n\n"

        # Недельный объем
        if 'weekly_volume' in records:
            rec = records['weekly_volume']
            message += f"📊 {self.RECORD_TYPES['weekly_volume']}: {rec['value']:.1f} км\n"
            message += f"   Неделя: {rec['date'].strftime('%d.%m.%Y')}\n"

        return message

    @staticmethod
    def _pace_to_seconds(pace_str: str) -> float:
        """Конвертировать темп (мин/км) в секунды"""
        # Формат: "5:30" или "5:30.0"
        parts = pace_str.replace(',', '.').split(':')
        minutes = int(parts[0])
        seconds = float(parts[1]) if len(parts) > 1 else 0
        return minutes * 60 + seconds

    @staticmethod
    def _seconds_to_pace(seconds: float) -> str:
        """Конвертировать секунды в темп (мин/км)"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"


def create_records_manager(user_id: int) -> RecordsManager:
    """Создать менеджер рекордов"""
    return RecordsManager(user_id)
