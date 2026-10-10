# Контракт API (v1)

Базовый путь: `/api/v1`. Формат: JSON, UTF-8. Авторизация: `Authorization: Bearer <access_token>`.
Полная машиночитаемая спецификация генерируется FastAPI: `/openapi.json`, Swagger UI — `/docs`.

Ошибки возвращаются единым форматом:

```json
{ "error_code": "NOT_FOUND", "message": "Человекочитаемое описание", "detail": null }
```

Коды: `400` валидация, `401` нет токена, `403` чужая роль или чужой ресурс, `404` нет объекта,
`409` конфликт состояния (например, смена грейда раньше срока), `422` ошибка схемы.

## Роли

`candidate` — кабинет кандидата, `employer` — кабинет работодателя. Роль задаётся при регистрации.
Эндпоинты `/candidate/*` доступны только кандидату, `/employer/*` только работодателю.

---

## Авторизация `/auth`

| Метод | Путь | Тело / ответ |
|---|---|---|
| POST | `/auth/register` | `{email, password, full_name, role}` → `{access_token, refresh_token, token_type}` |
| POST | `/auth/login` | `{email, password}` → токены |
| POST | `/auth/guest` | `{specialization, grade, consent}` → токены гостевого кандидата экспресс-теста; 404 при `GUEST_MODE=false`, 10 запросов в минуту |
| GET | `/auth/fsp/config` | `{enabled, test_provider}`: доступен ли вход через ФСП ID (FSP-20) |
| POST | `/auth/fsp/start` | `{mode: login\|link}` → `{authorize_url}` и HttpOnly-cookie `fsp_oidc` (state, nonce, PKCE, 10 минут); `link` — только вошедший кандидат, иначе 403 |
| POST | `/auth/fsp/callback` | `{code, state}` → `{mode, fsp_id, created, tokens}`; 400 при чужом state или отказе провайдера, 403 если привязку завершает другой пользователь, 409 если участник ФСП уже подтверждён в другом аккаунте |
| POST | `/auth/refresh` | `{refresh_token}` → токены |
| GET | `/auth/verify/{token}` | подтверждение почты; ссылка из письма ведёт на страницу фронтенда `/verify/{token}` |
| POST | `/auth/resend-verification` | повторная отправка письма |
| GET | `/auth/me` | `User` |

```ts
type Role = 'candidate' | 'employer'
interface User { id: string; email: string; full_name: string | null; role: Role;
  is_verified: boolean; phone: string | null; city: string | null; avatar_url: string | null;
  created_at: string; updated_at: string }
```

## Справочник `/catalog`

| GET | `/catalog` | `Catalog` (публичный) |
|---|---|---|

```ts
interface Catalog {
  specializations: { code: string; title: string; topics: string[]; stack_hints: string[] }[]  // backend, frontend, data, devops, qa, security
  grades: { code: Grade; title: string; order: number; years: string }[]
  industries: { code: string; title: string }[]
  work_formats: { code: 'office' | 'hybrid' | 'remote'; title: string }[]
  grade_change_cooldown_days: number   // 90
}
type Grade = 'intern' | 'junior' | 'middle' | 'senior' | 'lead'
```

---

## Кабинет кандидата `/candidate`

### Профиль

| Метод | Путь | Описание |
|---|---|---|
| GET | `/candidate/profile` | свой профиль (создаётся пустым при первом обращении) |
| PUT | `/candidate/profile` | обновить поля анкеты (`CandidateProfileUpdate`) |
| POST | `/candidate/profile/resume` | `multipart/form-data` `file` (PDF/DOCX) → распознанные поля `ResumeParseResult`, профиль дополняется |
| GET | `/candidate/profile/pdf` | стандартизированный PDF-профиль (`application/pdf`) |
| PUT | `/candidate/settings` | приватность, согласие, ФСП ID (`CandidateSettingsUpdate`) |
| GET | `/candidate/consents` | журнал согласий `{current_version, items: {kind, version, action: 'given'|'revoked', at}[]}`, новые сверху |
| GET | `/candidate/fsp` | достижения ФСП по привязанному ID (`FspSummary`) |

