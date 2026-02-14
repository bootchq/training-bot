"""Обработчики команд бота (mixins)"""
from .onboarding import OnboardingMixin
from .ai_chat import AIChatMixin
from .sync import SyncMixin

__all__ = ['OnboardingMixin', 'AIChatMixin', 'SyncMixin']
