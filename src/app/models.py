"""Импорт всех ORM-моделей: нужен Alembic и create_all, чтобы метаданные были полными."""

from app.arena.models import ArenaParticipant, ArenaRating, ArenaRound, ArenaSubmission
from app.assessment.models import AssessmentAttempt
from app.auth.models import User
from app.candidates.models import CandidateProfile, ConsentEvent
from app.challenges.models import Challenge, ChallengeSubmission
from app.employers.models import Company, Favorite, Vacancy
from app.hiring.models import Application, Invitation

__all__ = [
    'Application',
    'ArenaParticipant',
    'ArenaRating',
    'ArenaRound',
    'ArenaSubmission',
    'AssessmentAttempt',
    'CandidateProfile',
    'Challenge',
    'ChallengeSubmission',
    'Company',
    'ConsentEvent',
    'Favorite',
    'Invitation',
    'User',
    'Vacancy',
]
