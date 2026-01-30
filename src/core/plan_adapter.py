"""Адаптация плана тренировок"""
from datetime import date, timedelta
from typing import Optional, Dict, Any, List

from ..database.db import db, Training, TrainingPlan, WellnessSurvey
from ..utils.logger import logger


class PlanAdapter:
    """Адаптация плана на основе фактических тренировок"""

    def __init__(self, user_id: int):
        """
        Инициализация адаптера

        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id

    def analyze_day(self, target_date: date) -> Dict[str, Any]:
        """
        Анализ выполнения тренировки за день

        Args:
            target_date: Дата для анализа

        Returns:
            Словарь с результатами анализа
        """
        # Получаем план на день
        plan = db.get_plan_for_date(self.user_id, target_date)

        # Получаем факт из БД (тренировки за день)
        actual = db.get_training_for_date(self.user_id, target_date)

        if not plan:
            return {
                'status': 'no_plan',
                'message': f'Нет плана на {target_date}',
                'plan': None,
                'actual': actual
            }

        # Статус выполнения
        if not actual:
            status = 'skipped'
            message = f'Тренировка пропущена: {plan.type}, {plan.duration_min} мин'
        else:
            # Сравниваем факт с планом
            comparison = self._compare_training(plan, actual)
            status = comparison['status']
            message = comparison['message']

        return {
            'status': status,
            'message': message,
            'plan': plan,
            'actual': actual
        }

    def _compare_training(self, plan: TrainingPlan, actual: Training) -> Dict[str, str]:
        """
        Сравнение планового и фактического выполнения

        Args:
            plan: Плановая тренировка
            actual: Фактическая тренировка

        Returns:
            Статус и сообщение
        """
        # Если нет данных о расстоянии - сравниваем по длительности
        if plan.distance_km and actual.distance_km:
            ratio = actual.distance_km / plan.distance_km

            if ratio > 1.5:
                return {
                    'status': 'overperformed',
                    'message': f'Перевыполнение: {actual.distance_km:.1f}км вместо {plan.distance_km:.1f}км ({ratio*100:.0f}%)'
                }
            elif ratio < 0.7:
                return {
                    'status': 'underperformed',
                    'message': f'Недовыполнение: {actual.distance_km:.1f}км вместо {plan.distance_km:.1f}км ({ratio*100:.0f}%)'
                }

        # Проверка пульса (если была лёгкая, но пульс высокий)
        if plan.type == 'easy' and actual.avg_hr:
            # Грубая оценка: >z3 это примерно >88% от max (предполагаем max=190)
            if actual.avg_hr > 167:  # ~88% от 190
                return {
                    'status': 'high_hr',
                    'message': f'Высокий пульс на лёгкой: {actual.avg_hr} bpm (норма до z2)'
                }

        return {
            'status': 'completed',
            'message': f'Выполнено: {actual.distance_km:.1f}км за {actual.duration_min}мин'
        }

    def adapt_on_skip(self, skip_date: date) -> List[str]:
        """
        Адаптация при пропуске тренировки

        Best practice: 1-2 пропуска - без изменений, 3+ - перераспределение 50-75% объема
        Источник: trainright.com/missed-workouts-guide-to-adjusting-training

        Args:
            skip_date: Дата пропущенной тренировки

        Returns:
            Список изменений
        """
        changes = []

        # Считаем количество пропусков подряд
        consecutive_skips = self._count_consecutive_skips(skip_date)

        logger.info(f"Пропусков подряд: {consecutive_skips}")

        if consecutive_skips <= 2:
            # 1-2 пропуска - без адаптации (best practice)
            # Один пропуск не критичен, просто продолжаем план
            logger.info("1-2 пропуска - план не меняется (best practice)")
            return []

        elif consecutive_skips >= 3:
            # 3+ пропуска - перераспределяем 50-75% объема на 4-6 недель
            # Приоритет важным тренировкам (темповые, интервалы, длинные)
            logger.info("3+ пропуска - перераспределяем объем (best practice)")

            # Получаем пропущенные тренировки
            missed_trainings = self._get_missed_trainings(skip_date, consecutive_skips)

            # Перераспределяем приоритетные тренировки (60% объема)
            for missed in missed_trainings:
                if missed.type in ['tempo', 'intervals', 'long']:
                    # Важные тренировки - перераспределяем больший %
                    change = self._redistribute_volume(missed.date, percentage=0.6)
                    if change:
                        changes.append(change)
                elif missed.type == 'easy':
                    # Лёгкие тренировки - меньший % (50%)
                    change = self._redistribute_volume(missed.date, percentage=0.5)
                    if change:
                        changes.append(change)

        return changes

    def adapt_on_overperformance(self, overperf_date: date) -> List[str]:
        """
        Адаптация при перевыполнении

        Args:
            overperf_date: Дата перевыполненной тренировки

        Returns:
            Список изменений
        """
        changes = []

        # Следующая тренировка должна быть легче
        next_training = self._get_next_training(overperf_date)

        if next_training and next_training.type != 'easy':
            # Меняем на лёгкую
            change = db.update_training_plan(
                next_training.id,
                type='easy',
                description=f"[АДАПТИРОВАНО] Восстановление после перевыполнения. Было: {next_training.type}"
            )
            changes.append(f"Следующая тренировка изменена на лёгкую (восстановление)")

        return changes

    def adapt_on_wellness(
        self,
        wellness_date: date,
        training_rating: int = 5,
        wellness_rating: int = 2,
        sleep_quality: str = 'ok',
        pain_reported: bool = False
    ) -> List[str]:
        """
        Адаптация по самочувствию с объяснением причины

        Args:
            wellness_date: Дата опроса
            training_rating: Оценка тренировки (1-10)
            wellness_rating: Самочувствие (1=усталость, 2=норма, 3=отлично)
            sleep_quality: Качество сна (bad/ok/good)
            pain_reported: Есть ли боль

        Returns:
            Список изменений с причинами
        """
        changes = []
        reasons = []
        total_reduction = 0

        next_training = self._get_next_training(wellness_date)
        if not next_training:
            return changes

        # 1. Плохой сон — главный фактор восстановления
        if sleep_quality == 'bad':
            total_reduction += 0.20
            reasons.append("плохой сон")
            logger.info(f"Wellness: плохой сон -> -20%")

        # 2. Усталость (wellness_rating=1)
        if wellness_rating == 1:
            total_reduction += 0.15
            reasons.append("усталость")
            logger.info(f"Wellness: усталость -> -15%")

        # 3. Боль — серьёзный сигнал
        if pain_reported:
            total_reduction += 0.25
            reasons.append("боль/дискомфорт")
            logger.info(f"Wellness: боль -> -25%")

        # 4. Плохая оценка тренировки (<=4)
        if training_rating <= 4:
            total_reduction += 0.10
            reasons.append(f"тяжёлая тренировка ({training_rating}/10)")
            logger.info(f"Wellness: низкая оценка {training_rating} -> -10%")

        # Применяем адаптацию
        if total_reduction >= 0.40:
            # Критично: меняем на лёгкую или отдых
            if next_training.type in ['tempo', 'intervals', 'long']:
                reason_text = ", ".join(reasons)
                db.update_training_plan(
                    next_training.id,
                    type='easy',
                    description=f"[АДАПТИРОВАНО] Заменено на лёгкую ({reason_text}). Было: {next_training.type}"
                )
                changes.append(f"Заменил {next_training.type} на лёгкую — {reason_text}")
            else:
                self._reduce_training(next_training, reduction=0.30)
                changes.append(f"Снизил нагрузку на 30% — {', '.join(reasons)}")

        elif total_reduction >= 0.20:
            # Умеренно: снижаем на 20%
            reason_text = ", ".join(reasons)
            self._reduce_training(next_training, reduction=0.20)
            changes.append(f"Снизил нагрузку на 20% — {reason_text}")

        elif total_reduction >= 0.10:
            # Немного: снижаем на 10%
            reason_text = ", ".join(reasons)
            self._reduce_training(next_training, reduction=0.10)
            changes.append(f"Снизил нагрузку на 10% — {reason_text}")

        # Отличное самочувствие — можно добавить
        if (wellness_rating == 3 and sleep_quality == 'good' and
            training_rating >= 8 and not pain_reported):
            if next_training.type not in ['easy', 'recovery', 'long']:
                self._increase_training(next_training, increase=0.10)
                changes.append("Увеличил нагрузку на 10% — отличное восстановление")

        return changes

    def _count_consecutive_skips(self, from_date: date) -> int:
        """Подсчёт пропусков подряд до указанной даты"""
        count = 0
        current_date = from_date

        for _ in range(7):  # Проверяем максимум 7 дней назад
            plan = db.get_plan_for_date(self.user_id, current_date)
            actual = db.get_training_for_date(self.user_id, current_date)

            if plan and not actual:
                count += 1
                current_date -= timedelta(days=1)
            else:
                break

        return count

    def _get_missed_trainings(self, from_date: date, count: int) -> List[TrainingPlan]:
        """
        Получить список пропущенных тренировок

        Args:
            from_date: Дата последнего пропуска
            count: Количество пропусков

        Returns:
            Список пропущенных тренировок
        """
        missed = []
        current_date = from_date

        for _ in range(count):
            plan = db.get_plan_for_date(self.user_id, current_date)
            if plan:
                missed.append(plan)
            current_date -= timedelta(days=1)

        return missed

    def _redistribute_volume(self, skip_date: date, percentage: float = 0.5) -> Optional[str]:
        """
        Перераспределение объёма после пропуска

        Args:
            skip_date: Дата пропущенной тренировки
            percentage: Процент объема для перераспределения (0.5 = 50%, 0.6 = 60%)

        Returns:
            Описание изменения
        """
        # Получаем пропущенную тренировку
        skipped = db.get_plan_for_date(self.user_id, skip_date)

        if not skipped:
            return None

        # Находим следующую аналогичную тренировку (в пределах 4-6 недель)
        next_similar = self._find_next_similar_training(skip_date, skipped.type)

        if not next_similar:
            return None

        # Перераспределяем по расстоянию или по длительности
        if skipped.distance_km:
            # Добавляем процент от пропущенного объёма
            additional_km = skipped.distance_km * percentage
            new_distance = (next_similar.distance_km or 0) + additional_km

            db.update_training_plan(
                next_similar.id,
                distance_km=new_distance,
                description=f"[АДАПТИРОВАНО] +{additional_km:.1f}км ({int(percentage*100)}%) от пропущенной {skip_date.strftime('%d.%m')}"
            )

            return f"Объём {additional_km:.1f}км перераспределён на {next_similar.date.strftime('%d.%m')}"

        elif skipped.duration_min:
            # Добавляем процент от пропущенной длительности
            additional_min = int(skipped.duration_min * percentage)
            new_duration = (next_similar.duration_min or 0) + additional_min

            db.update_training_plan(
                next_similar.id,
                duration_min=new_duration,
                description=f"[АДАПТИРОВАНО] +{additional_min}мин ({int(percentage*100)}%) от пропущенной {skip_date.strftime('%d.%m')}"
            )

            return f"Длительность +{additional_min}мин перераспределена на {next_similar.date.strftime('%d.%m')}"

        return None

    def _reduce_intensity(self, from_date: date, reduction: float) -> Optional[str]:
        """
        Снижение интенсивности будущих тренировок

        Args:
            from_date: Начиная с какой даты
            reduction: Коэффициент снижения (0.1 = 10%)

        Returns:
            Описание изменения
        """
        # Получаем тренировки на следующие 2 недели
        future_trainings = db.get_plan_for_period(
            self.user_id,
            from_date + timedelta(days=1),
            from_date + timedelta(days=14)
        )

        count = 0
        for training in future_trainings:
            if training.type in ['tempo', 'intervals']:
                # Снижаем длительность на reduction%
                if training.duration_min:
                    new_duration = int(training.duration_min * (1 - reduction))
                    db.update_training_plan(
                        training.id,
                        duration_min=new_duration,
                        description=f"[АДАПТИРОВАНО] Снижено на {reduction*100:.0f}% из-за пропусков"
                    )
                    count += 1

        if count > 0:
            return f"Снижена интенсивность {count} тренировок на {reduction*100:.0f}%"

        return None

    def _get_next_training(self, from_date: date) -> Optional[TrainingPlan]:
        """Получить следующую тренировку после указанной даты"""
        future = db.get_plan_for_period(
            self.user_id,
            from_date + timedelta(days=1),
            from_date + timedelta(days=7)
        )

        if future:
            return future[0]

        return None

    def _find_next_similar_training(self, from_date: date, training_type: str) -> Optional[TrainingPlan]:
        """Найти следующую тренировку того же типа"""
        future = db.get_plan_for_period(
            self.user_id,
            from_date + timedelta(days=1),
            from_date + timedelta(days=21)
        )

        for training in future:
            if training.type == training_type:
                return training

        return None

    def _reduce_training(self, training: TrainingPlan, reduction: float) -> bool:
        """Снизить нагрузку тренировки"""
        updates = {}

        if training.duration_min:
            updates['duration_min'] = int(training.duration_min * (1 - reduction))

        if training.distance_km:
            updates['distance_km'] = training.distance_km * (1 - reduction)

        updates['description'] = f"[АДАПТИРОВАНО] Снижено на {reduction*100:.0f}% по самочувствию"

        db.update_training_plan(training.id, **updates)
        return True

    def _increase_training(self, training: TrainingPlan, increase: float) -> bool:
        """Увеличить нагрузку тренировки"""
        # Не увеличиваем длинные тренировки и восстановительные
        if training.type in ['long', 'easy']:
            return False

        updates = {}

        if training.duration_min:
            updates['duration_min'] = int(training.duration_min * (1 + increase))

        if training.distance_km:
            updates['distance_km'] = training.distance_km * (1 + increase)

        updates['description'] = f"[АДАПТИРОВАНО] Увеличено на {increase*100:.0f}% (хорошее самочувствие)"

        db.update_training_plan(training.id, **updates)
        return True


# Глобальный экземпляр для удобства
def create_adapter(user_id: int) -> PlanAdapter:
    """Создать адаптер для пользователя"""
    return PlanAdapter(user_id)
