"""
Состояние бегуна - единый объект для анализа прогресса и адаптации плана

Этот модуль реализует переход от реактивной адаптации (события → реакция)
к предсказывающей адаптации (тренд → диагноз → адаптация).

Философия: Safety First
- Безопасность > амбиции
- Паттерны > разовые события
- История = ограничитель роста
"""
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Literal
from dataclasses import dataclass, asdict

from ..database.db import Training, WellnessSurvey, db
from ..utils.logger import logger


# Типы для type hints
StatusType = Literal["progressing", "stable", "mild_fatigue", "overreaching", "danger"]
TrendType = Literal["growing", "stable", "declining"]
HRTrendType = Literal["stable", "rising_1_week", "rising_2_weeks", "rising_3_weeks", "critical"]
RHRStatusType = Literal["ok", "warning", "critical"]


@dataclass
class VolumeMetrics:
    """Метрики объёма тренировок"""
    avg_weekly_km: float  # Средний недельный объём
    baseline_weekly_km: float  # Базовый уровень (для ограничения роста)
    trend: TrendType  # Тренд: растёт / стабильно / падает
    max_weekly_km: float  # Максимальный недельный объём


@dataclass
class IntensityMetrics:
    """Метрики интенсивности (по минутам, не дням!)"""
    intense_minutes_week: int  # Сумма tempo + intervals + threshold минут
    total_minutes_week: int  # Общее время бега за неделю
    actual_ratio: float  # Фактическое соотношение (15-20% для BASE/BUILD)
    target_ratio: str  # Целевое соотношение "15-20%"
    status: Literal["ok", "too_low", "too_high"]


@dataclass
class ResponseMetrics:
    """Реакция организма на нагрузку"""
    # Пульс на easy
    easy_hr_baseline: Optional[int]  # Базовый уровень easy HR
    easy_hr_current: Optional[int]  # Текущий easy HR
    easy_hr_delta_pct: Optional[float]  # Изменение в %
    easy_hr_trend: HRTrendType  # Тренд: stable / rising_1_week / rising_2_weeks / critical

    # Дрейф пульса на длинных
    long_hr_drift_avg_pct: Optional[float]  # Средний дрейф за 4 недели (%)

    # RHR (Resting Heart Rate) - если есть
    rhr_baseline: Optional[int]
    rhr_current: Optional[int]
    rhr_delta: Optional[int]  # Изменение в bpm
    rhr_status: RHRStatusType  # ok / warning (+5-7) / critical (+8+)

    # Wellness (субъективное)
    wellness_avg: Optional[float]  # Средняя оценка самочувствия (1-10)
    sleep_avg: Optional[float]  # Средняя оценка сна


@dataclass
class ProgressMetrics:
    """Метрики прогресса"""
    vdot_4w_ago: Optional[float]  # VDOT 4 недели назад
    vdot_current: Optional[float]  # Текущий VDOT
    vdot_delta: Optional[float]  # Изменение VDOT
    vdot_trend: TrendType  # progressing / stable / regressing

    pace_improvement: Literal["yes", "no", "unclear"]  # Темп прогрессирует?


@dataclass
class AdherenceMetrics:
    """Дисциплина выполнения плана"""
    missed_rate_pct: float  # Процент пропущенных тренировок
    overdone_rate_pct: float  # Процент перевыполнения >120%
    plan_completion_pct: float  # Процент выполненного плана


@dataclass
class Diagnosis:
    """Диагностика состояния"""
    status: StatusType  # progressing / stable / mild_fatigue / overreaching / danger
    confidence: Literal["high", "medium", "low"]
    flags: List[str]  # ["easy_hr_rising", "rhr_elevated", "pain_reported"]


@dataclass
class Recommendation:
    """Рекомендация по адаптации"""
    action: Literal["continue", "hold", "reduce_10", "reduce_25", "deload_week", "rest_day"]
    reason: str  # Понятное объяснение
    max_weekly_km: Optional[float] = None  # Если action = increase, ограничение


