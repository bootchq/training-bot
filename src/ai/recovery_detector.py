"""AI детектор восстановления на основе wellness + HRV + sRPE"""
from datetime import date, timedelta
from typing import Dict, Any

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..database.db import db, WellnessSurvey
from ..utils.config import Config
from ..utils.logger import logger


class RecoveryDetector:
    """AI-детектор уровня восстановления"""

    # Статус восстановления
    RECOVERY_STATUS = {
        'rest': 'Полный отдых',
        'easy': 'Легкая тренировка',
        'normal': 'Обычная тренировка',
        'hard': 'Интенсивная тренировка'
    }

    def __init__(self):
        """Инициализация"""
        self.api_key = Config.GROQ_API_KEY

        if self.api_key and OPENAI_AVAILABLE:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url="https://api.groq.com/openai/v1"
            )
            self.model = "llama-3.3-70b-versatile"
            logger.info("RecoveryDetector инициализирован (Groq)")
        else:
            self.client = None
            logger.warning("RecoveryDetector недоступен: нет Groq API ключа")

    def detect_recovery_status(self, user_id: int) -> Dict[str, Any]:
        """
        Определить статус восстановления пользователя

        Args:
            user_id: ID пользователя

        Returns:
            dict с полями:
                - status: str ('rest'/'easy'/'normal'/'hard')
                - status_text: str (текстовое описание)
                - confidence: float (0-1, уверенность в оценке)
                - reasoning: str (объяснение)
                - metrics: dict (метрики для объяснения)
        """
        # Собираем метрики восстановления
        metrics = self._collect_recovery_metrics(user_id)

        if not metrics['has_data']:
            return self._get_default_status()

        # Если нет AI - используем rule-based логику
        if not self.client:
            return self._rule_based_detection(metrics)

        # AI анализ
        try:
            status = self._ai_detection(metrics)
            logger.info(f"Recovery status определён для user_id={user_id}: {status['status']}")
            return status
        except Exception as e:
            logger.error(f"Ошибка AI детекции восстановления: {e}")
            return self._rule_based_detection(metrics)

    def _collect_recovery_metrics(self, user_id: int) -> Dict[str, Any]:
        """Собрать метрики для анализа восстановления"""
        metrics = {
            'has_data': False,
            'wellness_last_3d': [],
            'pain_last_7d': 0,
            'avg_sleep_quality': None,
            'srpe_last_7d': [],
            'rhr_trend': None,  # повышение/понижение RHR
            'hrv_trend': None,  # повышение/понижение HRV
        }

        today = date.today()

        # Последние 7 дней wellness surveys
        with db.get_session() as session:
            surveys = session.query(WellnessSurvey).filter(
                WellnessSurvey.user_id == user_id,
                WellnessSurvey.date >= today - timedelta(days=7)
            ).order_by(WellnessSurvey.date.desc()).all()

            if not surveys:
                return metrics

            metrics['has_data'] = True

            # Последние 3 дня wellness rating
            for s in surveys[:3]:
                if s.wellness_rating:
                    metrics['wellness_last_3d'].append(s.wellness_rating)

            # Боли за 7 дней
            metrics['pain_last_7d'] = sum(1 for s in surveys if s.pain_reported)

            # Средняя оценка сна
            sleep_ratings = [self._sleep_to_number(s.sleep_quality) for s in surveys if s.sleep_quality]
            if sleep_ratings:
                metrics['avg_sleep_quality'] = sum(sleep_ratings) / len(sleep_ratings)

            # sRPE за 7 дней (тренировочная нагрузка)
            for s in surveys:
                if s.srpe:
                    metrics['srpe_last_7d'].append(s.srpe)

            # RHR и HRV тренды (сравниваем последние 3 дня с предыдущими 4)
            rhr_last3 = [s.rhr for s in surveys[:3] if s.rhr]
            rhr_prev4 = [s.rhr for s in surveys[3:7] if s.rhr]

            hrv_last3 = [s.hrv for s in surveys[:3] if s.hrv]
            hrv_prev4 = [s.hrv for s in surveys[3:7] if s.hrv]

            if rhr_last3 and rhr_prev4:
                avg_last = sum(rhr_last3) / len(rhr_last3)
                avg_prev = sum(rhr_prev4) / len(rhr_prev4)
                diff = avg_last - avg_prev
                if diff > 3:
                    metrics['rhr_trend'] = 'up'  # плохо
                elif diff < -3:
                    metrics['rhr_trend'] = 'down'  # хорошо
                else:
                    metrics['rhr_trend'] = 'stable'

            if hrv_last3 and hrv_prev4:
                avg_last = sum(hrv_last3) / len(hrv_last3)
                avg_prev = sum(hrv_prev4) / len(hrv_prev4)
                diff = avg_last - avg_prev
                if diff > 5:
                    metrics['hrv_trend'] = 'up'  # хорошо
                elif diff < -5:
                    metrics['hrv_trend'] = 'down'  # плохо
                else:
                    metrics['hrv_trend'] = 'stable'

        return metrics

    def _sleep_to_number(self, sleep_quality: str) -> float:
        """Конвертация текстовой оценки сна в число"""
        mapping = {
            'отлично': 5.0,
            'хорошо': 4.0,
            'нормально': 3.0,
            'плохо': 2.0,
            'очень плохо': 1.0
        }
        return mapping.get(sleep_quality.lower(), 3.0)

    def _rule_based_detection(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Rule-based определение статуса (без AI)"""
        score = 0  # 0-10, чем выше - тем лучше восстановление

        # 1. Wellness rating (последние 3 дня)
        if metrics['wellness_last_3d']:
            avg_wellness = sum(metrics['wellness_last_3d']) / len(metrics['wellness_last_3d'])
            score += (avg_wellness - 1) * 2  # 1-5 → 0-8

        # 2. Боли (-2 балла за каждый день с болью)
        score -= metrics['pain_last_7d'] * 2

        # 3. Сон (+1 балл за каждый балл выше 3)
        if metrics['avg_sleep_quality']:
            score += (metrics['avg_sleep_quality'] - 3)

        # 4. RHR тренд
        if metrics['rhr_trend'] == 'up':
            score -= 2  # повышенный RHR = недовосстановление
        elif metrics['rhr_trend'] == 'down':
            score += 1

        # 5. HRV тренд
        if metrics['hrv_trend'] == 'up':
            score += 2  # высокий HRV = хорошее восстановление
        elif metrics['hrv_trend'] == 'down':
            score -= 2

        # 6. sRPE нагрузка (если >500 AU/день последние 7 дней - переутомление)
        if metrics['srpe_last_7d']:
            avg_srpe = sum(metrics['srpe_last_7d']) / len(metrics['srpe_last_7d'])
            if avg_srpe > 500:
                score -= 2
            elif avg_srpe > 400:
                score -= 1

        # Определяем статус по score
        if score < 2:
            status = 'rest'
            confidence = 0.8
        elif score < 5:
            status = 'easy'
            confidence = 0.7
        elif score < 8:
            status = 'normal'
            confidence = 0.6
        else:
            status = 'hard'
            confidence = 0.7

        return {
            'status': status,
            'status_text': self.RECOVERY_STATUS[status],
            'confidence': confidence,
            'reasoning': self._build_reasoning(status, metrics, score),
            'metrics': {
                'recovery_score': round(score, 1),
                'wellness_avg': round(sum(metrics['wellness_last_3d']) / len(metrics['wellness_last_3d']), 1) if metrics['wellness_last_3d'] else None,
                'pain_days': metrics['pain_last_7d'],
                'sleep_avg': round(metrics['avg_sleep_quality'], 1) if metrics['avg_sleep_quality'] else None,
                'rhr_trend': metrics['rhr_trend'],
                'hrv_trend': metrics['hrv_trend']
            }
        }

    def _ai_detection(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """AI определение статуса восстановления"""
        prompt = self._build_ai_prompt(metrics)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": """Ты - спортивный физиолог, специализируешься на восстановлении бегунов.
Анализируешь wellness данные, HRV, RHR, sRPE и определяешь готовность к тренировкам.
Отвечай ТОЛЬКО в формате JSON:
{
  "status": "rest/easy/normal/hard",
  "confidence": число 0-1,
  "reasoning": "объяснение 2-3 предложения"
}"""
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )

        # Парсим JSON
        content = response.choices[0].message.content.strip()
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        import json
        result = json.loads(content)

        return {
            'status': result['status'],
            'status_text': self.RECOVERY_STATUS[result['status']],
            'confidence': result['confidence'],
            'reasoning': result['reasoning'],
            'metrics': {
                'wellness_avg': round(sum(metrics['wellness_last_3d']) / len(metrics['wellness_last_3d']), 1) if metrics['wellness_last_3d'] else None,
                'pain_days': metrics['pain_last_7d'],
                'sleep_avg': round(metrics['avg_sleep_quality'], 1) if metrics['avg_sleep_quality'] else None,
                'rhr_trend': metrics['rhr_trend'],
                'hrv_trend': metrics['hrv_trend']
            }
        }

    def _build_ai_prompt(self, metrics: Dict[str, Any]) -> str:
        """Промпт для AI анализа"""
        avg_wellness = sum(metrics['wellness_last_3d']) / len(metrics['wellness_last_3d']) if metrics['wellness_last_3d'] else 3

        prompt = f"""Оцени готовность бегуна к тренировкам на основе данных восстановления.

**Wellness (последние 3 дня):**
- Средняя оценка: {avg_wellness:.1f}/5 (1=плохо, 5=отлично)
- Отдельные дни: {', '.join(str(w) for w in metrics['wellness_last_3d'])}

**Боли и дискомфорт:**
- Дней с болью (7 дней): {metrics['pain_last_7d']}

**Сон (7 дней):**
- Средняя оценка: {f"{metrics['avg_sleep_quality']:.1f}/5" if metrics['avg_sleep_quality'] else 'нет данных'}

**RHR (пульс покоя) тренд:**
- {metrics['rhr_trend'] or 'нет данных'} (up=плохо, down=хорошо)

**HRV (вариабельность) тренд:**
- {metrics['hrv_trend'] or 'нет данных'} (up=хорошо, down=плохо)

**sRPE (нагрузка за 7 дней):**
- {len(metrics['srpe_last_7d'])} тренировок
- Средняя sRPE: {f"{sum(metrics['srpe_last_7d'])/len(metrics['srpe_last_7d']):.0f} AU" if metrics['srpe_last_7d'] else 'нет данных'}

**Рекомендуй один из статусов:**
- rest: полный отдых (серьёзное недовосстановление)
- easy: только легкая тренировка Z1-Z2
- normal: обычная тренировка по плану
- hard: можно интенсивную тренировку

Верни JSON с полями: status, confidence (0-1), reasoning.
"""
        return prompt

    def _build_reasoning(self, status: str, metrics: Dict[str, Any], score: float) -> str:
        """Текстовое объяснение статуса"""
        reasons = []

        if metrics['wellness_last_3d']:
            avg = sum(metrics['wellness_last_3d']) / len(metrics['wellness_last_3d'])
            if avg < 2.5:
                reasons.append("низкое самочувствие")
            elif avg > 4:
                reasons.append("отличное самочувствие")

        if metrics['pain_last_7d'] > 0:
            reasons.append(f"боли {metrics['pain_last_7d']} дней")

        if metrics['rhr_trend'] == 'up':
            reasons.append("повышенный RHR")
        if metrics['hrv_trend'] == 'down':
            reasons.append("сниженный HRV")

        if not reasons:
            reasons.append("нормальные показатели")

        return f"Рекомендуется {self.RECOVERY_STATUS[status].lower()}. Причины: {', '.join(reasons)}. Recovery score: {score:.1f}/10."

    def _get_default_status(self) -> Dict[str, Any]:
        """Статус по умолчанию когда нет данных"""
        return {
            'status': 'normal',
            'status_text': self.RECOVERY_STATUS['normal'],
            'confidence': 0.3,
            'reasoning': 'Недостаточно данных для точной оценки восстановления. Рекомендуется обычная тренировка.',
            'metrics': {}
        }


# Глобальный экземпляр
recovery_detector = RecoveryDetector()
