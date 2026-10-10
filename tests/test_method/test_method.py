"""Юнит-тесты методики: банк заданий, оценка θ, решение по грейду, подбор, ФСП."""

from __future__ import annotations

import random

import pytest

from app.assessment import bank, engine
from app.assessment.simulate import correct_answer, simulate, wrong_answer
from app.catalog.data import GRADE_CODES, GRADE_ORDER, SPEC_BY_CODE, SPEC_CODES
from app.fsp.provider import MockFspProvider, summarize
from app.matching.service import ability_fit, extract_stack, grade_fit, norm


@pytest.mark.parametrize('family', sorted(bank.FAMILIES))
def test_every_family_generates_checkable_items(family: str) -> None:
    for level in range(1, 6):
        item = bank.generate(family, 42, level)
        assert item.level == level
        assert bank.check(item, correct_answer(item))
        assert not bank.check(item, wrong_answer(item))
        assert not bank.check(item, None)


def test_same_seed_same_item_other_seed_other_item() -> None:
    fam = sorted(bank.FAMILIES)[0]
    assert bank.generate(fam, 1, 3) == bank.generate(fam, 1, 3)
    stems = {bank.generate(fam, s, 3).stem for s in range(20)}
    assert len(stems) > 1


@pytest.mark.parametrize('spec', SPEC_CODES)
def test_blueprint_covers_all_spec_topics(spec: str) -> None:
    plan = engine.build_blueprint(spec, 'middle', rng_seed=7)
    assert len(plan) == 10
    assert {p.id for p in plan} == {f'q{i}' for i in range(1, 11)}


def test_ability_is_monotonic_in_correct_answers() -> None:
    bs = [engine.difficulty(lvl) for lvl in (2, 3, 3, 4, 4, 3, 2, 3, 4, 3)]
    thetas = [engine.estimate_ability([(b, i < k) for i, b in enumerate(bs)]) for k in range(11)]
    assert thetas == sorted(thetas)
    assert thetas[0] < engine.cut('junior') < engine.cut('senior') < thetas[-1]


def test_decide_never_lowers_existing_grade() -> None:
    d = engine.decide(engine.cut('middle') + 0.1, 'middle', 'senior')
    assert d.assigned_grade == 'senior'
    fail = engine.decide(engine.cut('senior') - 1, 'senior', 'middle')
    assert fail.passed is False
    assert fail.assigned_grade == 'middle'
    assert fail.suggestion == 'retry_lower'


def test_decide_suggests_higher_grade_for_strong_result() -> None:
    assert engine.decide(engine.cut('senior') + 0.5, 'middle', None).suggestion == 'try_higher'
    assert engine.decide(engine.cut('middle') + 0.2, 'middle', None).suggestion == 'keep'


def test_simulated_strong_candidate_passes_weak_fails() -> None:
    rng = random.Random(1)
    strong = [simulate('backend', 'junior', 2.5, rng)['passed'] for _ in range(20)]
    weak = [simulate('backend', 'senior', -2.5, rng)['passed'] for _ in range(20)]
    assert sum(strong) >= 18
    assert sum(weak) <= 2


def test_grade_and_ability_fit() -> None:
    assert grade_fit('middle', 'junior', 'senior') == 100
    assert grade_fit('junior', 'middle', 'senior') == 55
    assert grade_fit('lead', 'middle', 'senior') == 70
    assert grade_fit('intern', 'senior', 'lead') == 0
    inside = ability_fit(engine.cut('middle') + 0.5, 'junior', 'middle')
    above = ability_fit(engine.cut('lead'), 'junior', 'middle')
    assert inside == 100
    assert above < 50
    assert ability_fit(None, 'junior', 'middle') == 0


def test_stack_normalization_and_extraction() -> None:
    assert norm('K8s') == 'kubernetes'
    assert norm('Postgres') == 'postgresql'
    found = extract_stack('Сервис на FastAPI, база PostgreSQL, очереди Kafka')
    assert {'FastAPI', 'PostgreSQL', 'Kafka'} <= set(found)


def test_fsp_provider_deterministic_and_no_history_case() -> None:
    p = MockFspProvider()
    assert p.fetch('FSP-12345') == p.fetch('FSP-12345')
    assert p.fetch('bad-id') is None
    empty = summarize(p.fetch('FSP-12340'), 'backend')
    assert empty is not None
    assert empty['has_history'] is False
    assert empty['score'] == 0


def test_fsp_relevant_discipline_weighs_more() -> None:
    raw = {
        'fsp_id': 'FSP-1111',
        'achievements': [
            {
                'event': 'x',
                'discipline': 'информационная безопасность',
                'level': 'всероссийский',
                'place': 1,
                'year': 2026,
                'role': None,
            },
        ],
    }
    assert summarize(raw, 'security')['score'] > summarize(raw, 'frontend')['score']


def test_vacancy_test_topics_follow_stack_and_keep_difficulty() -> None:
    from app.assessment.vacancy import preview, vacancy_topics

    topics = vacancy_topics('backend', ['Python', 'FastAPI', 'PostgreSQL', 'Kafka'])
    codes = [t['topic'] for t in topics]
    assert codes[0] == 'python'
    assert {'sql', 'architecture'} <= set(codes)
    assert len(codes) == 5
    p = preview('backend', 'middle', ['Python', 'PostgreSQL', 'Kafka'])
    a, b = p['variants']
    assert a['difficulty_profile'] == b['difficulty_profile']
    standard = sorted(engine.materialize(x).level for x in engine.build_blueprint('backend', 'middle', rng_seed=3))
    assert a['difficulty_profile'] == standard
    assert [i['stem'] for i in a['items']] != [i['stem'] for i in b['items']]


@pytest.mark.parametrize('grade', GRADE_CODES)
def test_express_blueprint(grade: str) -> None:
    """Экспресс-план: 5 тем × 1 задание на уровне проверяемого грейда (FSP-32)."""
    plan = engine.build_blueprint('backend', grade, rng_seed=7, items_per_topic=engine.EXPRESS_ITEMS_PER_TOPIC)
    assert len(plan) == 5
    assert {p.topic for p in plan} == set(SPEC_BY_CODE['backend']['topics'])
    assert {p.level for p in plan} == {GRADE_ORDER[grade] + 1}
    assert engine.EXPRESS_SECONDS_PER_ITEM * len(plan) <= 300