@dataclass
class RunnerState:
    """
    Единый объект состояния бегуна за последние 4 недели

    Обновляется раз в неделю и служит основой для всех решений по адаптации.
    Переход от "событие → реакция" к "тренд → диагноз → адаптация".
    """
    period: str  # "last_4_weeks"

    volume: VolumeMetrics
    intensity: IntensityMetrics
    response: ResponseMetrics
    progress: ProgressMetrics
    adherence: AdherenceMetrics
    diagnosis: Diagnosis
    recommendation: Recommendation

    def to_dict(self) -> Dict[str, Any]:
        """Конвертировать в словарь для сериализации"""
        return asdict(self)

    def get_simple_status(self) -> Dict[str, str]:
        """
        Упрощённый статус для beginner (без перегруза данными)

        Returns:
            {icon, message, detail}
        """
        SIMPLE_STATUS = {
            "progressing": {
                "icon": "🟢",
                "message": "Отличная форма! Продолжаем.",
                "detail": "Прогресс стабильный, тело адаптируется"
            },
            "stable": {
                "icon": "🟡",
                "message": "Всё в порядке. Держим темп.",
                "detail": "Стабильное состояние, продолжаем работу"
            },
            "mild_fatigue": {
                "icon": "🟠",
                "message": "Нужен отдых. Снижаем нагрузку.",
                "detail": "Признаки лёгкой усталости, даём телу восстановиться"
            },
            "overreaching": {
                "icon": "🔴",
                "message": "Стоп! Разгрузочная неделя.",
                "detail": "Перегрузка. Недельный отдых критичен"
            },
            "danger": {
                "icon": "🚨",
                "message": "ВНИМАНИЕ! Полный отдых.",
                "detail": "Опасность травмы или перетренированности"
            }
        }

        return SIMPLE_STATUS[self.diagnosis.status]


