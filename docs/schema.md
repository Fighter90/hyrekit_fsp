# Схема данных

PostgreSQL 16 в Docker и на площадке, SQLite при локальном запуске и в тестах. Схема строится миграциями Alembic (`alembic/versions/`, применяются `alembic upgrade head`) из моделей SQLAlchemy (`src/app/*/models.py`):

| Миграция | Что делает |
| -- | -- |
| `0001_initial_schema` | Исходная схема: пользователи, профили, попытки, компании, вакансии, приглашения, отклики, короткие задания |
| `0002_consents_favorites` | `consent_events` и `employer_favorites` (FSP-25, FSP-45) |
| `0003_express_test` | `candidate_profiles.is_guest`, `assessment_attempts.mode` (FSP-32) |
| `0004_strict_grade_cut` | Перенос сохранённых θ на шкалу со строгим порогом, без новых полей (FSP-61) |
| `0005_code_arena` | Таблицы Code Arena: `arena_rounds`, `arena_participants`, `arena_submissions`, `arena_ratings` (FSP-36…FSP-42) |
| `0006_item_calibration` | `item_calibration` — статус семейств заданий (FSP-33) |
| `0007_fsp_oidc` | `candidate_profiles.fsp_sub` — подтверждение ФСП ID входом (FSP-20) |

Идентификаторы — UUID, время — UTC без часового пояса.

```mermaid
erDiagram
  users ||--o| candidate_profiles : "кандидат"
  users ||--o| companies : "работодатель"
  candidate_profiles ||--o{ assessment_attempts : ""
  companies ||--o{ vacancies : ""
  companies ||--o{ invitations : ""
  candidate_profiles ||--o{ invitations : ""
  vacancies ||--o{ applications : ""
  candidate_profiles ||--o{ applications : ""
  companies ||--o{ challenges : ""
  challenges ||--o{ challenge_submissions : ""
  candidate_profiles ||--o{ challenge_submissions : ""
  candidate_profiles ||--o{ consent_events : ""
  companies ||--o{ employer_favorites : ""
  candidate_profiles ||--o{ employer_favorites : ""
  arena_rounds ||--o{ arena_participants : ""
  candidate_profiles ||--o{ arena_participants : ""
  arena_participants ||--o{ arena_submissions : ""
  arena_rounds ||--o{ arena_submissions : ""
  candidate_profiles ||--o{ arena_submissions : ""
  candidate_profiles ||--o| arena_ratings : ""
  companies ||--o{ arena_rounds : "спонсор"
  item_calibration {
    varchar family
    varchar status
    boolean excluded
  }
```

## Что где лежит

| Таблица | Содержимое |
| -- | -- |
| `users` | Учётная запись, роль `candidate` или `employer`, подтверждение почты |
| `candidate_profiles` | Анкета, стек, грейд и категория, θ и балл теста, ФСП ID, `sub` провайдера ФСП ID и снимок достижений, настройки приватности, дата согласия, признак гостя экспресс-теста |
| `assessment_attempts` | Режим (`full` или `express`), план попытки (семейства, уровни, зёрна), ответы, срок, результат и решение по грейду |
| `companies` | Профиль компании работодателя, одна на пользователя |
| `vacancies` | Потребность: специализация, диапазон грейдов, стек, вилка, публикация |
| `invitations` | Приглашение компании кандидату: предложение, вилка, способ связи, статус |
| `applications` | Отклик кандидата на вакансию и его статус |
| `challenges`, `challenge_submissions` | Короткие задания и ответы кандидатов с оценкой |
| `consent_events` | Журнал выдачи и отзыва согласия с редакцией текста |
| `employer_favorites` | Избранное компании: кандидат, при желании потребность и заметка |
| `arena_rounds` | Раунд Code Arena: открытый или по расписанию, задачи, заморозка таблицы, компания-организатор |
| `arena_participants` | Участие кандидата в раунде: личный таймер, решённые задачи, штраф, рейтинг до и после |
| `arena_submissions` | Отправка решения: язык, код, вердикт и тесты, время и память, разбор, сигналы списывания |
| `arena_ratings` | Рейтинг Arena кандидата по Glicko-2: рейтинг, отклонение, волатильность, история |
| `item_calibration` | Статус семейства заданий по последней калибровке: показы, доля верных, дрейф, z, сдвиг трудности, исключение |

Правильные ответы теста в базе не хранятся: план попытки содержит только семейство, уровень и зерно, ответ вычисляется генератором при проверке.

## Таблицы

