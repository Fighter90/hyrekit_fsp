# Справочник направлений, специализаций, грейдов и технологий

Linear: FSP-21 · веха Промежуточная сдача. Пункты ТЗ: 2.

## Цель
Единый словарь, на котором строятся категории, тест и подбор. Коды стабильны и служат ключами категорий.

## Правила и числа
- Грейды: Intern, Junior, Middle, Senior, Lead; порядок 0–4.
- Специализации MVP: Backend, Frontend, Data Science / ML, DevOps / SRE, QA, информационная безопасность.
- У специализации 5 тем теста, подсказки стека и профильные дисциплины ФСП.
- Категория — `специализация:грейд`, заголовок — «Backend · Middle».
- Смена грейда — не чаще раза в 90 дней.

## Критерии приёмки (EARS)
- WHEN клиент запрашивает `GET /catalog` THE SYSTEM SHALL вернуть специализации с темами и подсказками стека, грейды, отрасли, форматы работы и срок смены грейда без авторизации.
- WHEN технология стека вакансии есть в `TECH_TOPICS` THE SYSTEM SHALL сопоставить ей тему теста.

## Интерфейсы
`GET /api/v1/catalog`; `app.catalog.data`: `GRADES`, `SPECIALIZATIONS`, `TOPIC_TITLES`, `TECH_TOPICS`, `category_code`, `category_title`.

## План тестов
`tests/test_flow.py` (каталог в сквозном сценарии), `tests/test_method/test_method.py::test_blueprint_covers_all_spec_topics`.