class RunnerStateCalculator:
    """Расчёт состояния бегуна за последние 4 недели"""

    def __init__(self, user_id: int):
        """
        Args:
            user_id: ID пользователя
        """
        self.user_id = user_id
        self.WEEKS = 4  # Анализируем последние 4 недели

    def calculate(self, as_of_date: Optional[date] = None) -> RunnerState:
        """
        Расчёт состояния бегуна на указанную дату

        Args:
            as_of_date: Дата, на которую рассчитывается состояние (по умолчанию сегодня)

        Returns:
            RunnerState объект
        """
        if as_of_date is None:
            as_of_date = date.today()

        # Период анализа: 4 недели назад от as_of_date
        start_date = as_of_date - timedelta(days=self.WEEKS * 7)

        logger.info(f"Calculating RunnerState for user {self.user_id}: {start_date} → {as_of_date}")

        # Получаем данные за период
        trainings = db.get_trainings_for_period(self.user_id, start_date, as_of_date)
        wellness_surveys = db.get_wellness_for_period(self.user_id, start_date, as_of_date)
        user = db.get_user_by_telegram_id(self.user_id)

        # Расчёт метрик
        volume = self._calculate_volume(trainings, start_date, as_of_date)
        intensity = self._calculate_intensity(trainings)
        response = self._calculate_response(trainings, wellness_surveys, user)
        progress = self._calculate_progress(trainings, user)
        adherence = self._calculate_adherence(trainings, start_date, as_of_date)

        # Диагностика
        diagnosis = self._diagnose(volume, intensity, response, progress, adherence)

        # Рекомендация
        recommendation = self._recommend(diagnosis, volume, response)

        return RunnerState(
            period="last_4_weeks",
            volume=volume,
            intensity=intensity,
            response=response,
            progress=progress,
            adherence=adherence,
            diagnosis=diagnosis,
            recommendation=recommendation
        )

    def _calculate_volume(self, trainings: List[Training], start_date: date, end_date: date) -> VolumeMetrics:
        """
        Расчёт метрик объёма за 4 недели

        Args:
            trainings: Список тренировок
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            VolumeMetrics
        """
        if not trainings:
            return VolumeMetrics(
                avg_weekly_km=0.0,
                baseline_weekly_km=0.0,
                trend="stable",
                max_weekly_km=0.0
            )

        # Группируем по неделям
        weeks_km = {}
        for t in trainings:
            if t.distance_km:
                week_start = t.date - timedelta(days=t.date.weekday())
                weeks_km[week_start] = weeks_km.get(week_start, 0) + t.distance_km

        if not weeks_km:
            return VolumeMetrics(
                avg_weekly_km=0.0,
                baseline_weekly_km=0.0,
                trend="stable",
                max_weekly_km=0.0
            )

        # Средний недельный объём
        avg_weekly_km = sum(weeks_km.values()) / len(weeks_km)

        # Базовый уровень = средний за 4-8 недель назад (если есть данные)
        # Для простоты: baseline = avg_weekly_km (можно улучшить позже)
        baseline_weekly_km = avg_weekly_km

        # Максимальный недельный объём
        max_weekly_km = max(weeks_km.values())

        # Тренд: сравниваем первую и вторую половину периода
        sorted_weeks = sorted(weeks_km.items())
        if len(sorted_weeks) >= 2:
            first_half = sum(v for _, v in sorted_weeks[:len(sorted_weeks)//2])
            second_half = sum(v for _, v in sorted_weeks[len(sorted_weeks)//2:])

            if second_half > first_half * 1.10:
                trend: TrendType = "growing"
            elif second_half < first_half * 0.90:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return VolumeMetrics(
            avg_weekly_km=round(avg_weekly_km, 1),
            baseline_weekly_km=round(baseline_weekly_km, 1),
            trend=trend,
            max_weekly_km=round(max_weekly_km, 1)
        )

    def _calculate_intensity(self, trainings: List[Training]) -> IntensityMetrics:
        """
        Расчёт метрик интенсивности (по МИНУТАМ, не по дням!)

        Критично: 80/20 должна считаться по фактическому времени в зонах,
        а не по количеству тренировок.

        Args:
            trainings: Список тренировок

        Returns:
            IntensityMetrics
        """
        if not trainings:
            return IntensityMetrics(
                intense_minutes_week=0,
                total_minutes_week=0,
                actual_ratio=0.0,
                target_ratio="15-20%",
                status="ok"
            )

        intense_minutes = 0
        total_minutes = 0

        # Типы интенсивных тренировок
        intense_types = {'tempo', 'intervals', 'threshold', 'race'}

        for t in trainings:
            if t.duration_min:
                total_minutes += t.duration_min

                # Если тренировка интенсивная - считаем её минуты
                if t.type in intense_types:
                    # Если есть hr_zones, считаем только время в Z4/Z5
                    if t.hr_zones and isinstance(t.hr_zones, dict):
                        # hr_zones = {"Z1": 10, "Z2": 20, "Z3": 5, "Z4": 15, "Z5": 5}
                        intense_minutes += t.hr_zones.get('Z4', 0) + t.hr_zones.get('Z5', 0)
                    else:
                        # Нет данных по зонам - предполагаем что 60% времени было интенсивным
                        # (разминка + заминка ~40%)
                        intense_minutes += int(t.duration_min * 0.6)

        # Средние за неделю (делим на количество недель)
        weeks_count = len(set((t.date - timedelta(days=t.date.weekday())).isocalendar()[:2] for t in trainings))
        weeks_count = max(weeks_count, 1)

        intense_minutes_week = int(intense_minutes / weeks_count)
        total_minutes_week = int(total_minutes / weeks_count)

        # Соотношение
        if total_minutes_week > 0:
            actual_ratio = intense_minutes_week / total_minutes_week
        else:
            actual_ratio = 0.0

        # Статус: целевое соотношение 15-20% для BASE/BUILD
        if actual_ratio < 0.10:
            status: Literal["ok", "too_low", "too_high"] = "too_low"
        elif actual_ratio > 0.25:
            status = "too_high"
        else:
            status = "ok"

        return IntensityMetrics(
            intense_minutes_week=intense_minutes_week,
            total_minutes_week=total_minutes_week,
            actual_ratio=round(actual_ratio, 3),
            target_ratio="15-20%",
            status=status
        )

    def _calculate_response(self, trainings: List[Training], wellness_surveys: List[WellnessSurvey], user) -> ResponseMetrics:
        """
        Расчёт реакции организма на нагрузку

        Ключевой метод: отслеживает ПАТТЕРНЫ (тренды), а не разовые события.

        Args:
            trainings: Список тренировок
            wellness_surveys: Опросы самочувствия
            user: Пользователь (для baseline)

        Returns:
            ResponseMetrics
        """
        # === EASY HR TREND ===
        easy_trainings = [t for t in trainings if t.type == 'easy' and t.avg_hr]

        if easy_trainings:
            # Группируем по неделям
            weeks = {}
            for t in easy_trainings:
                week_num = t.date.isocalendar()[1]
                if week_num not in weeks:
                    weeks[week_num] = []
                weeks[week_num].append(t.avg_hr)

            # Средний HR по неделям
            weekly_avg_hr = {week: sum(hrs)/len(hrs) for week, hrs in weeks.items()}
            sorted_weeks = sorted(weekly_avg_hr.items())

            # Baseline = первая неделя или среднее за первые 2 недели
            if len(sorted_weeks) >= 2:
                easy_hr_baseline = int((sorted_weeks[0][1] + sorted_weeks[1][1]) / 2)
            else:
                easy_hr_baseline = int(sorted_weeks[0][1]) if sorted_weeks else None

            # Current = последняя неделя
            easy_hr_current = int(sorted_weeks[-1][1]) if sorted_weeks else None

            # Delta
            if easy_hr_baseline and easy_hr_current:
                easy_hr_delta_pct = round((easy_hr_current - easy_hr_baseline) / easy_hr_baseline * 100, 1)
            else:
                easy_hr_delta_pct = None

            # Тренд: проверяем сколько недель подряд растёт
            if len(sorted_weeks) >= 3 and easy_hr_baseline:
                last_3 = sorted_weeks[-3:]
                rising_count = 0
                for week_hr in last_3:
                    if week_hr[1] > easy_hr_baseline * 1.03:  # >3% выше baseline
                        rising_count += 1

                if rising_count >= 3:
                    easy_hr_trend: HRTrendType = "rising_3_weeks"
                elif rising_count >= 2:
                    easy_hr_trend = "rising_2_weeks"
                elif rising_count >= 1:
                    easy_hr_trend = "rising_1_week"
                else:
                    easy_hr_trend = "stable"
            else:
                easy_hr_trend = "stable"
        else:
            easy_hr_baseline = None
            easy_hr_current = None
            easy_hr_delta_pct = None
            easy_hr_trend = "stable"

        # === LONG RUN HR DRIFT ===
        long_trainings = [t for t in trainings if t.type == 'long' and t.avg_hr and t.max_hr]
        if long_trainings:
            # Дрейф = (max_hr - avg_hr) / avg_hr * 100
            drifts = [(t.max_hr - t.avg_hr) / t.avg_hr * 100 for t in long_trainings]
            long_hr_drift_avg_pct = round(sum(drifts) / len(drifts), 1)
        else:
            long_hr_drift_avg_pct = None

        # === RHR (Resting Heart Rate) ===
        rhr_data = [s for s in wellness_surveys if s.rhr]

        if len(rhr_data) >= 7:  # Минимум неделя данных
            # Группируем по неделям
            from datetime import timedelta
            weeks_rhr = {}
            for s in rhr_data:
                week_start = s.date - timedelta(days=s.date.weekday())
                if week_start not in weeks_rhr:
                    weeks_rhr[week_start] = []
                weeks_rhr[week_start].append(s.rhr)

            sorted_weeks = sorted(weeks_rhr.items())

            # Baseline = среднее за первые 2 недели (если есть)
            if len(sorted_weeks) >= 2:
                first_two_weeks = sorted_weeks[:2]
                all_baseline_rhr = [rhr for _, rhrs in first_two_weeks for rhr in rhrs]
                rhr_baseline = int(sum(all_baseline_rhr) / len(all_baseline_rhr))
            else:
                rhr_baseline = int(sum(sorted_weeks[0][1]) / len(sorted_weeks[0][1]))

            # Current = среднее за последнюю неделю
            last_week_rhrs = sorted_weeks[-1][1]
            rhr_current = int(sum(last_week_rhrs) / len(last_week_rhrs))

            # Delta
            rhr_delta = rhr_current - rhr_baseline

            # Status: +5-7 = warning, +8+ = critical
            if rhr_delta >= 8:
                rhr_status: RHRStatusType = "critical"
            elif rhr_delta >= 5:
                rhr_status = "warning"
            else:
                rhr_status = "ok"
        else:
            rhr_baseline = None
            rhr_current = None
            rhr_delta = None
            rhr_status = "ok"

        # === WELLNESS ===
        if wellness_surveys:
            # Средняя оценка самочувствия (1=усталость, 2=норма, 3=отлично)
            wellness_ratings = [s.wellness_rating for s in wellness_surveys if s.wellness_rating]
            wellness_avg = round(sum(wellness_ratings) / len(wellness_ratings), 1) if wellness_ratings else None

            # Средняя оценка сна (bad=1, ok=2, good=3)
            sleep_map = {"bad": 1, "ok": 2, "good": 3}
            sleep_scores = [sleep_map.get(s.sleep_quality, 2) for s in wellness_surveys if s.sleep_quality]
            sleep_avg = round(sum(sleep_scores) / len(sleep_scores), 1) if sleep_scores else None
        else:
            wellness_avg = None
            sleep_avg = None

        return ResponseMetrics(
            easy_hr_baseline=easy_hr_baseline,
            easy_hr_current=easy_hr_current,
            easy_hr_delta_pct=easy_hr_delta_pct,
            easy_hr_trend=easy_hr_trend,
            long_hr_drift_avg_pct=long_hr_drift_avg_pct,
            rhr_baseline=rhr_baseline,
            rhr_current=rhr_current,
            rhr_delta=rhr_delta,
            rhr_status=rhr_status,
            wellness_avg=wellness_avg,
            sleep_avg=sleep_avg
        )

    def _calculate_progress(self, trainings: List[Training], user) -> ProgressMetrics:
        """
        Расчёт прогресса

        Отслеживает изменение VDOT и темпа за 4 недели.

        Args:
            trainings: Список тренировок
            user: Пользователь

        Returns:
            ProgressMetrics
        """
        # VDOT: используем историю для отслеживания прогресса
        from datetime import timedelta, date
        four_weeks_ago = date.today() - timedelta(days=28)

        vdot_history = db.get_vdot_history(self.user_id, start_date=four_weeks_ago)

        if len(vdot_history) >= 2:
            # Сортируем по дате (get_vdot_history возвращает desc, нужен asc)
            vdot_history = sorted(vdot_history, key=lambda h: h.date)

            vdot_4w_ago = vdot_history[0].vdot
            vdot_current = vdot_history[-1].vdot
            vdot_delta = round(vdot_current - vdot_4w_ago, 1)

            if vdot_delta > 0.5:
                vdot_trend: TrendType = "progressing"
            elif vdot_delta < -0.5:
                vdot_trend = "declining"
            else:
                vdot_trend = "stable"
        else:
            # Fallback на текущий VDOT из user
            vdot_current = user.vdot if user else None
            vdot_4w_ago = vdot_current
            vdot_delta = None
            vdot_trend = "stable"

        # Темп прогрессирует? Сравниваем первую и вторую половину периода
        if len(trainings) >= 4:
            first_half = trainings[:len(trainings)//2]
            second_half = trainings[len(trainings)//2:]

            # Средний темп (если есть данные)
            def avg_pace_sec(ts):
                paces = []
                for t in ts:
                    if t.avg_pace:
                        # avg_pace = "5:30" -> 5*60+30 = 330 секунд
                        parts = t.avg_pace.split(':')
                        if len(parts) == 2:
                            pace_sec = int(parts[0]) * 60 + int(parts[1])
                            paces.append(pace_sec)
                return sum(paces) / len(paces) if paces else None

            first_pace = avg_pace_sec(first_half)
            second_pace = avg_pace_sec(second_half)

            if first_pace and second_pace:
                # Улучшение = темп стал быстрее (меньше секунд)
                if second_pace < first_pace * 0.95:  # >5% быстрее
                    pace_improvement: Literal["yes", "no", "unclear"] = "yes"
                elif second_pace > first_pace * 1.05:  # >5% медленнее
                    pace_improvement = "no"
                else:
                    pace_improvement = "unclear"
            else:
                pace_improvement = "unclear"
        else:
            pace_improvement = "unclear"

        return ProgressMetrics(
            vdot_4w_ago=vdot_4w_ago,
            vdot_current=vdot_current,
            vdot_delta=vdot_delta,
            vdot_trend=vdot_trend,
            pace_improvement=pace_improvement
        )

    def _calculate_adherence(self, trainings: List[Training], start_date: date, end_date: date) -> AdherenceMetrics:
        """
        Расчёт дисциплины выполнения плана

        Args:
            trainings: Список тренировок
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            AdherenceMetrics
        """
        # Получаем плановые тренировки за период
        plans = db.get_plan_for_period(self.user_id, start_date, end_date)

        if not plans:
            return AdherenceMetrics(
                missed_rate_pct=0.0,
                overdone_rate_pct=0.0,
                plan_completion_pct=100.0
            )

        # Сопоставляем план и факт по датам
        plan_by_date = {p.date: p for p in plans}
        actual_by_date = {t.date: t for t in trainings}

        missed_count = 0
        overdone_count = 0
        completed_count = 0

        for plan_date, plan in plan_by_date.items():
            actual = actual_by_date.get(plan_date)

            if not actual:
                # Пропуск
                missed_count += 1
            else:
                completed_count += 1

                # Перевыполнение? (>120% по расстоянию или времени)
                if plan.distance_km and actual.distance_km:
                    if actual.distance_km > plan.distance_km * 1.2:
                        overdone_count += 1
                elif plan.duration_min and actual.duration_min:
                    if actual.duration_min > plan.duration_min * 1.2:
                        overdone_count += 1

        total_planned = len(plans)
        missed_rate_pct = round((missed_count / total_planned * 100), 1) if total_planned > 0 else 0.0
        overdone_rate_pct = round((overdone_count / total_planned * 100), 1) if total_planned > 0 else 0.0
        plan_completion_pct = round((completed_count / total_planned * 100), 1) if total_planned > 0 else 100.0

        return AdherenceMetrics(
            missed_rate_pct=missed_rate_pct,
            overdone_rate_pct=overdone_rate_pct,
            plan_completion_pct=plan_completion_pct
        )

    def _diagnose(
        self,
        volume: VolumeMetrics,
        intensity: IntensityMetrics,
        response: ResponseMetrics,
        progress: ProgressMetrics,
        adherence: AdherenceMetrics
    ) -> Diagnosis:
        """
        Диагностика состояния на основе всех метрик

        Decision Stack (Safety First - БЫСТРАЯ реакция):
        1. ОПАСНОСТЬ: RHR critical, easy_hr rising 3 weeks → DANGER (полный отдых)
        2. ПЕРЕГРУЗКА: easy_hr rising 2 weeks → OVERREACHING (deload -25%)
        3. УСТАЛОСТЬ: easy_hr rising 1 week + wellness < 6 → MILD_FATIGUE (reduce -10%)
        4. ПРОГРЕСС: vdot растёт, wellness хороший → PROGRESSING
        5. СТАБИЛЬНО: по умолчанию → STABLE
        """
        flags = []

        # Уровень 1: ОПАСНОСТЬ (3 недели - критично)
        if response.rhr_status == "critical":
            flags.append("rhr_critical")
            return Diagnosis(status="danger", confidence="high", flags=flags)

        if response.easy_hr_trend in ["rising_3_weeks", "critical"]:
            flags.append("easy_hr_rising_3_weeks")
            return Diagnosis(status="danger", confidence="high", flags=flags)

        # Уровень 2: ПЕРЕГРУЗКА (2 недели - DELOAD немедленно)
        if response.easy_hr_trend == "rising_2_weeks":
            flags.append("easy_hr_rising_2_weeks")
            return Diagnosis(status="overreaching", confidence="high", flags=flags)

        # Уровень 3: УСТАЛОСТЬ (1 неделя + низкое самочувствие)
        if response.easy_hr_trend == "rising_1_week":
            if response.wellness_avg and response.wellness_avg < 6:
                flags.append("easy_hr_rising_1_week")
                flags.append("wellness_low")
                return Diagnosis(status="mild_fatigue", confidence="high", flags=flags)

        # Уровень 4: ПРОГРЕСС
        if progress.vdot_trend == "progressing" and response.wellness_avg and response.wellness_avg >= 7:
            return Diagnosis(status="progressing", confidence="high", flags=flags)

        # По умолчанию: стабильно
        return Diagnosis(status="stable", confidence="medium", flags=flags)

    def _recommend(self, diagnosis: Diagnosis, volume: VolumeMetrics, response: ResponseMetrics) -> Recommendation:
        """
        Рекомендация на основе диагноза (Safety First)
        """
        if diagnosis.status == "danger":
            return Recommendation(
                action="rest_day",
                reason="Критические показатели - полный отдых"
            )

        if diagnosis.status == "overreaching":
            return Recommendation(
                action="deload_week",
                reason="Перегрузка - разгрузочная неделя (-25% объёма)"
            )

        if diagnosis.status == "mild_fatigue":
            return Recommendation(
                action="reduce_10",
                reason="Лёгкая усталость - снижаем нагрузку на 10%"
            )

        if diagnosis.status == "progressing":
            # Safety First: рост не более 10% от baseline
            safe_max = volume.baseline_weekly_km * 1.10
            return Recommendation(
                action="continue",
                reason="Прогресс стабильный, можно продолжать",
                max_weekly_km=safe_max
            )

        # stable
        return Recommendation(
            action="hold",
            reason="Удерживаем текущий уровень"
        )


def create_runner_state_calculator(user_id: int) -> RunnerStateCalculator:
    """
    Создать калькулятор состояния бегуна

    Args:
        user_id: ID пользователя

    Returns:
        RunnerStateCalculator
    """
    return RunnerStateCalculator(user_id)
