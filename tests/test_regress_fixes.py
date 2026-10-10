"""Регресс 10.10: склонения в PDF-профиле и сообщениях 404."""

from app.candidates.pdf import years_label
from app.core.exceptions import NotFound


def test_years_label() -> None:
    assert [years_label(x) for x in (1, 3, 6, 11, 21, 22, 1.5)] == [
        '1 год',
        '3 года',
        '6 лет',
        '11 лет',
        '21 год',
        '22 года',
        '1.5 года',
    ]


def test_not_found_gender() -> None:
    assert NotFound('Приглашение').message == 'Приглашение не найдено'
    assert NotFound('Вакансия').message == 'Вакансия не найдена'
    assert NotFound('Отклик').message == 'Отклик не найден'
