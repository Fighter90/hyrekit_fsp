"""Демо-данные HyreKit.

Создаёт два демонстрационных аккаунта и наполняет банк кандидатов, чтобы
кабинет работодателя был живым с первого входа:

* `candidate@hyrekit.ru` — кандидат без теста, проходит сценарий с нуля;
* `employer@hyrekit.ru` — работодатель с компанией, вакансиями и заданиями;
* 120 синтетических кандидатов по всем направлениям. Их результаты получены
  симуляцией прохождения теста (`app.assessment.simulate`), а достижения ФСП —
  из эмулятора реестра, поэтому категории и рейтинги согласованы с методикой.

Сидирование идемпотентно: повторный запуск ничего не дублирует.
Запуск вручную: `python -m app.core.seed`.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.assessment import engine
from app.assessment.simulate import simulate
from app.auth.models import User, UserRole
from app.candidates.models import DEFAULT_PRIVACY, CandidateProfile, ConsentEvent
from app.candidates.service import CONSENT_VERSION, utcnow
from app.catalog.data import GRADE_CODES, GRADE_ORDER, SPEC_BY_CODE, SPEC_CODES, category_code
from app.challenges.models import Challenge
from app.core.database import get_session_factory
from app.core.security import hash_password
from app.employers.models import Company, Vacancy
from app.fsp.provider import get_provider

logger = logging.getLogger(__name__)

DEMO_PASSWORD = 'HyreKit2026'  # noqa: S105 — публичный демо-пароль из README
CANDIDATE_EMAIL = 'candidate@hyrekit.ru'
EMPLOYER_EMAIL = 'employer@hyrekit.ru'
SYNTHETIC_COUNT = 120

FIRST_M = ['Артём', 'Максим', 'Иван', 'Егор', 'Кирилл', 'Матвей', 'Тимофей', 'Роман', 'Глеб', 'Лев']
FIRST_F = ['Алиса', 'Полина', 'Варвара', 'Ксения', 'Дарья', 'Вера', 'Милана', 'Ульяна', 'Ева', 'Таисия']
LAST = ['Орлов', 'Волков', 'Зайцев', 'Белов', 'Громов', 'Ершов', 'Комаров', 'Лосев', 'Миронов', 'Титов']
CITIES = ['Москва', 'Санкт-Петербург', 'Казань', 'Новосибирск', 'Екатеринбург', 'Нижний Новгород', 'Томск']
SOFT = ['коммуникация', 'командная работа', 'самоорганизация', 'наставничество', 'ответственность']
ROLES = {
    'backend': ['Backend-разработчик', 'Python-разработчик', 'Go-разработчик'],
    'frontend': ['Frontend-разработчик', 'React-разработчик'],
    'data': ['Data Scientist', 'ML-инженер', 'Аналитик данных'],
    'devops': ['DevOps-инженер', 'SRE-инженер'],
    'qa': ['QA-инженер', 'Инженер по автоматизации тестирования'],
    'security': ['Специалист по ИБ', 'Пентестер'],
}
SALARY = {'intern': 50_000, 'junior': 100_000, 'middle': 200_000, 'senior': 320_000, 'lead': 420_000}
YEARS = {'intern': 0, 'junior': 1, 'middle': 3, 'senior': 5, 'lead': 8}

VACANCIES = [
    {
        'title': 'Python backend-разработчик (платёжный шлюз)',
        'description': 'Развиваем платёжный шлюз на FastAPI и PostgreSQL, очереди на Kafka, кэш в Redis. '
        'Нужен опыт проектирования API и работы с транзакциями.',
        'team_description': 'Команда платформы, 6 человек, релизы каждую неделю.',
        'specialization': 'backend',
        'grade_min': 'middle',
        'grade_max': 'senior',
        'stack': ['Python', 'FastAPI', 'PostgreSQL', 'Redis', 'Kafka'],
        'salary_from': 220_000,
        'salary_to': 330_000,
        'work_format': 'hybrid',
        'city': 'Москва',
    },
    {
        'title': 'Frontend-разработчик React (личный кабинет)',
        'description': 'Делаем личный кабинет клиента на React и TypeScript, сборка на Vite. '
        'Важны аккуратная вёрстка и внимание к доступности.',
        'team_description': 'Продуктовая команда, дизайнер и два фронтендера.',
        'specialization': 'frontend',
        'grade_min': 'junior',
        'grade_max': 'middle',
        'stack': ['TypeScript', 'React', 'Vite', 'CSS'],
        'salary_from': 120_000,
        'salary_to': 210_000,
        'work_format': 'remote',
        'city': None,
    },
    {
        'title': 'DevOps-инженер (Kubernetes)',
        'description': 'Поддерживаем кластеры Kubernetes, инфраструктура описана в Terraform, '
        'мониторинг на Prometheus. Нужен уверенный Linux.',
        'team_description': 'Платформенная команда из 4 инженеров.',
        'specialization': 'devops',
        'grade_min': 'middle',
        'grade_max': 'lead',
        'stack': ['Linux', 'Docker', 'Kubernetes', 'Terraform', 'Prometheus'],
        'salary_from': 230_000,
        'salary_to': 380_000,
        'work_format': 'hybrid',
        'city': 'Санкт-Петербург',
    },
]

CHALLENGES = [
    {
        'title': 'Идемпотентный платёж',
        'description': 'Опишите, как сделать эндпоинт создания платежа идемпотентным: '
        'какой ключ, где хранить, что вернуть при повторе.',
        'specialization': 'backend',
        'days': 14,
    },
    {
        'title': 'Медленный список на React',
        'description': 'Список из 10 000 строк тормозит при вводе в фильтр. Предложите три способа ускорить.',
        'specialization': 'frontend',
        'days': 10,
    },
]


async def _user(session: AsyncSession, email: str, name: str, role: UserRole) -> tuple[User, bool]:
    existing = (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if existing:
        return existing, False
    user = User(email=email, hashed_password=hash_password(DEMO_PASSWORD), full_name=name, role=role, is_verified=True)
    session.add(user)
    await session.flush()
    return user, True


def _true_ability(rng: random.Random, grade: str) -> float:
    """Истинная способность около середины коридора грейда."""
    return engine.cut(grade) + 0.5 + rng.gauss(0, 0.45)


async def _synthetic(session: AsyncSession, index: int, rng: random.Random, hash_: str) -> None:
    spec = SPEC_CODES[index % len(SPEC_CODES)]
    grade = rng.choices(GRADE_CODES, weights=[1, 3, 4, 3, 1])[0]
    female = rng.random() < 0.4
    first = rng.choice(FIRST_F if female else FIRST_M)
    last = rng.choice(LAST) + ('а' if female else '')
    user = User(
        email=f'talent{index + 1:02d}@demo.hyrekit.ru',
        hashed_password=hash_,
        full_name=f'{first} {last}',
        role=UserRole.CANDIDATE,
        is_verified=True,
    )
    session.add(user)
    await session.flush()

    attempt = simulate(spec, grade, _true_ability(rng, grade), rng)
    # Если тест не сдан, кандидат пересдаёт уровнем ниже — как подсказывает система.
    tested = grade
    while not attempt['passed'] and GRADE_ORDER[tested] > 0:
        tested = GRADE_CODES[GRADE_ORDER[tested] - 1]
        attempt = simulate(spec, tested, _true_ability(rng, grade), rng)
    now = utcnow()
    hints = SPEC_BY_CODE[spec]['stack_hints']
    stack = rng.sample(hints, k=min(len(hints), rng.randint(3, 5)))
    has_fsp = rng.random() < 0.65
    fsp_id = f'FSP-{rng.randint(10_000, 99_999)}' if has_fsp else None
    salary = int(SALARY[tested] * rng.uniform(0.85, 1.2) // 5000 * 5000)
    privacy = dict(DEFAULT_PRIVACY)
    privacy['show_full_name'] = rng.random() < 0.7
    profile = CandidateProfile(
        user_id=user.id,
        full_name=user.full_name,
        city=rng.choice(CITIES),
        telegram=f'@{last.lower()}_{index + 1}',
        contact_email=user.email,
        phone=f'+7 9{rng.randint(10, 99)} {rng.randint(100, 999)}-{rng.randint(10, 99)}-{rng.randint(10, 99)}',
        headline=rng.choice(ROLES[spec]),
        about='Синтетический профиль для демонстрации подбора.',
        industry=rng.choice(['fintech', 'ecommerce', 'gov', 'telecom', 'it_services']),
        specialization=spec,
        declared_grade=grade,
        experience_years=max(0.0, YEARS[tested] + round(rng.uniform(-0.5, 1.5), 1)),
        stack=stack,
        roles=[rng.choice(ROLES[spec])],
        soft_skills=rng.sample(SOFT, k=2),
        salary_from=salary,
        salary_to=int(salary * 1.25 // 5000 * 5000),
        work_format=rng.choice(['office', 'hybrid', 'remote']),
        grade=tested if attempt['passed'] else None,
        category=category_code(spec, tested) if attempt['passed'] else None,
        test_score=attempt['score'] if attempt['passed'] else None,
        ability=attempt['ability'] if attempt['passed'] else None,
        grade_changed_at=now - timedelta(days=rng.randint(5, 120)),
        last_activity_at=now - timedelta(days=rng.randint(0, 150)),
        fsp_id=fsp_id,
        fsp_snapshot=get_provider().fetch(fsp_id) if fsp_id else None,
        privacy=privacy,
        consent_given_at=now - timedelta(days=rng.randint(1, 60)),
    )
    session.add(profile)
    await session.flush()
    session.add(
        ConsentEvent(
            profile_id=profile.id,
            version=CONSENT_VERSION,
            action='given',
            created_at=profile.consent_given_at,
            updated_at=profile.consent_given_at,
        )
    )


async def seed_demo(session: AsyncSession) -> None:
    """Создать демо-аккаунты и банк кандидатов (идемпотентно)."""
    rng = random.Random(2026)
    await _user(session, CANDIDATE_EMAIL, 'Демо Кандидат', UserRole.CANDIDATE)
    employer, created = await _user(session, EMPLOYER_EMAIL, 'Демо Работодатель', UserRole.EMPLOYER)

    if created:
        company = Company(
            owner_id=employer.id,
            name='ТехноПлатформа',
            industry='fintech',
            description='Демо-компания: финтех-платформа, ищем инженеров в команды платежей и инфраструктуры.',
            website='https://hyrekit.ru',
            contact_email=EMPLOYER_EMAIL,
            city='Москва',
        )
        session.add(company)
        await session.flush()
        for v in VACANCIES:
            session.add(Vacancy(company_id=company.id, is_published=True, **v))
        for c in CHALLENGES:
            session.add(
                Challenge(
                    company_id=company.id,
                    title=c['title'],
                    description=c['description'],
                    specialization=c['specialization'],
                    due_at=utcnow() + timedelta(days=c['days']),
                )
            )

    have = (await session.execute(select(User.id).where(User.email.like('talent%@demo.hyrekit.ru')))).all()
    if not have:
        hash_ = hash_password(DEMO_PASSWORD)
        for i in range(SYNTHETIC_COUNT):
            await _synthetic(session, i, rng, hash_)
    await session.commit()
    logger.info('Демо-данные готовы: %s, %s / %s', CANDIDATE_EMAIL, EMPLOYER_EMAIL, DEMO_PASSWORD)


async def run() -> None:
    async with get_session_factory()() as session:
        try:
            await seed_demo(session)
        except IntegrityError:
            # Несколько воркеров uvicorn стартуют одновременно; данные уже создал соседний.
            await session.rollback()
            logger.info('Демо-данные уже создаёт другой процесс, пропускаем')


def run_seed() -> None:
    """Точка входа для CLI: python -m app.core.seed."""
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())


if __name__ == '__main__':
    run_seed()
