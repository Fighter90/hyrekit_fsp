"""Бизнес-логика профиля кандидата: анкета, рейтинг, карточка для работодателя."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment.engine import cut
from app.auth.models import User
from app.candidates.models import DEFAULT_PRIVACY, CandidateProfile, ConsentEvent
from app.catalog.data import GRADE_COOLDOWN_DAYS, category_title
from app.fsp.provider import summarize

RATING_WEIGHTS = {'test': 0.65, 'fsp': 0.25, 'freshness': 0.10}
# Версия текста согласия на обработку и публикацию профиля (раздел 4 политики конфиденциальности).
# При изменении текста — поднять версию; в журнале остаётся, на какую версию кандидат соглашался.
CONSENT_VERSION = '2026-10-10'


def utcnow() -> datetime:
    """Naive UTC — единый формат хранения дат в БД."""
    return datetime.now(UTC).replace(tzinfo=None)


async def _find_profile(session: AsyncSession, user_id: Any) -> CandidateProfile | None:
    stmt = select(CandidateProfile).where(CandidateProfile.user_id == user_id)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_or_create_profile(session: AsyncSession, user: User) -> CandidateProfile:
    """Профиль кандидата; создаётся при первом обращении.

    Кабинет запрашивает несколько эндпоинтов параллельно, поэтому вставка идёт
    в точке сохранения: проигравший гонку запрос ловит нарушение уникальности
    user_id и читает уже созданный профиль.
    """
    profile = await _find_profile(session, user.id)
    if profile is None:
        profile = CandidateProfile(
            user_id=user.id,
            full_name=user.full_name,
            contact_email=user.email,
            city=user.city,
            phone=user.phone,
            stack=[],
            roles=[],
            soft_skills=[],
            privacy=dict(DEFAULT_PRIVACY),
        )
        try:
            async with session.begin_nested():
                session.add(profile)
        except IntegrityError:
            profile = await _find_profile(session, user.id)
            if profile is None:
                raise
    return profile


def fsp_summary(profile: CandidateProfile) -> dict[str, Any] | None:
    if not profile.fsp_snapshot:
        return None
    summary = summarize(profile.fsp_snapshot, profile.specialization)
    return {**summary, 'verified': bool(profile.fsp_sub)} if summary else None


def test_component(profile: CandidateProfile) -> float:
    """Сила результата теста относительно порога грейда, 0..100."""
    if profile.ability is None or profile.grade is None:
        return 0.0
    return 100 / (1 + math.exp(-1.5 * (profile.ability - cut(profile.grade))))


def freshness(profile: CandidateProfile, now: datetime | None = None) -> float:
    """Актуальность профиля: 100 в течение 30 дней после активности, затем линейно до 0 к 180 дням."""
    if profile.last_activity_at is None:
        return 0.0
    days = ((now or utcnow()) - profile.last_activity_at).days
    if days <= 30:
        return 100.0
    return max(0.0, 100 * (1 - (days - 30) / 150))


def rating_breakdown(profile: CandidateProfile) -> dict[str, float]:
    fsp = fsp_summary(profile)
    return {
        'test': round(test_component(profile), 1),
        'fsp': float(fsp['score']) if fsp else 0.0,
        'freshness': round(freshness(profile), 1),
    }


def rating(profile: CandidateProfile) -> float | None:
    """Ранг внутри категории: тест (65 %) + ФСП (25 %) + актуальность (10 %)."""
    if profile.grade is None:
        return None
    b = rating_breakdown(profile)
    return round(sum(RATING_WEIGHTS[k] * b[k] for k in RATING_WEIGHTS), 1)


def completeness(profile: CandidateProfile) -> int:
    checks = [
        profile.full_name,
        profile.city,
        profile.headline,
        profile.about,
        profile.specialization,
        profile.stack,
        profile.experience_years is not None,
        profile.salary_from,
        profile.work_format,
        profile.grade,
        profile.consent_given_at,
        profile.phone or profile.telegram or profile.contact_email,
    ]
    return round(100 * sum(bool(c) for c in checks) / len(checks))


def is_visible(profile: CandidateProfile) -> bool:
    return bool(profile.category and profile.consent_given_at)


def next_grade_change_at(profile: CandidateProfile) -> datetime | None:
    if profile.grade_changed_at is None:
        return None
    return profile.grade_changed_at + timedelta(days=GRADE_COOLDOWN_DAYS)


def to_out(profile: CandidateProfile) -> dict[str, Any]:
    return {
        'id': profile.id,
        'user_id': profile.user_id,
        'full_name': profile.full_name,
        'city': profile.city,
        'phone': profile.phone,
        'telegram': profile.telegram,
        'contact_email': profile.contact_email,
        'headline': profile.headline,
        'about': profile.about,
        'industry': profile.industry,
        'specialization': profile.specialization,
        'declared_grade': profile.declared_grade,
        'grade': profile.grade,
        'category': profile.category,
        'category_title': category_title(profile.specialization, profile.grade),
        'stack': profile.stack or [],
        'roles': profile.roles or [],
        'soft_skills': profile.soft_skills or [],
        'experience_years': profile.experience_years,
        'salary_from': profile.salary_from,
        'salary_to': profile.salary_to,
        'work_format': profile.work_format,
        'test_score': profile.test_score,
        'rating': rating(profile),
        'grade_changed_at': profile.grade_changed_at,
        'next_grade_change_at': next_grade_change_at(profile),
        'fsp_id': profile.fsp_id,
        'fsp': fsp_summary(profile),
        'privacy': {**DEFAULT_PRIVACY, **(profile.privacy or {})},
        'consent_given_at': profile.consent_given_at,
        'is_visible': is_visible(profile),
        'is_guest': bool(profile.is_guest),
        'completeness': completeness(profile),
        'created_at': profile.created_at,
        'updated_at': profile.updated_at,
    }


def public_alias(profile_id: UUID) -> str:
    return f'Кандидат #{str(profile_id).replace("-", "")[:4].upper()}'


def to_card(
    profile: CandidateProfile,
    *,
    contacts_unlocked: bool = False,
    invitation_status: str | None = None,
) -> dict[str, Any]:
    """Карточка кандидата для работодателя с учётом приватности.

    Контакты раскрываются только после принятия приглашения или отклика
    кандидата (ТЗ, п. 2.2). Имя, город, ФСП и зарплата — по настройкам.
    """
    privacy = {**DEFAULT_PRIVACY, **(profile.privacy or {})}
    show_name = privacy['show_full_name'] or contacts_unlocked
    fsp = fsp_summary(profile) if privacy['show_fsp'] else None
    return {
        'id': profile.id,
        'display_name': (profile.full_name if show_name and profile.full_name else public_alias(profile.id)),
        'headline': profile.headline,
        'city': profile.city if privacy['show_city'] else None,
        'category': profile.category,
        'category_title': category_title(profile.specialization, profile.grade),
        'specialization': profile.specialization,
        'grade': profile.grade,
        'stack': profile.stack or [],
        'roles': profile.roles or [],
        'soft_skills': profile.soft_skills or [],
        'experience_years': profile.experience_years,
        'about': profile.about,
        'test_score': profile.test_score,
        'rating': rating(profile),
        'fsp': fsp if fsp and fsp['has_history'] else None,
        'salary_from': profile.salary_from if privacy['show_salary'] else None,
        'salary_to': profile.salary_to if privacy['show_salary'] else None,
        'work_format': profile.work_format,
        'contacts': (
            {'email': profile.contact_email, 'phone': profile.phone, 'telegram': profile.telegram}
            if contacts_unlocked
            else None
        ),
        'contacts_unlocked': contacts_unlocked,
        'invitation_status': invitation_status,
    }


def set_consent(session: AsyncSession, profile: CandidateProfile, given: bool) -> None:
    """Выдать или отозвать согласие на публикацию и записать событие в журнал.

    Повтор того же состояния журнал не засоряет: событие пишется только при смене.
    """
    if bool(profile.consent_given_at) == given:
        return
    now = utcnow()
    profile.consent_given_at = now if given else None
    session.add(
        ConsentEvent(
            profile_id=profile.id,
            kind='publication',
            version=CONSENT_VERSION,
            action='given' if given else 'revoked',
            created_at=now,
            updated_at=now,
        )
    )


async def consent_history(session: AsyncSession, profile: CandidateProfile) -> list[dict[str, Any]]:
    stmt = select(ConsentEvent).where(ConsentEvent.profile_id == profile.id).order_by(ConsentEvent.created_at.desc())
    return [
        {'kind': e.kind, 'version': e.version, 'action': e.action, 'at': e.created_at}
        for e in (await session.execute(stmt)).scalars()
    ]


def touch(profile: CandidateProfile) -> None:
    profile.last_activity_at = utcnow()


# ── Гость экспресс-теста для жюри (FSP-32) ───────────────────────────────────
GUEST_EMAIL_DOMAIN = 'guest.hyrekit.ru'
GUEST_INDUSTRY = 'it_services'
GUEST_EXPERIENCE_YEARS = {'intern': 0.0, 'junior': 1.0, 'middle': 3.0, 'senior': 5.0, 'lead': 8.0}


async def create_guest(session: AsyncSession, *, specialization: str, grade: str) -> User:
    """Отдельный подтверждённый кандидат на каждый запуск: эксперты не мешают друг другу."""
    import secrets

    from app.auth.models import UserRole
    from app.catalog.data import SPEC_BY_CODE
    from app.core.security import hash_password

    tag = secrets.token_hex(6)
    spec = SPEC_BY_CODE[specialization]
    user = User(
        email=f'guest-{tag}@{GUEST_EMAIL_DOMAIN}',
        hashed_password=hash_password(secrets.token_urlsafe(24)),
        full_name=f'Гость жюри {tag[:4].upper()}',
        role=UserRole.CANDIDATE,
        is_verified=True,
    )
    session.add(user)
    await session.flush()
    now = utcnow()
    session.add(
        CandidateProfile(
            user_id=user.id,
            full_name=user.full_name,
            headline=f'{spec["title"]} · экспресс-тест жюри',
            industry=GUEST_INDUSTRY,
            specialization=specialization,
            declared_grade=grade,
            experience_years=GUEST_EXPERIENCE_YEARS[grade],
            stack=list(spec['stack_hints'][:4]),
            roles=[],
            soft_skills=[],
            privacy=dict(DEFAULT_PRIVACY),
            consent_given_at=now,
            last_activity_at=now,
            is_guest=True,
        )
    )
    await session.flush()
    return user
