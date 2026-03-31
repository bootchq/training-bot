"""SmartAdvisor — умная рекомендация тренировки на основе плана vs факта"""
from datetime import date, timedelta
from typing import Dict, Any

from ..database.db import db
from ..ai.recovery_detector import recovery_detector
from ..utils.logger import logger
from ..utils import time_utils
from .groq_client import get_groq_client, MODEL_MAIN


class SmartAdvisor:
    """Умный советник: анализирует план vs факт за 3 недели и рекомендует лучшую тренировку"""

    def __init__(self):
        self.client = get_groq_client()
        self.model = MODEL_MAIN

    def get_smart_recommendation(self, user_id: int) -> Dict[str, Any]:
        """
        Главный метод: анализирует 3 недели и рекомендует тренировку на сегодня.

        Returns:
            {
                'workout_type': str,
                'duration_min': int,
                'distance_km': float,
                'target_zone': str,
                'description': str,
                'reasoning': str,
                'plan_status': dict,
                'recovery_status': str,
            }
        """
        # 1. Собираем контекст
        context = self._build_context(user_id)

        # 2. Rule-based рекомендация
        rule_rec = self._rule_based_recommendation(context)

        # 3. AI enrichment (если доступен)
        if self.client:
            try:
                ai_rec = self._ai_enrichment(context, rule_rec)
                ai_rec['plan_status'] = context['plan_status']
                ai_rec['recovery_status'] = context['recovery']['status']
                return ai_rec
            except Exception as e:
                logger.error(f"SmartAdvisor AI ошибка: {e}")

        # Fallback на rule-based
        rule_rec['plan_status'] = context['plan_status']
        rule_rec['recovery_status'] = context['recovery']['status']
        return rule_rec

    def _build_context(self, user_id: int) -> Dict[str, Any]:
        """Собрать полный контекст за 21 день"""
        today = time_utils.today()
        three_weeks_ago = today - timedelta(days=21)

        # Профиль
        settings = db.get_user_settings(user_id)

        # План за 3 недели
        planned = db.get_plan_for_period(user_id, three_weeks_ago, today)

        # Факт за 3 недели
        actual = db.get_trainings_for_period(user_id, three_weeks_ago, today)

        # Recovery
        recovery = recovery_detector.detect_recovery_status(user_id)

        # Анализ план vs факт
        plan_status = self._analyze_plan_vs_actual(planned, actual, today)

        # Последняя тренировка
        latest = db.get_latest_training(user_id)
        last_training_info = None
        if latest and latest.date:
            days_since = (today - latest.date).days
            last_training_info = {
                'date': latest.date,
                'days_ago': days_since,
                'type': latest.type,
                'distance_km': latest.distance_km or 0,
                'duration_min': latest.duration_min or 0,
                'avg_hr': latest.avg_hr,
            }

        # План на сегодня
        todays_plan = db.get_plan_for_date(user_id, today)

        return {
            'user_id': user_id,
            'vdot': settings.get('vdot') if settings else None,
            'lthr': settings.get('lthr') if settings else None,
            'goal_type': settings.get('goal_type', 'race') if settings else 'race',
            'goal_distance_km': settings.get('goal_distance_km', 21) if settings else 21,
            'fitness_level': settings.get('fitness_level', 'beginner') if settings else 'beginner',
            'recovery': recovery,
            'plan_status': plan_status,
            'last_training': last_training_info,
            'todays_plan': todays_plan,
            'today_weekday': today.weekday(),  # 0=Пн, 5=Сб, 6=Вс
        }

    def _analyze_plan_vs_actual(self, planned: list, actual: list, today: date) -> Dict[str, Any]:
        """Сравнить план vs факт за 3 недели"""
        # Текущая неделя
        start_of_week = today - timedelta(days=today.weekday())

        # Факт по датам
        actual_dates = {t.date: t for t in actual if t.date}

        # Плановые типы
        planned_types = []
        planned_this_week = 0
        done_this_week = 0
        skipped_types = []
        missed_long_runs = 0
        missed_intervals = 0
        has_hills_last_2w = False

        for p in planned:
            if not p.date:
                continue
            planned_types.append(p.type)

            # Текущая неделя
            if p.date >= start_of_week:
                planned_this_week += 1
                if p.date in actual_dates:
                    done_this_week += 1

            # Пропущенные
            if p.date < today and p.date not in actual_dates:
                skipped_types.append(p.type)
                if p.type == 'long':
                    missed_long_runs += 1
                elif p.type in ('intervals', 'vo2max', 'tempo', 'threshold'):
                    missed_intervals += 1

            # Горки за последние 2 недели
            two_weeks_ago = today - timedelta(days=14)
            if p.date >= two_weeks_ago and p.type in ('hills',):
                has_hills_last_2w = True

        # Проверяем горки в фактических тренировках тоже
        for t in actual:
            if t.date and t.date >= today - timedelta(days=14):
                if t.elevation_m and t.elevation_m > 200:
                    has_hills_last_2w = True

        # Дней без бега
        days_since_last_run = 0
        if actual:
            latest_actual = max(actual, key=lambda t: t.date if t.date else today - timedelta(days=999))
            if latest_actual.date:
                days_since_last_run = (today - latest_actual.date).days

        # Вчерашняя тренировка — тяжёлая?
        yesterday = today - timedelta(days=1)
        yesterday_was_hard = False
        if yesterday in actual_dates:
            t = actual_dates[yesterday]
            if t.type in ('intervals', 'vo2max', 'tempo', 'threshold', 'long'):
                yesterday_was_hard = True
            elif t.avg_hr and t.avg_hr > 160:
                yesterday_was_hard = True

        return {
            'planned_total': len(planned),
            'done_total': len(actual),
            'completion_rate': len(actual) / max(len(planned), 1) * 100,
            'planned_this_week': planned_this_week,
            'done_this_week': done_this_week,
            'skipped_types': skipped_types,
            'days_since_last_run': days_since_last_run,
            'missed_long_runs': missed_long_runs,
            'missed_intervals': missed_intervals,
            'has_hills_last_2w': has_hills_last_2w,
            'yesterday_was_hard': yesterday_was_hard,
        }

    def _rule_based_recommendation(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based рекомендация с приоритетами"""
        recovery_status = context['recovery']['status']
        plan_status = context['plan_status']
        goal_type = context['goal_type']
        is_weekend = context['today_weekday'] >= 5

        # a) Полный отдых при плохом восстановлении
        if recovery_status == 'rest':
            return {
                'workout_type': 'Отдых',
                'duration_min': 0,
                'distance_km': 0,
                'target_zone': '-',
                'description': 'Полный отдых. Твоё тело просит восстановления.\n\nМожно: лёгкая растяжка, прогулка, foam roller.',
                'reasoning': f"Recovery статус: {context['recovery']['status_text']}. {context['recovery']['reasoning']}",
            }

        # b) Вкатка после длительного перерыва (>4 дней)
        if plan_status['days_since_last_run'] >= 4:
            days = plan_status['days_since_last_run']
            duration = 30 if days >= 7 else 40
            return {
                'workout_type': 'Вкатка',
                'duration_min': duration,
                'distance_km': round(duration / 7.5, 1),
                'target_zone': 'Z1-Z2',
                'description': (
                    f"**Вкатка после {days} дней перерыва**\n\n"
                    f"- {duration} мин очень легко, Z1-Z2\n"
                    f"- Темп: не важен, слушай тело\n"
                    f"- Первые 10 мин можешь чередовать бег/ходьбу\n\n"
                    f"После бега: лёгкая растяжка 5 мин"
                ),
                'reasoning': f"{days} дней без бега. Организму нужна мягкая адаптация перед полноценными тренировками. Не торопись — 1-2 вкатки и можно возвращаться к плану.",
            }

        # c) Лёгкая тренировка после тяжёлой вчера
        if plan_status['yesterday_was_hard'] and recovery_status != 'hard':
            duration = 45
            desc = (
                "**Лёгкий восстановительный бег + страйды**\n\n"
                f"- {duration} мин в Z1-Z2, разговорный темп\n"
                "- После основной части: 4-6x100м страйды\n"
                "  (ускорение до Z5 за 15-20 сек, полное восстановление между ними)\n\n"
                "Страйды помогают нервной системе без нагрузки на сердце"
            )
            return {
                'workout_type': 'Easy + Страйды',
                'duration_min': duration,
                'distance_km': round(duration / 7, 1),
                'target_zone': 'Z1-Z2',
                'description': desc,
                'reasoning': 'Вчера была интенсивная тренировка. Сегодня лёгкий бег + страйды для поддержания нейромышечной координации без утомления.',
            }

        # d) Длинная — если пропущена и сегодня выходной
        if plan_status['missed_long_runs'] > 0 and is_weekend:
            # Адаптируем длительность в зависимости от перерыва
            if plan_status['days_since_last_run'] >= 3:
                duration = 75  # Сокращённая
            else:
                duration = 90

            desc = "**Длинная (компенсация пропуска)**\n\n"
            desc += f"- {duration} мин в Z2, разговорный темп\n"
            desc += "- Можно делать пит-стопы каждые 30 мин\n"

            if goal_type == 'trail':
                desc += "- Ищи холмистый маршрут, набор ~300-500м\n"
                desc += "- Шагай в крутые горки, бежай пологие\n"

            desc += "\nГлавное — время на ногах, не темп"

            return {
                'workout_type': 'Длинная',
                'duration_min': duration,
                'distance_km': round(duration / 7.5, 1),
                'target_zone': 'Z2',
                'description': desc,
                'reasoning': f'Пропущено {plan_status["missed_long_runs"]} длинных тренировок за 3 недели. Выходной — идеально для длинной. Длительность сокращена для безопасности.',
            }

        # e) Интервалы — если пропущены и восстановление позволяет
        if plan_status['missed_intervals'] > 0 and recovery_status == 'hard':
            desc = (
                "**Интервалы (компенсация пропуска)**\n\n"
                "- Разминка: 15 мин Z2 + 4x100м ускорения\n"
                "- Основная часть: 5x4 мин Z4-Z5, отдых 2.5 мин трусцой\n"
                "- Заминка: 10 мин Z1-Z2\n\n"
            )
            if goal_type == 'trail':
                desc += "Вариант: делать интервалы в горку (градиент 6-8%)"
            return {
                'workout_type': 'Интервалы',
                'duration_min': 60,
                'distance_km': 9.0,
                'target_zone': 'Z4-Z5',
                'description': desc,
                'reasoning': f'Пропущено {plan_status["missed_intervals"]} интенсивных тренировок. Восстановление отличное — идеальный момент для интервалов.',
            }

        # e2) Горки для trail — если давно не было
        if goal_type == 'trail' and not plan_status['has_hills_last_2w'] and recovery_status in ('normal', 'hard'):
            desc = (
                "**Горки (трейловая специфика)**\n\n"
                "- Разминка: 15 мин Z2\n"
                "- Основная часть: 6-8x 200-300м в горку (градиент 8-12%)\n"
                "  Вверх: усилие Z4-Z5 (1.5-2 мин)\n"
                "  Вниз: трусцой Z1 (полное восстановление)\n"
                "- Заминка: 10 мин Z1-Z2\n\n"
                "Фокус: сила ног + экономичность бега в горку"
            )
            return {
                'workout_type': 'Горки',
                'duration_min': 60,
                'distance_km': 8.0,
                'target_zone': 'Z4-Z5',
                'description': desc,
                'reasoning': 'Больше 2 недель без горок. Для трейла критически важна горная подготовка — включаем горки.',
            }

        # f) Всё по плану — берём сегодняшнюю
        if context['todays_plan']:
            plan = context['todays_plan']
            return {
                'workout_type': plan.type.capitalize() if plan.type else 'Easy',
                'duration_min': plan.duration_min or 60,
                'distance_km': plan.distance_km or 8.0,
                'target_zone': plan.target_zone or 'Z2',
                'description': plan.description or f"{plan.type} тренировка по плану",
                'reasoning': 'План выполняется стабильно. Сегодня — тренировка по расписанию.',
            }

        # g) Нет плана на сегодня — умная рекомендация
        if recovery_status == 'easy':
            return {
                'workout_type': 'Лёгкая',
                'duration_min': 40,
                'distance_km': 6.0,
                'target_zone': 'Z1-Z2',
                'description': '**Лёгкий бег**\n\n- 40 мин Z1-Z2, разговорный темп\n- Фокус: расслабленные плечи, каденс 170+',
                'reasoning': 'Нет запланированной тренировки. Восстановление среднее — лёгкая пробежка поддержит форму.',
            }

        # Нормальное восстановление + нет плана = фартлек (разнообразие)
        desc = (
            "**Фартлек (переменный бег)**\n\n"
            "- Разминка: 10 мин Z2\n"
            "- Основная часть: 25 мин переменного бега\n"
            "  Чередуй: 1-3 мин быстро (Z3-Z4) / 1-2 мин легко (Z2)\n"
            "  Ускорения по ощущениям — когда тело хочет\n"
            "- Заминка: 10 мин Z1-Z2\n\n"
            "Фартлек = свобода. Не смотри на часы, беги по ощущениям"
        )
        return {
            'workout_type': 'Фартлек',
            'duration_min': 45,
            'distance_km': 7.0,
            'target_zone': 'Z2-Z4',
            'description': desc,
            'reasoning': 'Нет плана на сегодня, восстановление хорошее. Фартлек — отличный формат для поддержания формы и разнообразия.',
        }

    def _ai_enrichment(self, context: Dict[str, Any], rule_rec: Dict[str, Any]) -> Dict[str, Any]:
        """AI обогащение рекомендации через Groq"""
        plan_status = context['plan_status']
        recovery = context['recovery']
        last = context['last_training']

        prompt = f"""Проанализируй данные бегуна и скорректируй рекомендацию тренировки на сегодня.

**Профиль:**
- VDOT: {context.get('vdot', 'неизвестен')}
- Цель: {context['goal_type']} {context['goal_distance_km']}км
- Уровень: {context['fitness_level']}
- День недели: {['Пн','Вт','Ср','Чт','Пт','Сб','Вс'][context['today_weekday']]}

**Recovery:** {recovery['status']} ({recovery['reasoning']})

**Последние 3 недели (план vs факт):**
- Запланировано: {plan_status['planned_total']} тренировок
- Выполнено: {plan_status['done_total']} ({plan_status['completion_rate']:.0f}%)
- Эта неделя: {plan_status['done_this_week']}/{plan_status['planned_this_week']}
- Пропущенные типы: {', '.join(plan_status['skipped_types']) or 'нет'}
- Пропущено длинных: {plan_status['missed_long_runs']}
- Пропущено интервальных: {plan_status['missed_intervals']}
- Дней без бега: {plan_status['days_since_last_run']}
- Вчера была тяжёлая: {'да' if plan_status['yesterday_was_hard'] else 'нет'}

**Последняя тренировка:** {f"{last['days_ago']} дней назад, {last['type']}, {last['distance_km']}км" if last else 'нет данных'}

**Rule-based предложение:** {rule_rec['workout_type']} — {rule_rec['reasoning']}

Задача: Подтверди или скорректируй рекомендацию. Верни ТОЛЬКО JSON:
{{"workout_type": "...", "duration_min": число, "distance_km": число, "target_zone": "...", "description": "детальное описание (разминка + основная + заминка)", "reasoning": "почему именно эта тренировка (2-3 предложения)"}}

ВАЖНО:
- НЕ рекомендуй "лёгкий бег Z2 30 мин" если восстановление нормальное и нет противопоказаний
- Если пропущена длинная — предложи длинную (адаптированную)
- Для трейла: включай горки и набор высоты
- Описание должно быть КОНКРЕТНЫМ: разминка + основная часть + заминка с зонами и длительностью"""

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Ты — тренер по бегу. Рекомендуешь ОДНУ конкретную тренировку на сегодня на основе анализа плана и факта. Отвечай ТОЛЬКО JSON без markdown."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.6,
            max_tokens=600
        )

        content = response.choices[0].message.content.strip()
        # Убираем markdown blocks
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        import json
        result = json.loads(content)

        logger.info(f"SmartAdvisor AI рекомендация: {result.get('workout_type')} для user {context['user_id']}")
        return result


# Глобальный экземпляр
smart_advisor = SmartAdvisor()
