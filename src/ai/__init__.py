"""AI модули"""
from .consultant import consultant, TrainingConsultant
from .workout_recommender import workout_recommender, WorkoutRecommender
from .recovery_detector import recovery_detector, RecoveryDetector
from .weekly_coach import weekly_coach, WeeklyCoach

__all__ = [
    'consultant',
    'TrainingConsultant',
    'workout_recommender',
    'WorkoutRecommender',
    'recovery_detector',
    'RecoveryDetector',
    'weekly_coach',
    'WeeklyCoach',
]
