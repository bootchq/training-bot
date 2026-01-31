"""Расчёт статистики тренировок"""
from datetime import date
from datetime import timedelta
from typing import Any
from typing import Dict
from typing import List

from ..database.db import Training
from ..database.db import db


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

            # Загружаем все атрибуты
            for training in trainings:
                _ = (training.id, training.date, training.distance_km,
                     training.duration_min, training.avg_hr, training.hr_zones,
                     training.avg_pace, training.max_hr, training.elevation_m, training.notes)

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

    def format_week_stats_separate(self, stats: Dict[str, Any]) -> List[str]:
        """
        Форматирование статистики за неделю (каждая тренировка отдельным сообщением).

        Args:
            stats: Словарь со статистикой

        Returns:
            Список строк (каждая строка = отдельное сообщение)
        """
        if stats['trainings_count'] == 0:
            return ["📊 Статистика за неделю\n\n❌ Нет тренировок за последние 7 дней"]

        messages = []

        # Первое сообщение - заголовок
        header = "📊 Статистика за неделю\n"
        header += f"({stats['start_date'].strftime('%d.%m')} - {stats['end_date'].strftime('%d.%m')})\n\n"
        header += f"🏃 Тренировок: {stats['trainings_count']}\n"
        header += f"📏 Объём: {stats['total_distance']:.1f} км\n"
        header += f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n"

        if stats['avg_hr']:
            header += f"💓 Средний пульс: {int(stats['avg_hr'])} bpm"

        messages.append(header)

        # Каждая тренировка отдельным сообщением
        trainings = stats.get('trainings', [])
        for i, training in enumerate(trainings, 1):
            msg = f"🏃 **Тренировка {i} из {len(trainings)}**\n\n"
            msg += self._format_training_details(training, 0)  # 0 чтобы не добавлять номер
            messages.append(msg)

        return messages

    def _format_training_details(self, training: Training, number: int = 0) -> str:
        """
        Форматирование деталей тренировки

        Args:
            training: Объект тренировки
            number: Порядковый номер (0 = без номера)

        Returns:
            Отформатированная строка
        """
        if number > 0:
            text = f"**{number}. {training.date.strftime('%d.%m.%Y')} ({self._get_day_name(training.date)})**\n"
        else:
            text = f"**{training.date.strftime('%d.%m.%Y')} ({self._get_day_name(training.date)})**\n"

        # Расстояние
        if training.distance_km:
            text += f"📏 Расстояние: {training.distance_km:.2f} км\n"

        # Время
        if training.duration_min:
            hours = training.duration_min // 60
            minutes = training.duration_min % 60
            if hours > 0:
                text += f"⏱ Время: {hours}ч {minutes}мин\n"
            else:
                text += f"⏱ Время: {minutes}мин\n"

        # Темп
        if training.avg_pace:
            text += f"⚡️ Темп: {training.avg_pace} мин/км\n"

        # Пульс
        if training.avg_hr:
            text += f"💓 Средний пульс: {training.avg_hr} bpm\n"

        if training.max_hr:
            text += f"💓 Макс пульс: {training.max_hr} bpm\n"

        # Набор высоты
        if training.elevation_m and training.elevation_m > 0:
            text += f"⛰ Набор высоты: {training.elevation_m} м\n"

        # Тип тренировки (по зонам пульса)
        if training.hr_zones:
            workout_type = self._determine_workout_type(training.hr_zones)
            text += f"🎯 Тип: {workout_type}\n"

            # Зоны пульса
            text += f"📈 Зоны пульса: {self._format_hr_zones_compact(training.hr_zones)}\n"

        # Заметки
        if training.notes:
            text += f"📝 {training.notes}\n"

        return text

    def _get_day_name(self, date_obj: date) -> str:
        """Получить название дня недели"""
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        return days[date_obj.weekday()]

    def _determine_workout_type(self, hr_zones: Dict[str, int]) -> str:
        """
        Определить тип тренировки по зонам пульса

        Args:
            hr_zones: Словарь с временем в зонах

        Returns:
            Название типа тренировки
        """
        if not hr_zones:
            return "Неизвестно"

        total_time = sum(hr_zones.values())
        if total_time == 0:
            return "Неизвестно"

        # Процент времени в каждой зоне
        z1_z2_percent = (hr_zones.get('z1', 0) + hr_zones.get('z2', 0)) / total_time * 100
        z3_z4_percent = (hr_zones.get('z3', 0) + hr_zones.get('z4', 0)) / total_time * 100
        z5_percent = hr_zones.get('z5', 0) / total_time * 100

        if z5_percent > 10:
            return "Анаэробная (спринт)"
        elif z3_z4_percent > 50:
            return "Пороговая / Интенсивная"
        elif z1_z2_percent > 70:
            return "Аэробная (база)"
        else:
            return "Смешанная"

    def _format_hr_zones_compact(self, hr_zones: Dict[str, int]) -> str:
        """
        Компактное форматирование зон пульса

        Args:
            hr_zones: Словарь с временем в зонах

        Returns:
            Строка вида "Z1: 20мин (40%), Z2: 30мин (60%)"
        """
        if not hr_zones:
            return "Нет данных"

        total_time = sum(hr_zones.values())
        if total_time == 0:
            return "Нет данных"

        parts = []
        for zone in ['z1', 'z2', 'z3', 'z4', 'z5']:
            seconds = hr_zones.get(zone, 0)
            if seconds > 0:
                minutes = seconds // 60
                percent = (seconds / total_time) * 100
                zone_num = zone.upper()
                parts.append(f"{zone_num}: {minutes}мин ({percent:.0f}%)")

        return ", ".join(parts) if parts else "Нет данных"

    def format_month_stats_summary(self, stats: Dict[str, Any]) -> str:
        """
        Форматирование статистики за месяц (только общая информация).

        Args:
            stats: Словарь со статистикой

        Returns:
            Отформатированная строка
        """
        if stats['trainings_count'] == 0:
            return "📊 Статистика за месяц\n\n❌ Нет тренировок за последние 30 дней"

        text = "📊 Статистика за месяц\n"
        text += f"({stats['start_date'].strftime('%d.%m')} - {stats['end_date'].strftime('%d.%m')})\n\n"

        text += f"🏃 Тренировок: {stats['trainings_count']}\n"
        text += f"📏 Объём: {stats['total_distance']:.1f} км\n"
        text += f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n"

        if stats['avg_hr']:
            text += f"💓 Средний пульс: {int(stats['avg_hr'])} bpm\n"

        return text

    def format_combined_stats(self, stats: Dict[str, Any], period: str = "week") -> str:
        """
        Объединённая статистика: километраж + прогресс + тренды

        Args:
            stats: Словарь со статистикой текущего периода
            period: Период ("week" или "month")

        Returns:
            Отформатированная строка
        """
        if stats['trainings_count'] == 0:
            period_ru = "неделю" if period == "week" else "месяц"
            return f"📊 Статистика\n\n❌ Нет тренировок за {period_ru}"

        period_ru = "Неделя" if period == "week" else "Месяц"
        text = "📊 Статистика\n\n"
        text += f"**[{period_ru}]**\n"
        text += f"({stats['start_date'].strftime('%d.%m')} - {stats['end_date'].strftime('%d.%m')})\n\n"

        # Километраж
        text += f"📏 Километраж: **{stats['total_distance']:.1f} км**\n"
        text += f"🏃 Тренировок: {stats['trainings_count']}\n"
        text += f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n\n"

        # Прогресс к цели
        progress_text = self._calculate_goal_progress(stats)
        if progress_text:
            text += progress_text + "\n"

        # Тренды (сравнение с предыдущим периодом)
        trends_text = self._calculate_trends(stats, period)
        if trends_text:
            text += "**Тренды:**\n" + trends_text

        return text

    def _calculate_goal_progress(self, stats: Dict[str, Any]) -> str:
        """
        Рассчитать прогресс к цели

        Args:
            stats: Словарь со статистикой

        Returns:
            Строка с прогрессом или пустая строка
        """
        user = db.get_user_by_id(self.user_id)
        if not user or not user.goal_distance_km or not user.goal_date:
            return ""

        goal_distance = user.goal_distance_km
        goal_date = user.goal_date
        today = date.today()

        # Сколько дней осталось
        days_left = (goal_date - today).days
        if days_left < 0:
            return ""  # Цель уже прошла

        # Прогресс за последние 30 дней
        month_start = today - timedelta(days=30)
        monthly_stats = self._calculate_stats(month_start, today, "месяц")
        current_volume = monthly_stats['total_distance']

        # Рекомендуемый объём для подготовки (примерно 40% от дистанции забега в месяц)
        recommended_monthly = goal_distance * 0.4

        # Процент выполнения
        progress_percent = min(100, int((current_volume / recommended_monthly) * 100)) if recommended_monthly > 0 else 0

        # Progress bar
        filled = int(progress_percent / 10)
        bar = "█" * filled + "░" * (10 - filled)

        text = f"**Прогресс к цели:** {goal_distance}км ({goal_date.strftime('%d.%m.%Y')})\n"
        text += f"{bar} {progress_percent}%\n"
        text += f"Объём за 30 дней: {current_volume:.1f}/{recommended_monthly:.0f} км\n"
        text += f"До старта: {days_left} дней\n"

        return text

    def _calculate_trends(self, current_stats: Dict[str, Any], period: str) -> str:
        """
        Рассчитать тренды (сравнение с предыдущим периодом)

        Args:
            current_stats: Статистика текущего периода
            period: Период ("week" или "month")

        Returns:
            Строка с трендами или пустая строка
        """
        if current_stats['trainings_count'] == 0:
            return ""

        # Получаем предыдущий период
        if period == "week":
            prev_end = current_stats['start_date'] - timedelta(days=1)
            prev_start = prev_end - timedelta(days=7)
        else:  # month
            prev_end = current_stats['start_date'] - timedelta(days=1)
            prev_start = prev_end - timedelta(days=30)

        prev_stats = self._calculate_stats(prev_start, prev_end, "предыдущий")

        if prev_stats['trainings_count'] == 0:
            return ""  # Нет данных для сравнения

        text = ""

        # Средний темп
        current_pace = self._calculate_avg_pace(current_stats['trainings'])
        prev_pace = self._calculate_avg_pace(prev_stats['trainings'])

        if current_pace and prev_pace:
            pace_diff_seconds = self._pace_to_seconds(current_pace) - self._pace_to_seconds(prev_pace)
            pace_emoji = "↗️" if pace_diff_seconds < 0 else "↘️"
            pace_sign = "-" if pace_diff_seconds < 0 else "+"
            text += f"  ⚡ Темп: {prev_pace} → {current_pace} ({pace_sign}{abs(pace_diff_seconds)}сек/км) {pace_emoji}\n"

        # Средний пульс
        if current_stats['avg_hr'] and prev_stats['avg_hr']:
            hr_diff = int(current_stats['avg_hr']) - int(prev_stats['avg_hr'])
            hr_emoji = "↘️" if hr_diff < 0 else "↗️"
            hr_sign = "" if hr_diff < 0 else "+"
            text += f"  💓 Ср. пульс: {int(prev_stats['avg_hr'])} → {int(current_stats['avg_hr'])} ({hr_sign}{hr_diff}) {hr_emoji}\n"

        # Калории (примерная оценка: 65 ккал на км)
        current_calories = int(current_stats['total_distance'] * 65)
        prev_calories = int(prev_stats['total_distance'] * 65)
        text += f"  🔥 Калории: {current_calories} ккал\n"

        return text

    def _calculate_avg_pace(self, trainings: List[Training]) -> str:
        """
        Рассчитать средний темп

        Args:
            trainings: Список тренировок

        Returns:
            Средний темп в формате "5:30" или None
        """
        pace_seconds_list = []
        for t in trainings:
            if t.avg_pace:
                pace_seconds_list.append(self._pace_to_seconds(t.avg_pace))

        if not pace_seconds_list:
            return None

        avg_seconds = sum(pace_seconds_list) / len(pace_seconds_list)
        minutes = int(avg_seconds // 60)
        seconds = int(avg_seconds % 60)
        return f"{minutes}:{seconds:02d}"

    def _pace_to_seconds(self, pace_str: str) -> float:
        """
        Конвертировать темп из строки в секунды

        Args:
            pace_str: Темп в формате "5:30"

        Returns:
            Темп в секундах
        """
        try:
            parts = pace_str.split(':')
            return int(parts[0]) * 60 + int(parts[1])
        except Exception:
            return 0.0


def create_stats_calculator(user_id: int) -> StatsCalculator:
    """Создать калькулятор статистики"""
    return StatsCalculator(user_id)