```ts
interface CandidateProfile {
  id: string; user_id: string
  full_name: string | null; city: string | null; phone: string | null; telegram: string | null
  contact_email: string | null
  headline: string | null                  // желаемая роль, «Python backend-разработчик»
  about: string | null
  industry: string | null                  // код из catalog.industries
  specialization: string | null            // код из catalog.specializations
  declared_grade: Grade | null             // выбран кандидатом перед тестом
  grade: Grade | null                      // подтверждён тестом
  category: string | null                  // `${specialization}:${grade}`, видна работодателю
  category_title: string | null            // «Backend · Middle»
  stack: string[]; roles: string[]; soft_skills: string[]
  experience_years: number | null
  salary_from: number | null; salary_to: number | null   // рубли
  work_format: 'office' | 'hybrid' | 'remote' | null
  test_score: number | null                // 0..100, последняя оценка
  rating: number | null                    // 0..100, итоговый рейтинг внутри категории
  grade_changed_at: string | null
  next_grade_change_at: string | null      // когда можно сменить грейд
  fsp_id: string | null
  fsp: FspSummary | null
  privacy: { show_full_name: boolean; show_city: boolean; show_fsp: boolean; show_salary: boolean }
  consent_given_at: string | null          // согласие 152-ФЗ; без него профиль не виден работодателям
  is_visible: boolean                      // есть категория + согласие
  completeness: number                     // 0..100
  created_at: string; updated_at: string
}
type CandidateProfileUpdate = Partial<Pick<CandidateProfile,
  'full_name'|'city'|'phone'|'telegram'|'contact_email'|'headline'|'about'|'industry'|'stack'|'roles'|
  'soft_skills'|'experience_years'|'salary_from'|'salary_to'|'work_format'>>
interface CandidateSettingsUpdate {
  privacy?: Partial<CandidateProfile['privacy']>
  consent?: boolean            // true выставляет consent_given_at, false снимает
  fsp_id?: string | null       // привязка/отвязка ФСП ID
}
interface ResumeParseResult { fields: CandidateProfileUpdate; source: 'gigachat' | 'yandexgpt' | 'rules'; text_length: number }
interface FspAchievement { event: string; discipline: string; level: string; place: number | null;
  year: number; role: string | null; relevant_to: string[] }
interface FspSummary { fsp_id: string; athlete_name: string | null; achievements: FspAchievement[];
  score: number /*0..100*/; has_history: boolean }
```

### Опрос и тестирование

| Метод | Путь | Описание |
|---|---|---|
| POST | `/candidate/assessment/survey` | `{industry, specialization, experience_years, stack[], declared_grade}` — опрос + выбор грейда; ответ `CandidateProfile` |
| GET | `/candidate/assessment/eligibility` | `Eligibility` — какие грейды можно сдавать сейчас |
| POST | `/candidate/assessment/start` | `{grade}` → `AttemptView` (задания без правильных ответов) |
| POST | `/candidate/assessment/{attempt_id}/answer` | `{item_id, answer}` → `{saved: true}` |
| POST | `/candidate/assessment/{attempt_id}/finish` | → `AttemptResult` |
| GET | `/candidate/assessment/history` | `AttemptResult[]` |

```ts
interface Eligibility { declared_grade: Grade | null; current_grade: Grade | null
  allowed_grades: Grade[]; locked_until: string | null; reason: string | null }
interface AttemptItem { id: string; topic: string; difficulty: number /*1..5*/; kind: 'single' | 'multi' | 'number'
  stem: string; code: string | null; options: string[] /* пусто для number */ }
interface AttemptView { id: string; grade: Grade; specialization: string; started_at: string
  deadline_at: string; items: AttemptItem[]; answers: Record<string, string | string[]> }
interface AttemptResult { id: string; grade_tested: Grade; specialization: string
  score: number /*0..100*/; ability: number /*theta*/; correct: number; total: number
  passed: boolean; assigned_grade: Grade | null; suggestion: 'keep' | 'retry_lower' | 'try_higher'
  by_topic: { topic: string; correct: number; total: number }[]; finished_at: string }
```

### Приглашения, вакансии, отклики

| Метод | Путь | Описание |
|---|---|---|
| GET | `/candidate/invitations` | `Invitation[]` — только свои |
| POST | `/candidate/invitations/{id}/view` | отметить просмотренным |
| POST | `/candidate/invitations/{id}/accept` | принять — работодатель видит контакты |
| POST | `/candidate/invitations/{id}/decline` | `{reason?}` отклонить |
| GET | `/candidate/vacancies?specialization=&grade=&q=` | опубликованные вакансии `Vacancy[]` |
| POST | `/candidate/vacancies/{id}/apply` | `{message?}` → `Application` |
| GET | `/candidate/applications` | свои отклики `Application[]` |
| GET | `/candidate/challenges` | регулярные короткие задания `Challenge[]` |
| POST | `/candidate/challenges/{id}/submit` | `{answer}` → `ChallengeSubmission` |

