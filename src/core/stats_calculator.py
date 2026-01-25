"""Расчёт статистики тренировок"""
from datetime import date, timedelta
from typing import Dict, Any, List
from pathlib import Path
import tempfile

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

        # Сводная статистика
        text = f"📊 Статистика за {stats['period']}\n"
        text += f"({stats['start_date'].strftime('%d.%m')} - {stats['end_date'].strftime('%d.%m')})\n\n"

        text += f"🏃 Тренировок: {stats['trainings_count']}\n"
        text += f"📏 Объём: {stats['total_distance']:.1f} км\n"
        text += f"⏱ Время: {stats['total_hours']}ч {stats['total_minutes']}мин\n"

        if stats['avg_hr']:
            text += f"💓 Средний пульс: {int(stats['avg_hr'])} bpm\n"

        # Детали каждой тренировки
        text += f"\n━━━━━━━━━━━━━━━━━━━━\n"
        text += f"\n🏃 Все тренировки:\n\n"

        trainings = stats.get('trainings', [])
        for i, training in enumerate(trainings, 1):
            text += self._format_training_details(training, i)
            text += "\n"

        return text

    def _format_training_details(self, training: Training, number: int) -> str:
        """
        Форматирование деталей тренировки

        Args:
            training: Объект тренировки
            number: Порядковый номер

        Returns:
            Отформатированная строка
        """
        text = f"**{number}. {training.date.strftime('%d.%m.%Y')} ({self._get_day_name(training.date)})**\n"

        # Расстояние
        if training.distance_km:
            text += f"   📏 Расстояние: {training.distance_km:.2f} км\n"

        # Время
        if training.duration_min:
            hours = training.duration_min // 60
            minutes = training.duration_min % 60
            if hours > 0:
                text += f"   ⏱ Время: {hours}ч {minutes}мин\n"
            else:
                text += f"   ⏱ Время: {minutes}мин\n"

        # Темп
        if training.avg_pace:
            text += f"   ⚡️ Темп: {training.avg_pace} мин/км\n"

        # Пульс
        if training.avg_hr:
            text += f"   💓 Средний пульс: {training.avg_hr} bpm\n"

        if training.max_hr:
            text += f"   💓 Макс пульс: {training.max_hr} bpm\n"

        # Набор высоты
        if training.elevation_m and training.elevation_m > 0:
            text += f"   ⛰ Набор высоты: {training.elevation_m} м\n"

        # Тип тренировки (по зонам пульса)
        if training.hr_zones:
            workout_type = self._determine_workout_type(training.hr_zones)
            text += f"   🎯 Тип: {workout_type}\n"

            # Зоны пульса
            text += f"   📈 Зоны пульса: {self._format_hr_zones_compact(training.hr_zones)}\n"

        # Заметки
        if training.notes:
            text += f"   📝 {training.notes}\n"

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


    def generate_weekly_chart(self) -> str:
        """
        Генерация графика за неделю (объём по дням)

        Returns:
            Путь к файлу с графиком
        """
        try:
            import matplotlib
            matplotlib.use('Agg')  # Без GUI
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            # Получаем данные за 4 недели
            end_date = date.today()
            start_date = end_date - timedelta(days=28)
            trainings = self._get_trainings_for_period(start_date, end_date)

            if not trainings:
                return None

            # Группируем по неделям
            weeks_data = {}
            for t in trainings:
                week_start = t.date - timedelta(days=t.date.weekday())
                week_label = week_start.strftime('%d.%m')
                if week_label not in weeks_data:
                    weeks_data[week_label] = {'distance': 0, 'duration': 0, 'count': 0}
                weeks_data[week_label]['distance'] += t.distance_km or 0
                weeks_data[week_label]['duration'] += t.duration_min or 0
                weeks_data[week_label]['count'] += 1

            # Создаём график
            fig, ax = plt.subplots(figsize=(10, 6))

            weeks = list(weeks_data.keys())
            distances = [weeks_data[w]['distance'] for w in weeks]
            counts = [weeks_data[w]['count'] for w in weeks]

            # Столбцы объёма
            bars = ax.bar(weeks, distances, color='#4CAF50', alpha=0.8, label='Объём (км)')

            # Подписи над столбцами
            for bar, dist, cnt in zip(bars, distances, counts):
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{dist:.1f} км\n({cnt} трен.)',
                       ha='center', va='bottom', fontsize=10)

            ax.set_xlabel('Неделя', fontsize=12)
            ax.set_ylabel('Объём (км)', fontsize=12)
            ax.set_title('📊 Объём тренировок по неделям', fontsize=14, fontweight='bold')
            ax.legend()

            plt.tight_layout()

            # Сохраняем
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"График создан: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Ошибка генерации графика: {e}")
            return None

    def generate_hr_zones_chart(self) -> str:
        """
        Генерация графика распределения по зонам пульса

        Returns:
            Путь к файлу с графиком
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Получаем статистику за месяц
            stats = self.get_month_stats()

            if not stats.get('hr_zones'):
                return None

            zones = stats['hr_zones']
            total_time = sum(zones.values())

            if total_time == 0:
                return None

            # Данные для графика
            labels = ['Z1\n(разминка)', 'Z2\n(база)', 'Z3\n(темп)', 'Z4\n(порог)', 'Z5\n(анаэр.)']
            values = [zones.get(f'z{i}', 0) / 60 for i in range(1, 6)]  # в минутах
            colors = ['#81C784', '#4CAF50', '#FFC107', '#FF9800', '#F44336']

            # Создаём график
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

            # Pie chart
            non_zero = [(l, v, c) for l, v, c in zip(labels, values, colors) if v > 0]
            if non_zero:
                pie_labels, pie_values, pie_colors = zip(*non_zero)
                ax1.pie(pie_values, labels=pie_labels, colors=pie_colors, autopct='%1.0f%%',
                       startangle=90, textprops={'fontsize': 10})
                ax1.set_title('Распределение по зонам', fontsize=12, fontweight='bold')

            # Bar chart
            ax2.bar(labels, values, color=colors, alpha=0.8)
            ax2.set_ylabel('Время (мин)', fontsize=11)
            ax2.set_title('Время в каждой зоне', fontsize=12, fontweight='bold')

            # Подписи
            for i, v in enumerate(values):
                if v > 0:
                    ax2.text(i, v + 1, f'{int(v)} мин', ha='center', fontsize=9)

            fig.suptitle('💓 Анализ пульсовых зон (месяц)', fontsize=14, fontweight='bold')
            plt.tight_layout()

            # Сохраняем
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
            plt.close()

            logger.info(f"HR zones график создан: {temp_file.name}")
            return temp_file.name

        except Exception as e:
            logger.error(f"Ошибка генерации HR графика: {e}")
            return None

    def generate_progress_chart(self) -> str:
        """
        Генерация графика прогресса (объём по месяцам)

        Returns:
            Путь к файлу с графиком
        """
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt

            # Получаем данные за 3 месяца
            end_date = date.today()
            start_date = end_date - timedelta(days=90)
            trainings = self._get_trainings_for_period(start_date, end_date)

            if len(trainings) < 3:
                return None

            # Группируем по месяцам
            months_data = {}
            for t in trainings:
                month_key = t.date.strftime('%Y-%m')
                month_label = t.date.strftime('%B')[:3]
                if month_key not in months_data:
                    months_data[month_key] = {'label': month_label, 'distance': 0, 'time': 0}
                months_data[month_key]['distance'] += t.distance_km or 0
                months_data[month_key]['time'] += t.duration_min or 0

            # Создаём график
            fig, ax1 = plt.subplots(figsize=(10, 6))

            months = list(months_data.keys())
            labels = [months_data[m]['label'] for m in months]
            distances = [months_data[m]['distance'] for m in months]
            times = [months_data[m]['time'] / 60 for m in months]  # в часах

            # Линия объёма
            color1 = '#4CAF50'
            ax1.bar(labels, distances, color=color1, alpha=0.7, label='Объём (км)')
            ax1.set_xlabel('Месяц', fontsize=12)
            ax1.set_ylabel('Объём (км)', color=color1, fontsize=12)
            ax1.tick_params(axis='y', labelcolor=color1)

            # Вторая ось - время
            ax2 = ax1.twinx()
            color2 = '#2196F3'
            ax2.plot(labels, times, color=color2, marker='o', linewidth=2, markersize=8, label='Время (ч)')
            ax2.set_ylabel('Время (ч)', color=color2, fontsize=12)
            ax2.tick_params(axis='y', labelcolor=color2)

            fig.suptitle('📈 Прогресс тренировок', fontsize=14, fontweight='bold')
            fig.legend(loc='upper left', bbox_to_anchor=(0.1, 0.9))
            plt.tight_layout()

            # Сохраняем
            temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
            plt.savefig(temp_file.name, dpi=150, bbox_inches='tight')
            plt.close()

            return temp_file.name

        except Exception as e:
            logger.error(f"Ошибка генерации progress графика: {e}")
            return None


def create_stats_calculator(user_id: int) -> StatsCalculator:
    """Создать калькулятор статистики"""
    return StatsCalculator(user_id)