### `users`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `email` | varchar | unique, index, not null |
| `hashed_password` | varchar | not null |
| `full_name` | varchar |  |
| `role` | varchar | not null |
| `is_active` | boolean | not null |
| `is_verified` | boolean | not null |
| `phone` | varchar |  |
| `city` | varchar |  |
| `avatar_url` | varchar |  |
| `deleted_at` | datetime |  |
| `scheduled_deletion` | datetime |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `candidate_profiles`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `user_id` | uuid | FK → users.id, unique, index, not null |
| `full_name` | varchar |  |
| `city` | varchar |  |
| `phone` | varchar |  |
| `telegram` | varchar |  |
| `contact_email` | varchar |  |
| `headline` | varchar |  |
| `about` | text |  |
| `industry` | varchar |  |
| `specialization` | varchar | index |
| `declared_grade` | varchar |  |
| `experience_years` | float |  |
| `stack` | json | not null |
| `roles` | json | not null |
| `soft_skills` | json | not null |
| `salary_from` | integer |  |
| `salary_to` | integer |  |
| `work_format` | varchar |  |
| `grade` | varchar | index |
| `category` | varchar | index |
| `test_score` | float |  |
| `ability` | float |  |
| `grade_changed_at` | datetime |  |
| `last_activity_at` | datetime |  |
| `fsp_id` | varchar | index |
| `fsp_snapshot` | json |  |
| `fsp_sub` | varchar | unique, index |
| `privacy` | json | not null |
| `consent_given_at` | datetime |  |
| `is_guest` | boolean | not null |
| `resume_text` | text |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `companies`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `owner_id` | uuid | FK → users.id, unique, index, not null |
| `name` | varchar | not null |
| `industry` | varchar |  |
| `description` | text |  |
| `website` | varchar |  |
| `contact_email` | varchar |  |
| `contact_phone` | varchar |  |
| `city` | varchar |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `assessment_attempts`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `specialization` | varchar | not null |
| `grade` | varchar | not null |
| `mode` | varchar | not null |
| `plan` | json | not null |
| `answers` | json | not null |
| `started_at` | datetime | not null |
| `deadline_at` | datetime | not null |
| `finished_at` | datetime |  |
| `score` | float |  |
| `ability` | float |  |
| `correct` | integer |  |
| `total` | integer |  |
| `passed` | boolean |  |
| `assigned_grade` | varchar |  |
| `suggestion` | varchar |  |
| `by_topic` | json |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `challenges`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `company_id` | uuid | FK → companies.id, index, not null |
| `title` | varchar | not null |
| `description` | text | not null |
| `specialization` | varchar | index, not null |
| `due_at` | datetime |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `vacancies`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `company_id` | uuid | FK → companies.id, index, not null |
| `title` | varchar | not null |
| `description` | text | not null |
| `team_description` | text |  |
| `specialization` | varchar | index, not null |
| `grade_min` | varchar | not null |
| `grade_max` | varchar | not null |
| `stack` | json | not null |
| `salary_from` | integer | not null |
| `salary_to` | integer | not null |
| `work_format` | varchar | not null |
| `city` | varchar |  |
| `is_published` | boolean | index, not null |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `applications`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `vacancy_id` | uuid | FK → vacancies.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `message` | text |  |
| `status` | varchar | index, not null |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `challenge_submissions`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `challenge_id` | uuid | FK → challenges.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `answer` | text | not null |
| `score` | float |  |
| `feedback` | text |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `invitations`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `company_id` | uuid | FK → companies.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `vacancy_id` | uuid | FK → vacancies.id |
| `title` | varchar | not null |
| `message` | text | not null |
| `salary_from` | integer | not null |
| `salary_to` | integer | not null |
| `contact` | varchar | not null |
| `status` | varchar | index, not null |
| `decline_reason` | text |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `consent_events`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `kind` | varchar | not null |
| `version` | varchar | not null |
| `action` | varchar | not null |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `employer_favorites`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `company_id` | uuid | FK → companies.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `vacancy_id` | uuid | FK → vacancies.id |
| `note` | varchar |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

Уникальность: одна запись на пару `company_id` + `profile_id`.

### `arena_rounds`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `title` | varchar | not null |
| `description` | text |  |
| `specialization` | varchar | index |
| `starts_at` | datetime | index, not null |
| `ends_at` | datetime |  |
| `duration_minutes` | integer | not null |
| `is_open` | boolean | not null |
| `freeze_minutes` | integer | not null |
| `problems` | json | not null |
| `company_id` | uuid | FK → companies.id, index |
| `prize` | varchar |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `arena_participants`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `round_id` | uuid | FK → arena_rounds.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `started_at` | datetime | not null |
| `ends_at` | datetime | not null |
| `finished_at` | datetime |  |
| `solved` | integer | not null |
| `penalty` | integer | not null |
| `rated_at` | datetime |  |
| `rating_before` | float |  |
| `rating_after` | float |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `arena_submissions`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `participant_id` | uuid | FK → arena_participants.id, index, not null |
| `round_id` | uuid | FK → arena_rounds.id, index, not null |
| `profile_id` | uuid | FK → candidate_profiles.id, index, not null |
| `problem` | varchar | not null |
| `language` | varchar | not null |
| `code` | text | not null |
| `status` | varchar | index, not null |
| `verdict` | varchar |  |
| `passed` | integer | not null |
| `total` | integer | not null |
| `time_ms` | integer |  |
| `memory_kb` | integer |  |
| `tests` | json | not null |
| `message` | text |  |
| `feedback` | json |  |
| `signals` | json | not null |
| `similar_to` | uuid | FK → arena_submissions.id |
| `minute` | integer | not null |
| `judged_at` | datetime |  |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `arena_ratings`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `profile_id` | uuid | FK → candidate_profiles.id, unique, index, not null |
| `rating` | float | not null |
| `rd` | float | not null |
| `volatility` | float | not null |
| `rounds` | integer | not null |
| `solved` | integer | not null |
| `last_round_at` | datetime |  |
| `history` | json | not null |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

### `item_calibration`

| Поле | Тип | Ограничения |
| -- | -- | -- |
| `family` | varchar | unique, index, not null |
| `topic` | varchar | not null |
| `shows` | integer | not null |
| `correct` | integer | not null |
| `solve_rate` | float | not null |
| `expected_rate` | float | not null |
| `drift` | float | not null |
| `z` | float | not null |
| `offset` | float | not null |
| `status` | varchar | not null |
| `excluded` | boolean | index, not null |
| `calibrated_at` | datetime | not null |
| `id` | uuid | PK |
| `created_at` | datetime | not null |
| `updated_at` | datetime | not null |

Уникальность: одно участие на пару `round_id` + `profile_id` в `arena_participants`, один рейтинг на профиль в `arena_ratings`, одна запись на семейство в `item_calibration`.