```ts
type InvitationStatus = 'sent' | 'viewed' | 'accepted' | 'declined'
interface Invitation { id: string; status: InvitationStatus
  company: { id: string; name: string; industry: string | null; website: string | null }
  vacancy_id: string | null; title: string; message: string
  salary_from: number; salary_to: number; contact: string     // способ связи от работодателя
  candidate: CandidateCard                                    // для работодателя
  created_at: string; updated_at: string }
type ApplicationStatus = 'sent' | 'viewed' | 'accepted' | 'declined'
interface Application { id: string; status: ApplicationStatus; vacancy: Vacancy; message: string | null
  candidate: CandidateCard; created_at: string; updated_at: string }
interface Challenge { id: string; title: string; description: string; specialization: string
  company_name: string; due_at: string | null; submitted: boolean }
interface ChallengeSubmission { id: string; challenge_id: string; answer: string; score: number | null
  feedback: string | null; created_at: string }
```

---

## Кабинет работодателя `/employer`

| Метод | Путь | Описание |
|---|---|---|
| GET/PUT | `/employer/company` | профиль компании `Company` |
| GET | `/employer/vacancies` | свои потребности/вакансии `Vacancy[]` |
| POST | `/employer/vacancies` | создать `VacancyInput` |
| GET/PUT/DELETE | `/employer/vacancies/{id}` | просмотр, редактирование, удаление |
| GET | `/employer/vacancies/{id}/matches?grade=&stack=&has_fsp=&limit=` | подборка `MatchResult` |
| GET | `/employer/vacancies/{id}/assessment` | тест под вакансию: темы из стека и два варианта равной сложности `VacancyAssessment` |
| GET | `/employer/candidates?specialization=&grade=&category=&stack=&has_fsp=&q=&limit=&offset=` | банк кандидатов `CandidatePage` |
| GET | `/employer/candidates/{id}` | карточка кандидата `CandidateCard` (контакты скрыты до согласия) |
| GET | `/employer/categories` | категории с количеством кандидатов `CategoryStat[]` |
| GET | `/employer/favorites?vacancy_id=` | избранное `{candidate: CandidateCard, vacancy_id, note, added_at}[]`; без отозвавших согласие |
| PUT | `/employer/favorites/{profile_id}` | `{vacancy_id?, note?}` → добавить или обновить; 404 для невидимого кандидата |
| DELETE | `/employer/favorites/{profile_id}` | убрать из избранного, 204 |
| POST | `/employer/invitations` | `InvitationInput` → `Invitation` |
| GET | `/employer/invitations` | отправленные приглашения со статусами |
| GET | `/employer/applications` | входящие отклики |
| POST | `/employer/applications/{id}/status` | `{status: 'viewed'|'accepted'|'declined'}` |
| GET/POST | `/employer/challenges` | короткие задания для кандидатов |
| GET | `/employer/challenges/{id}/submissions` | ответы кандидатов |

```ts
interface Company { id: string; name: string; industry: string | null; description: string | null
  website: string | null; contact_email: string | null; contact_phone: string | null; city: string | null }
interface VacancyInput { title: string; description: string; team_description?: string
  specialization: string; grade_min: Grade; grade_max: Grade; stack: string[]
  salary_from: number; salary_to: number           // обязательны, рубли, from <= to
  work_format: 'office' | 'hybrid' | 'remote'; city?: string; is_published: boolean }
interface Vacancy extends VacancyInput { id: string; company: { id: string; name: string }
  applications_count: number; created_at: string; updated_at: string }
interface CandidateCard {
  id: string                     // id профиля
  display_name: string           // ФИО или «Кандидат #A1B2» при скрытом имени
  headline: string | null; city: string | null
  category: string; category_title: string; specialization: string; grade: Grade
  stack: string[]; roles: string[]; soft_skills: string[]; experience_years: number | null
  test_score: number | null; rating: number | null
  fsp: FspSummary | null         // null если скрыто или нет истории
  salary_from: number | null; salary_to: number | null
  work_format: string | null
  contacts: { email: string | null; phone: string | null; telegram: string | null } | null  // null до принятия
  contacts_unlocked: boolean
  invitation_status: InvitationStatus | null   // последнее приглашение от этой компании
  is_favorite?: boolean                        // в шортлисте компании (банк, подборка, карточка)
}
interface MatchItem { candidate: CandidateCard; score: number /*0..100*/
  breakdown: { category: number; stack: number; test: number; fsp: number; freshness: number }
  reasons: string[]              // объяснимость: «Совпадает категория Backend · Middle», «Есть 4 из 5 технологий: …»
  missing_stack: string[] }
interface MatchResult { vacancy_id: string; base_total: number /* до фильтров */; total: number; categories: CategoryStat[]; items: MatchItem[] }
interface CandidatePage { total: number; items: CandidateCard[] }
interface CategoryStat { category: string; title: string; specialization: string; grade: Grade
  count: number; with_fsp: number }
interface VacancyAssessment { specialization: string; grade: Grade; grade_level: number; seconds: number
  topics: { topic: string; title: string; reason: string }[]           // «Стек вакансии: Python, FastAPI»
  variants: { items: AttemptItem[]; difficulty_profile: number[] }[] }  // профили сложности совпадают
interface InvitationInput { candidate_id: string; vacancy_id?: string | null; title: string; message: string
  salary_from: number; salary_to: number; contact: string }
```

