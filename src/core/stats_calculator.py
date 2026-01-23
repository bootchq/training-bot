"""Расчёт статистики тренировок"""
from datetime import date, timedelta
from typing import Dict, Any, List

from ..database.db import db, Training
from ..utils.logger import logger


class StatsCalculator:
    """Калькулятор статистики"""

    def __init__(self, user_id: int):
        """
        Инициализация

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id

    def get_week_stats(self, end_date: date = None) -> Dict[str, Any]:
        """
        Статистика за неделю

        Args:
            end_date: Конец недели (по умолчанию - сегодня)

        Returns:
            Словарь со статистикой
        """
        if not end_date:
            end_date = date.today()

        start_date = end_date - timedelta(days=7)

        return self._calculate_stats(start_date, end_date, period_name="неделю")

    def get_month_stats(self, end_date: date = None) -> Dict[str, Any]:
        """
        Статистика за месяц

        Args:
            end_date: Конец периода (по умолчанию - сегодня)

        Returns:
            Словарь со статистикой
        """
        if not end_date:
            end_date = date.today()

        start_date = end_date - timedelta(days=30)

        return self._calculate_stats(start_date, end_date, period_name="месяц")

    def _calculate_stats(self, start_date: date, end_date: date, period_name: str) -> Dict[str, Any]:
        """
        Расчёт статистики за период

        Args:
            start_date: Начало периода
            end_date: Конец периода
            period_name: Название периода для отчёта

        Returns:
            Словарь со статистикой
        """
        # Получаем тренировки за период
        trainings = self._get_trainings_for_period(start_date, end_date)

        if not trainings:
            return {
                'period': period_name,
                'trainings_count': 0,
                'total_distance': 0,
                'total_duration': 0,
                'message': f"Нет тренировок за {period_name}"
            }

        # Расчёты
        total_distance = sum(t.distance_km or 0 for t in trainings)
        total_duration = sum(t.duration_min or 0 for t in trainings)
        avg_hr_list = [t.avg_hr for t in trainings if t.avg_hr]
        avg_hr = sum(avg_hr_list) / len(avg_hr_list) if avg_hr_list else None

        # Зоны пульса
        hr_zones_total = self._aggregate_hr_zones(trainings)

        # Форматирование
        total_hours = total_duration // 60
        total_minutes = total_duration % 60

        return {
            'period': period_name,
            'start_date': start_date,
            'end_date': end_date,
            'trainings_count': len(trainings),
            'total_distance': total_distance,
            'total_duration': total_duration,
            'total_hours': total_hours,
            'total_minutes': total_minutes,
            'avg_hr': avg_hr,
            'hr_zones': hr_zones_total,
            'trainings': trainings
        }

    def _get_trainings_for_period(self, start_date: date, end_date: date) -> List[Training]:
        """Получить тренировки за период"""
        with db.get_session() as session:
            trainings = session.query(Training).filter(
                Training.user_id == self.user_id,
                Training.date >= start_date,
                Training.date <= end_date,
                Training.type == 'actual'
            ).order_by(Training.date).all()

            # Загружаем атрибуты
            for training in trainings:
                _ = (training.id, training.date, training.distance_km,
                     training.duration_min, training.avg_hr, training.hr_zones)

            session.expunge_all()
            return trainings

    def _aggregate_hr_zones(self, trainings: List[Training]) -> Dict[str, int]:
        """
        Суммирование времени в зонах пульса

        Args:
            trainings: Список тренировок

        Returns:
            Словарь {z1: секунды, z2: секунды, ...}
        """
        zones_total = {'z1': 0, 'z2': 0, 'z3': 0, 'z4': 0, 'z5': 0}

        for training in trainings:
            if training.hr_zones:
                for zone, seconds in training.hr_zones.items():
                    if zone in zones_total:
                        zones_total[zone] += seconds

        return zones_total

    def format_stats(self, stats: Dict[str, Any]) -> str:
        """
        Форматирование статистики для вывода

        Args:
            stats: Словарь со статистикой

        Returns:
            Отформатированная строка
        """
        if stats['trainings_count'] == 0:
            return f"📊 Статистика за {stats['period']}\n\n{stats['message']}"

        text = f"📊 Статистика за {stats['period']}\n"
        text += f"({stats['start_date'].strftime('%d.%m')} - {stats['end_date'].strftime('%d.%m')})\n\n"

        # Основная статистика
        text += f"🏃 Тренировок: {stats['trainings_count']}\n"
        text += f"📏 Объём: {stats['total_distance']:.1f} км\n"
        text += f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n"

        if stats['avg_hr']:
            text += f"💓 Средний пульс: {int(stats['avg_hr'])} bpm\n"

        # Зоны пульса (если есть данные)
        hr_zones = stats['hr_zones']
        total_hr_time = sum(hr_zones.values())

        if total_hr_time > 0:
            text += f"\n📈 Зоны пульса:\n"

            zone_names = {
                'z1': 'Z1 (восстановление)',
                'z2': 'Z2 (аэробная)',
                'z3': 'Z3 (пороговая)',
                'z4': 'Z4 (VO2max)',
                'z5': 'Z5 (спринт)'
            }

            for zone in ['z1', 'z2', 'z3', 'z4', 'z5']:
                seconds = hr_zones.get(zone, 0)
                if seconds > 0:
                    minutes = seconds // 60
                    percent = (seconds / total_hr_time) * 100
                    text += f"   {zone_names[zone]}: {minutes}мин ({percent:.0f}%)\n"

        # Прогресс к целям
        text += self._format_goals_progress()

        return text

    def _format_goals_progress(self) -> str:
        """Форматирование прогресса к целям"""
        today = date.today()

        goals = [
            {'name': 'Тарки-Тау 50км', 'date': date(2026, 2, 15), 'distance': 50},
            {'name': 'Марафон 42км', 'date': date(2026, 3, 15), 'distance': 42},
            {'name': 'DWT 65км', 'date': date(2026, 4, 15), 'distance': 65}
        ]

        text = "\n🎯 До забегов:\n"

        for goal in goals:
            if goal['date'] >= today:
                days_left = (goal['date'] - today).days
                text += f"   {goal['name']}: {days_left} дней\n"

        return text


def create_stats_calculator(user_id: int) -> StatsCalculator:
    """Создать калькулятор статистики"""
    return StatsCalculator(user_id)
