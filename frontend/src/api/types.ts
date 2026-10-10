// Типы API v1 — зеркало контракта docs/spec/api.md

export type Role = 'candidate' | 'employer'
export type Grade = 'intern' | 'junior' | 'middle' | 'senior' | 'lead'
export type WorkFormat = 'office' | 'hybrid' | 'remote'

export interface ApiErrorBody {
  error_code?: string
  message?: string
  detail?: unknown
}

export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

/** Регистрация может вернуть сообщение вместо токенов (защита от перебора email). */
export type RegisterResponse = TokenPair | { message: string }

export interface MessageResponse {
  message: string
}

export interface RegisterInput {
  email: string
  password: string
  full_name: string
  role: Role
}

export interface User {
  id: string
  email: string
  full_name: string | null
  role: Role
  is_verified: boolean
  phone: string | null
  city: string | null
  avatar_url: string | null
  created_at: string
  updated_at: string
}

// --- Справочник ---

export interface Specialization {
  code: string
  title: string
  topics: string[]
  /** Подсказки стека — сервер отдаёт сверх контракта, поле необязательное. */
  stack_hints?: string[]
}

export interface GradeInfo {
  code: Grade
  title: string
  order: number
  years: string
}

export interface Catalog {
  specializations: Specialization[]
  grades: GradeInfo[]
  industries: { code: string; title: string }[]
  work_formats: { code: WorkFormat; title: string }[]
  grade_change_cooldown_days: number
}

// --- Кандидат ---

export interface FspAchievement {
  event: string
  discipline: string
  level: string
  place: number | null
  year: number
  role: string | null
  relevant_to: string[]
}

export interface FspSummary {
  fsp_id: string
  athlete_name: string | null
  achievements: FspAchievement[]
  score: number
  has_history: boolean
}

export interface Privacy {
  show_full_name: boolean
  show_city: boolean
  show_fsp: boolean
  show_salary: boolean
}

export interface CandidateProfile {
  id: string
  user_id: string
  full_name: string | null
  city: string | null
  phone: string | null
  telegram: string | null
  contact_email: string | null
  headline: string | null
  about: string | null
  industry: string | null
  specialization: string | null
  declared_grade: Grade | null
  grade: Grade | null
  category: string | null
  category_title: string | null
  stack: string[]
  roles: string[]
  soft_skills: string[]
  experience_years: number | null
  salary_from: number | null
  salary_to: number | null
  work_format: WorkFormat | null
  test_score: number | null
  rating: number | null
  grade_changed_at: string | null
  next_grade_change_at: string | null
  fsp_id: string | null
  fsp: FspSummary | null
  privacy: Privacy
  consent_given_at: string | null
  is_visible: boolean
  completeness: number
  created_at: string
  updated_at: string
}

export type CandidateProfileUpdate = Partial<
  Pick<
    CandidateProfile,
    | 'full_name'
    | 'city'
    | 'phone'
    | 'telegram'
    | 'contact_email'
    | 'headline'
    | 'about'
    | 'industry'
    | 'stack'
    | 'roles'
    | 'soft_skills'
    | 'experience_years'
    | 'salary_from'
    | 'salary_to'
    | 'work_format'
  >
>

export interface CandidateSettingsUpdate {
  privacy?: Partial<Privacy>
  consent?: boolean
  fsp_id?: string | null
}

export interface ResumeParseResult {
  fields: CandidateProfileUpdate
  source: 'gigachat' | 'rules'
  text_length: number
}

// --- Оценка ---

export interface SurveyInput {
  industry: string
  specialization: string
  experience_years: number
  stack: string[]
  declared_grade: Grade
}

export interface Eligibility {
  declared_grade: Grade | null
  current_grade: Grade | null
  allowed_grades: Grade[]
  locked_until: string | null
  reason: string | null
}

export type ItemKind = 'single' | 'multi' | 'number'
export type AnswerValue = string | string[]

export interface AttemptItem {
  id: string
  topic: string
  difficulty: number
  kind: ItemKind
  stem: string
  code: string | null
  options: string[]
}

export interface AttemptView {
  id: string
  grade: Grade
  specialization: string
  started_at: string
  deadline_at: string
  items: AttemptItem[]
  answers: Record<string, AnswerValue>
}

export type Suggestion = 'keep' | 'retry_lower' | 'try_higher'