## Code Arena `/arena`

Типы — `frontend/src/api/types.ts` (`Arena*`), правила — [fsp-36-code-arena.md](../specs/fsp-36-code-arena.md).

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/arena/sandbox` | все | слои песочницы `{landlock, seccomp, languages, max_parallel, limits}` |
| GET | `/arena/problems` | все | банк задач `ArenaProblemRef[]` |
| GET | `/arena/rounds` | все | раунды `ArenaRound[]`; кандидату — с его участием |
| GET | `/arena/rounds/{id}` | все | раунд, задачи варианта участника, отправки `ArenaRoundDetail` |
| POST | `/arena/rounds/{id}/join` | кандидат | участие, запуск личного таймера; 409 до старта и после конца |
| POST | `/arena/rounds/{id}/run` | кандидат | `{problem, language, code}` → результаты на примерах, не засчитывается; 20 в минуту |
| POST | `/arena/rounds/{id}/submit` | кандидат | `{problem, language, code, signals}` → `{submission, participation}` с вердиктами тестов и разбором; 10 в минуту; 409 после конца времени |
| POST | `/arena/rounds/{id}/finish` | кандидат | завершить досрочно, пересчитать рейтинг |
| GET | `/arena/rounds/{id}/leaderboard` | все | таблица ICPC `ArenaBoard`; у работодателя — статус приглашения |
| GET | `/arena/rounds/{id}/stream` | все | SSE: событие `board` при изменении таблицы |
| GET | `/arena/rounds/{id}/editorial` | все | эталоны и статистика; кандидату — после конца его участия, иначе 403 |
| GET | `/arena/submissions/{id}` | кандидат | своя отправка `ArenaSubmission` |
| GET/PUT | `/arena/me`, `/arena/me/settings` | кандидат | рейтинг, история, место; `{show_arena}` |
| POST | `/arena/rounds` | работодатель | `ArenaRoundInput` → раунд компании, 201 |
| GET | `/arena/top?specialization=&grade=&has_fsp=&min_rating=&limit=` | работодатель | витрина `{total, items: ArenaTopItem[]}` |
| GET | `/arena/candidates/{profile_id}` | работодатель | рейтинг и решения кандидата (решения — если кандидат открыл показ) |

## Тестовый провайдер ФСП ID `/api/v1/fsp-id`

Встроенный OpenID Connect-провайдер, пока Keycloak ФСП недоступен (FSP-20). Подключается, когда `FSP_OIDC_ISSUER` пуст и `FSP_OIDC_MOCK=true`. Путь без префикса `/api/v1` ниже — от корня приложения.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/api/v1/fsp-id/.well-known/openid-configuration` | discovery |
| GET | `/api/v1/fsp-id/authorize` | страница входа: `client_id`, `redirect_uri` (только `{PUBLIC_URL}/fsp-callback`), `response_type=code`, `scope` c `openid`, `state`, `nonce`, `code_challenge`, `code_challenge_method=S256` |
| POST | `/api/v1/fsp-id/authorize` | форма входа: `fsp_id`, `password`, `action=allow\|deny` → 303 на `redirect_uri` с `code` или `error=access_denied` |
| POST | `/api/v1/fsp-id/token` | `grant_type=authorization_code`, `code`, `redirect_uri`, `code_verifier`, клиент через `client_secret_post` или `client_secret_basic` → `{id_token, access_token}`; код одноразовый, 120 секунд |
| GET | `/api/v1/fsp-id/userinfo` | Bearer access-токен → claims участника (`sub`, `fsp_id`, `name`, `email`) |
| GET | `/api/v1/fsp-id/jwks` | `{keys: []}`: id_token подписан HS256 секретом клиента |

## Модели LLM `/llm`

| Метод | Путь | Роль | Описание |
|---|---|---|---|
| GET | `/llm/status` | все вошедшие | `{active, fallback, providers: [{provider, title, configured, ok, error, latency_ms}]}`: `active` — первый ответивший провайдер (`gigachat`, `yandexgpt`) или `null`, тогда `fallback = "rules"`; кэш 5 минут |

## Служебное

| GET | `/health` | `{status: "healthy", version}` |
|---|---|---|
