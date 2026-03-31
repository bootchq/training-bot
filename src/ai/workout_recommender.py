"""AI рекомендации персонализированных тренировок на основе истории и wellness данных"""
from datetime import date, timedelta
from typing import Dict, Any, List

from ..database.db import db, WellnessSurvey
from ..core.fitness_detector import detect_fitness_level
from ..utils.logger import logger
from .groq_client import get_groq_client, MODEL_MAIN


class WorkoutRecommender:
    """AI-рекомендатель тренировок на основе истории и wellness"""

    def __init__(self):
        self.client = get_groq_client()
        self.model = MODEL_MAIN
        if self.client:
            logger.info("WorkoutRecommender инициализирован (Groq)")
        else:
            logger.warning("WorkoutRecommender: Groq недоступен")

    def get_recommendation(self, user_id: int) -> Dict[str, Any]:
        """
        Получить персонализированную рекомендацию тренировки

        Args:
            user_id: ID пользователя

        Returns:
            dict с полями:
                - workout_type: str (тип тренировки)
                - duration_min: int (длительность)
                - distance_km: float (дистанция)
                - target_zone: str (целевая зона пульса)
                - description: str (описание)
                - reasoning: str (объяснение почему эта тренировка)
        """
        if not self.client:
            return self._get_fallback_recommendation(user_id)

        # Собираем контекст
        context = self._build_context(user_id)

        # Формируем промпт
        prompt = self._build_prompt(context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Ты - опытный тренер по бегу, специализирующийся на персонализированных планах.
Анализируешь историю тренировок, wellness данные и текущий уровень подготовки.
Даёшь конкретные рекомендации с учётом восстановления и прогрессии нагрузки.
Отвечай ТОЛЬКО в формате JSON без дополнительного текста:
{
  "workout_type": "тип (Интервалы/Темповый/Длинная/Восстановительная/Лёгкая)",
  "duration_min": число,
  "distance_km": число,
  "target_zone": "Z1-Z2 или Z3-Z4 и т.д.",
  "description": "краткое описание тренировки",
  "reasoning": "почему именно эта тренировка (2-3 предложения)"
}"""
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=500
            )

            # Парсим JSON ответ
            content = response.choices[0].message.content.strip()
            # Убираем markdown code blocks если есть
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            import json
            recommendation = json.loads(content)

            logger.info(f"AI рекомендация получена для user_id={user_id}")
            return recommendation

        except Exception as e:
            logger.error(f"Ошибка получения AI рекомендации: {e}")
            return self._get_fallback_recommendation(user_id)

    def _build_context(self, user_id: int) -> Dict[str, Any]:
        """Собрать контекст для AI"""
        context = {}

        # 1. Данные пользователя
        user = db.get_user_by_id(user_id)
        if user:
            context['vdot'] = user.vdot
            context['lthr'] = user.lthr
            context['goal_type'] = user.goal_type
            context['goal_distance_km'] = user.goal_distance_km
            context['goal_date'] = user.goal_date
            context['experience_level'] = user.experience_level

        # 2. Fitness level (текущий)
        fitness_level, fitness_stats = detect_fitness_level(user_id)
        context['fitness_level'] = fitness_level or 'beginner'
        context['fitness_score'] = fitness_stats.get('score', 0)

        # 3. Последние 14 дней тренировок
        context['recent_trainings'] = self._get_recent_trainings(user_id, days=14)

        # 4. Последние 7 дней wellness surveys
        context['recent_wellness'] = self._get_recent_wellness(user_id, days=7)

        # 5. Статистика за последние 7 дней
        context['weekly_stats'] = self._calculate_weekly_stats(user_id)

        return context

    def _get_recent_trainings(self, user_id: int, days: int = 14) -> List[Dict[str, Any]]:
        """Получить последние N дней тренировок"""
        start_date = date.today() - timedelta(days=days)
        trainings = db.get_trainings_for_period(user_id, start_date, date.today())

        result = []
        for t in trainings:
            result.append({
                'date': t.date.strftime('%Y-%m-%d'),
                'type': t.type,
                'distance_km': t.distance_km,
                'duration_min': t.duration_min,
                'avg_hr': t.avg_hr,
                'avg_pace': t.avg_pace,
            })
        return result

    def _get_recent_wellness(self, user_id: int, days: int = 7) -> List[Dict[str, Any]]:
        """Получить последние N дней wellness опросов"""
        start_date = date.today() - timedelta(days=days)

        with db.get_session() as session:
            surveys = session.query(WellnessSurvey).filter(
                WellnessSurvey.user_id == user_id,
                WellnessSurvey.date >= start_date
            ).order_by(WellnessSurvey.date.desc()).all()

            result = []
            for s in surveys:
                result.append({
                    'date': s.date.strftime('%Y-%m-%d'),
                    'wellness_rating': s.wellness_rating,  # 1-5 scale
                    'training_rating': s.training_rating,  # 1-10 scale
                    'pain_reported': s.pain_reported,
                    'pain_location': s.pain_location,
                    'sleep_quality': s.sleep_quality,
                    'srpe': s.srpe,
                    'rhr': s.rhr,
                    'hrv': s.hrv
                })
            return result

    def _calculate_weekly_stats(self, user_id: int) -> Dict[str, Any]:
        """Статистика за последние 7 дней"""
        start_date = date.today() - timedelta(days=7)
        trainings = db.get_trainings_for_period(user_id, start_date, date.today())

        total_distance = sum(t.distance_km or 0 for t in trainings)
        total_duration = sum(t.duration_min or 0 for t in trainings)
        count = len(trainings)

        # Средняя оценка wellness (из surveys)
        with db.get_session() as session:
            surveys = session.query(WellnessSurvey).filter(
                WellnessSurvey.user_id == user_id,
                WellnessSurvey.date >= start_date
            ).all()

            avg_wellness = sum(s.wellness_rating or 3 for s in surveys) / len(surveys) if surveys else 3
            avg_srpe = sum(s.srpe or 0 for s in surveys) / len(surveys) if surveys else 0
            pain_count = sum(1 for s in surveys if s.pain_reported)

        return {
            'workouts_count': count,
            'total_distance_km': round(total_distance, 1),
            'total_duration_min': total_duration,
            'avg_wellness': round(avg_wellness, 1),
            'avg_srpe': round(avg_srpe, 0),
            'pain_days': pain_count
        }

    def _build_prompt(self, context: Dict[str, Any]) -> str:
        """Построить промпт для AI"""
        prompt = f"""Проанализируй данные бегуна и порекомендуй следующую тренировку.

**Профиль:**
- VDOT: {context.get('vdot', 'неизвестен')}
- LTHR: {context.get('lthr', 'неизвестен')} bpm
- Fitness Level: {context.get('fitness_level', 'beginner')} (score: {context.get('fitness_score', 0)})
- Цель: {context.get('goal_type', 'не указана')}
- Дистанция цели: {context.get('goal_distance_km', 'н/д')} км
- Опыт: {context.get('experience_level', 'beginner')}

**Последние 7 дней:**
- Тренировок: {context['weekly_stats']['workouts_count']}
- Дистанция: {context['weekly_stats']['total_distance_km']} км
- Время: {context['weekly_stats']['total_duration_min']} мин
- Средняя wellness: {context['weekly_stats']['avg_wellness']}/5 (1=плохо, 5=отлично)
- Средняя sRPE: {context['weekly_stats']['avg_srpe']} AU
- Дней с болью: {context['weekly_stats']['pain_days']}

**Последние тренировки (14 дней):**
"""
        for t in context['recent_trainings'][:5]:  # Последние 5
            prompt += f"- {t['date']}: {t.get('distance_km', 0):.1f}км, {t.get('duration_min', 0)}мин, пульс {t.get('avg_hr', 'н/д')}\n"

        if context['recent_wellness']:
            prompt += "\n**Wellness данные (7 дней):**\n"
            for w in context['recent_wellness'][:3]:  # Последние 3
                prompt += f"- {w['date']}: wellness {w['wellness_rating']}/5, тренировка {w['training_rating']}/10"
                if w['pain_reported']:
                    prompt += f", боль: {w['pain_location']}"
                prompt += "\n"

        prompt += """
**Задача:**
Порекомендуй следующую тренировку с учётом:
1. Текущий уровень восстановления (wellness, sRPE, боли)
2. Прогрессия нагрузки (не более +10% в неделю)
3. Цель и уровень подготовки
4. Разнообразие тренировок (не повторять тип)

Верни JSON с полями: workout_type, duration_min, distance_km, target_zone, description, reasoning.
"""
        return prompt

    def _get_fallback_recommendation(self, user_id: int) -> Dict[str, Any]:
        """Резервная рекомендация при ошибке AI"""
        # Базовая рекомендация на основе fitness level
        level, fitness_stats = detect_fitness_level(user_id)
        level = level or 'beginner'

        if level == 'beginner':
            return {
                'workout_type': 'Лёгкая',
                'duration_min': 30,
                'distance_km': 5.0,
                'target_zone': 'Z1-Z2',
                'description': 'Лёгкий бег в низкой зоне пульса',
                'reasoning': 'Базовая тренировка для развития аэробной базы'
            }
        elif level == 'intermediate':
            return {
                'workout_type': 'Темповый',
                'duration_min': 40,
                'distance_km': 8.0,
                'target_zone': 'Z3',
                'description': 'Темповая тренировка для развития порога',
                'reasoning': 'Улучшение лактатного порога'
            }
        else:  # advanced
            return {
                'workout_type': 'Интервалы',
                'duration_min': 50,
                'distance_km': 10.0,
                'target_zone': 'Z4-Z5',
                'description': 'Интервальная тренировка 6x800м',
                'reasoning': 'Развитие скорости и VO2max'
            }


# Глобальный экземпляр
workout_recommender = WorkoutRecommender()