export interface AttemptResult {
  id: string
  grade_tested: Grade
  specialization: string
  score: number
  ability: number
  correct: number
  total: number
  passed: boolean
  assigned_grade: Grade | null
  suggestion: Suggestion
  by_topic: { topic: string; correct: number; total: number }[]
  finished_at: string
}

// --- Приглашения, вакансии, отклики ---

export type InvitationStatus = 'sent' | 'viewed' | 'accepted' | 'declined'
export type ApplicationStatus = InvitationStatus

export interface CompanyBrief {
  id: string
  name: string
  industry: string | null
  website: string | null
}

export interface CandidateCard {
  id: string
  display_name: string
  headline: string | null
  city: string | null
  category: string
  category_title: string
  specialization: string
  grade: Grade
  stack: string[]
  roles: string[]
  soft_skills: string[]
  experience_years: number | null
  test_score: number | null
  rating: number | null
  fsp: FspSummary | null
  salary_from: number | null
  salary_to: number | null
  work_format: string | null
  contacts: { email: string | null; phone: string | null; telegram: string | null } | null
  contacts_unlocked: boolean
  invitation_status: InvitationStatus | null
}

export interface Invitation {
  id: string
  status: InvitationStatus
  company: CompanyBrief
  vacancy_id: string | null
  title: string
  message: string
  salary_from: number
  salary_to: number
  contact: string
  candidate: CandidateCard
  created_at: string
  updated_at: string
}

export interface VacancyInput {
  title: string
  description: string
  team_description?: string
  specialization: string
  grade_min: Grade
  grade_max: Grade
  stack: string[]
  salary_from: number
  salary_to: number
  work_format: WorkFormat
  city?: string
  is_published: boolean
}

export interface Vacancy extends VacancyInput {
  id: string
  company: { id: string; name: string }
  applications_count: number
  created_at: string
  updated_at: string
}

export interface Application {
  id: string
  status: ApplicationStatus
  vacancy: Vacancy
  message: string | null
  candidate: CandidateCard
  created_at: string
  updated_at: string
}

export interface Challenge {
  id: string
  title: string
  description: string
  specialization: string
  company_name: string
  due_at: string | null
  submitted: boolean
}

/** Тело создания задания работодателем — в контракте не описано, берём поля Challenge. */
export interface ChallengeInput {
  title: string
  description: string
  specialization: string
  due_at: string | null
}

export interface ChallengeSubmission {
  id: string
  challenge_id: string
  answer: string
  score: number | null
  feedback: string | null
  created_at: string
}

// --- Работодатель ---

export interface Company {
  id: string
  name: string
  industry: string | null
  description: string | null
  website: string | null
  contact_email: string | null
  contact_phone: string | null
  city: string | null
}

export type CompanyUpdate = Partial<Omit<Company, 'id'>>

export interface CategoryStat {
  category: string
  title: string
  specialization: string
  grade: Grade
  count: number
  with_fsp: number
}

export interface MatchBreakdown {
  category: number
  stack: number
  test: number
  fsp: number
  freshness: number
}

export interface MatchItem {
  candidate: CandidateCard
  score: number
  breakdown: MatchBreakdown
  reasons: string[]
  missing_stack: string[]
}

export interface MatchResult {
  vacancy_id: string
  total: number
  categories: CategoryStat[]
  items: MatchItem[]
}

export interface CandidatePage {
  total: number
  items: CandidateCard[]
}

export interface InvitationInput {
  candidate_id: string
  vacancy_id?: string | null
  title: string
  message: string
  salary_from: number
  salary_to: number
  contact: string
}

export interface MatchQuery {
  grade?: Grade | ''
  stack?: string
  has_fsp?: boolean
  limit?: number
}

export interface CandidateQuery {
  specialization?: string
  grade?: Grade | ''
  category?: string
  stack?: string
  has_fsp?: boolean
  q?: string
  limit?: number
  offset?: number
}

export interface VacancyQuery {
  specialization?: string
  grade?: Grade | ''
  q?: string
}

/** Тест под вакансию: темы из стека и варианты равной сложности. */
export interface VacancyAssessment {
  specialization: string
  grade: Grade
  grade_level: number
  seconds: number
  topics: { topic: string; title: string; reason: string }[]
  variants: { items: AttemptItem[]; difficulty_profile: number[] }[]
}
