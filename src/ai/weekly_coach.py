"""AI еженедельный анализ тренировок с персональными советами"""
from datetime import date, timedelta
from typing import Optional, Dict, Any

from ..database.db import db
from ..utils.logger import logger
from ..utils import time_utils
from .groq_client import get_groq_client, MODEL_MAIN


class WeeklyCoach:
    """AI-коуч для еженедельного анализа и советов"""

    def __init__(self):
        self.client = get_groq_client()
        self.model = MODEL_MAIN
        if self.client:
            logger.info("WeeklyCoach инициализирован (Groq)")
        else:
            logger.warning("WeeklyCoach: Groq недоступен")

    def get_weekly_insights(
        self,
        user_id: int,
        week_start: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Получить еженедельный анализ тренировок

        Args:
            user_id: ID пользователя
            week_start: Начало недели (пн), по умолчанию - текущая неделя

        Returns:
            dict с полями:
                - summary: str (краткая сводка недели)
                - plan_vs_actual: dict (выполнение плана)
                - progress_metrics: dict (метрики прогресса)
                - insights: List[str] (персональные инсайты)
                - recommendations: List[str] (рекомендации)
        """
        if week_start is None:
            today = time_utils.today()
            week_start = today - timedelta(days=today.weekday())

        week_end = week_start + timedelta(days=6)

        # Собираем данные недели
        week_data = self._collect_week_data(user_id, week_start, week_end)

        if not week_data['has_activities']:
            return self._get_no_data_response()

        # Если нет AI - базовый анализ
        if not self.client:
            return self._basic_analysis(week_data)

        # AI анализ
        try:
            insights = self._ai_analysis(week_data)
            logger.info(f"Weekly insights получены для user_id={user_id}")
            return insights
        except Exception as e:
            logger.error(f"Ошибка AI weekly анализа: {e}")
            return self._basic_analysis(week_data)

    def _collect_week_data(
        self,
        user_id: int,
        week_start: date,
        week_end: date
    ) -> Dict[str, Any]:
        """Собрать данные за неделю"""
        data = {
            'has_activities': False,
            'week_start': week_start.strftime('%d.%m'),
            'week_end': week_end.strftime('%d.%m'),
        }

        # План на неделю
        planned = db.get_plan_for_period(user_id, week_start, week_end)
        data['planned_workouts'] = len(planned)
        data['planned_distance'] = sum(p.distance_km or 0 for p in planned)
        data['planned_duration'] = sum(p.duration_min or 0 for p in planned)

        # Фактические тренировки
        actual = db.get_trainings_for_period(user_id, week_start, week_end)
        data['actual_workouts'] = len(actual)
        data['actual_distance'] = sum(t.distance_km or 0 for t in actual)
        data['actual_duration'] = sum(t.duration_min or 0 for t in actual)

        if actual:
            data['has_activities'] = True
            data['avg_hr'] = sum(t.avg_hr for t in actual if t.avg_hr) / len([t for t in actual if t.avg_hr]) if any(t.avg_hr for t in actual) else None

        # Completion rate
        if data['planned_workouts'] > 0:
            data['completion_rate'] = (data['actual_workouts'] / data['planned_workouts']) * 100
        else:
            data['completion_rate'] = 0

        # Прогресс VDOT (сравнение с предыдущей неделей)
        data['vdot_progress'] = self._calculate_vdot_progress(user_id, week_end)

        # Предыдущая неделя для сравнения
        prev_week_start = week_start - timedelta(days=7)
        prev_week_end = week_start - timedelta(days=1)
        prev_actual = db.get_trainings_for_period(user_id, prev_week_start, prev_week_end)

        data['prev_week_distance'] = sum(t.distance_km or 0 for t in prev_actual)
        data['prev_week_workouts'] = len(prev_actual)

        # Изменение объёма
        if data['prev_week_distance'] > 0:
            volume_change = ((data['actual_distance'] - data['prev_week_distance']) / data['prev_week_distance']) * 100
            data['volume_change_pct'] = round(volume_change, 1)
        else:
            data['volume_change_pct'] = None

        # Данные пользователя
        user = db.get_user_by_id(user_id)
        if user:
            data['goal_type'] = user.goal_type
            data['goal_distance_km'] = user.goal_distance_km
            data['goal_date'] = user.goal_date
            data['current_vdot'] = user.vdot

        return data

    def _calculate_vdot_progress(self, user_id: int, as_of_date: date) -> Optional[Dict[str, Any]]:
        """Рассчитать прогресс VDOT"""
        # Получаем историю VDOT за последние 4 недели
        start_date = as_of_date - timedelta(days=28)
        history = db.get_vdot_history(user_id, start_date, as_of_date)

        if len(history) < 2:
            return None

        # Сравниваем последний с первым
        first_vdot = history[0].vdot
        last_vdot = history[-1].vdot
        change = last_vdot - first_vdot
        change_pct = (change / first_vdot) * 100

        return {
            'current': last_vdot,
            'previous': first_vdot,
            'change': round(change, 1),
            'change_pct': round(change_pct, 1)
        }

    def _ai_analysis(self, week_data: Dict[str, Any]) -> Dict[str, Any]:
        """AI анализ недели"""
        prompt = self._build_ai_prompt(week_data)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """Ты - опытный тренер по бегу. Анализируешь неделю тренировок и даёшь персональные советы.
Фокусируйся на:
1. Выполнение плана (consistency)
2. Прогресс метрик
3. Управление нагрузкой
4. Конкретные рекомендации

Отвечай ТОЛЬКО в формате JSON:
{
  "summary": "краткая сводка недели 2-3 предложения",
  "insights": ["инсайт 1", "инсайт 2", "инсайт 3"],
  "recommendations": ["рекомендация 1", "рекомендация 2", "рекомендация 3"]
}

Инсайты - это наблюдения о выполнении, прогрессе.
Рекомендации - конкретные действия на следующую неделю."""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=800
        )

        # Парсим JSON
        content = response.choices[0].message.content.strip()
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        import json
        ai_result = json.loads(content)

        # Дополняем метриками
        return {
            'summary': ai_result['summary'],
            'plan_vs_actual': {
                'planned_workouts': week_data['planned_workouts'],
                'actual_workouts': week_data['actual_workouts'],
                'completion_rate': round(week_data['completion_rate'], 0),
                'planned_distance': round(week_data['planned_distance'], 1),
                'actual_distance': round(week_data['actual_distance'], 1),
            },
            'progress_metrics': {
                'volume_change_pct': week_data.get('volume_change_pct'),
                'vdot_progress': week_data.get('vdot_progress'),
            },
            'insights': ai_result['insights'],
            'recommendations': ai_result['recommendations']
        }

    def _build_ai_prompt(self, week_data: Dict[str, Any]) -> str:
        """Промпт для AI анализа"""
        prompt = f"""Проанализируй неделю тренировок бегуна.

**Период:** {week_data['week_start']} - {week_data['week_end']}

**План vs факт:**
- Запланировано: {week_data['planned_workouts']} тренировок, {week_data['planned_distance']:.1f} км
- Выполнено: {week_data['actual_workouts']} тренировок, {week_data['actual_distance']:.1f} км
- Completion rate: {week_data['completion_rate']:.0f}%

**Изменение объёма:**
- Предыдущая неделя: {week_data['prev_week_distance']:.1f} км
- Эта неделя: {week_data['actual_distance']:.1f} км
- Изменение: {f"{week_data['volume_change_pct']:+.1f}%" if week_data['volume_change_pct'] is not None else 'н/д'}

**Прогресс VDOT:**
"""
        if week_data.get('vdot_progress'):
            vp = week_data['vdot_progress']
            prompt += f"- Было: {vp['previous']:.1f}\n"
            prompt += f"- Стало: {vp['current']:.1f}\n"
            prompt += f"- Изменение: {vp['change']:+.1f} ({vp['change_pct']:+.1f}%)\n"
        else:
            prompt += "- Недостаточно данных\n"

        if week_data.get('goal_type'):
            prompt += "\n**Цель бегуна:**\n"
            prompt += f"- Тип: {week_data['goal_type']}\n"
            if week_data.get('goal_distance_km'):
                prompt += f"- Дистанция: {week_data['goal_distance_km']} км\n"
            if week_data.get('goal_date'):
                days_left = (week_data['goal_date'] - time_utils.today()).days
                prompt += f"- До забега: {days_left} дней\n"

        prompt += """
**Твоя задача:**
1. Дать краткую сводку недели (что получилось, что нет)
2. 3 персональных инсайта (наблюдения о тренировках, прогрессе, нагрузке)
3. 3 конкретные рекомендации на следующую неделю

Будь конкретным, избегай общих фраз. Учитывай правило 10% (не увеличивать объём >10%/неделю).

Верни JSON с полями: summary, insights (массив), recommendations (массив).
"""
        return prompt

    def _basic_analysis(self, week_data: Dict[str, Any]) -> Dict[str, Any]:
        """Базовый анализ без AI"""
        # Summary
        if week_data['completion_rate'] >= 80:
            summary = f"Отличная неделя! Выполнено {week_data['actual_workouts']} из {week_data['planned_workouts']} тренировок."
        elif week_data['completion_rate'] >= 50:
            summary = f"Неплохая неделя. Выполнено {week_data['actual_workouts']} из {week_data['planned_workouts']} тренировок."
        else:
            summary = f"Сложная неделя. Выполнено только {week_data['actual_workouts']} из {week_data['planned_workouts']} тренировок."

        # Insights
        insights = []
        if week_data['completion_rate'] >= 80:
            insights.append(f"✅ Отличная консистентность: {week_data['completion_rate']:.0f}% выполнения плана")
        elif week_data['completion_rate'] < 50:
            insights.append(f"⚠️ Низкая консистентность: {week_data['completion_rate']:.0f}% выполнения плана")

        if week_data.get('volume_change_pct'):
            if week_data['volume_change_pct'] > 10:
                insights.append(f"⚠️ Резкое увеличение объёма: {week_data['volume_change_pct']:+.1f}% (риск перетренированности)")
            elif week_data['volume_change_pct'] > 0:
                insights.append(f"📈 Плавное увеличение объёма: {week_data['volume_change_pct']:+.1f}%")

        if week_data.get('vdot_progress') and week_data['vdot_progress']['change'] > 0:
            insights.append(f"🚀 VDOT вырос: {week_data['vdot_progress']['change']:+.1f} балла")

        # Recommendations
        recommendations = []
        if week_data['completion_rate'] < 70:
            recommendations.append("Попробуй сделать план более реалистичным или найти время для тренировок")

        if week_data.get('volume_change_pct') and week_data['volume_change_pct'] > 10:
            recommendations.append("Снизь объём на следующей неделе на 5-10% для восстановления")
        else:
            recommendations.append("Продолжай в том же духе, можно плавно увеличивать объём (+5-10%)")

        recommendations.append("Не забывай про восстановление: сон 7-8 часов, растяжка после тренировок")

        return {
            'summary': summary,
            'plan_vs_actual': {
                'planned_workouts': week_data['planned_workouts'],
                'actual_workouts': week_data['actual_workouts'],
                'completion_rate': round(week_data['completion_rate'], 0),
                'planned_distance': round(week_data['planned_distance'], 1),
                'actual_distance': round(week_data['actual_distance'], 1),
            },
            'progress_metrics': {
                'volume_change_pct': week_data.get('volume_change_pct'),
                'vdot_progress': week_data.get('vdot_progress'),
            },
            'insights': insights,
            'recommendations': recommendations
        }

    def _get_no_data_response(self) -> Dict[str, Any]:
        """Ответ когда нет данных"""
        return {
            'summary': 'За эту неделю нет данных о тренировках.',
            'plan_vs_actual': {
                'planned_workouts': 0,
                'actual_workouts': 0,
                'completion_rate': 0,
                'planned_distance': 0.0,
                'actual_distance': 0.0,
            },
            'progress_metrics': {},
            'insights': ['Начни тренироваться чтобы отслеживать прогресс'],
            'recommendations': [
                'Создай тренировочный план',
                'Начни с лёгких тренировок 2-3 раза в неделю',
                'Синхронизируй с Garmin/Strava для автоматического трекинга'
            ]
        }


# Глобальный экземпляр
weekly_coach = WeeklyCoach()
