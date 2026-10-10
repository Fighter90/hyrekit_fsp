import type {
  ArenaBoard,
  ArenaCandidate,
  ArenaEditorialItem,
  ArenaLanguage,
  ArenaMe,
  ArenaParticipation,
  ArenaProblemRef,
  ArenaRound,
  ArenaRoundDetail,
  ArenaRoundInput,
  ArenaRunResult,
  ArenaSandbox,
  ArenaSubmission,
  ArenaTopItem,
  GuestInput,
  Application,
  ApplicationStatus,
  AttemptResult,
  AttemptView,
  AnswerValue,
  ApiErrorBody,
  CandidateCard,
  ConsentLog,
  FavoriteItem,
  CandidatePage,
  CandidateProfile,
  CandidateProfileUpdate,
  CandidateQuery,
  CandidateSettingsUpdate,
  Catalog,
  CategoryStat,
  Challenge,
  ChallengeInput,
  ChallengeSubmission,
  Company,
  CompanyUpdate,
  Eligibility,
  FspSummary,
  Grade,
  Invitation,
  InvitationInput,
  MatchQuery,
  MatchResult,
  MessageResponse,
  RegisterInput,
  RegisterResponse,
  ResumeParseResult,
  SurveyInput,
  TokenPair,
  User,
  Vacancy,
  VacancyAssessment,
  VacancyInput,
  VacancyQuery,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const ACCESS_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

/** Ошибка API с HTTP-статусом и кодом из единого формата ошибок. */
export class ApiError extends Error {
  status: number
  code: string | null

  constructor(message: string, status: number, code: string | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

type QueryValue = string | number | boolean | null | undefined

/** Собирает query-строку, пропуская пустые значения. */
export function buildQuery(params: Record<string, QueryValue> = {}): string {
  const qs = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue
    qs.append(key, String(value))
  }
  const s = qs.toString()
  return s ? `?${s}` : ''
}

function safeStorage(): Storage | null {
  try {
    return typeof localStorage !== 'undefined' ? localStorage : null
  } catch {
    return null
  }
}

/** Извлекает человекочитаемое сообщение из тела ошибки (включая массив ошибок pydantic). */
export function extractErrorMessage(err: ApiErrorBody | Record<string, unknown>, fallback: string): string {
  const body = err as Record<string, unknown>
  const raw = body.message || body.detail || fallback
  if (typeof raw === 'string') return raw
  if (Array.isArray(raw)) {
    const msgs = raw
      .map((e: unknown) => (e && typeof e === 'object' && typeof (e as { msg?: unknown }).msg === 'string' ? (e as { msg: string }).msg : null))
      .filter(Boolean)
    if (msgs.length > 0) return msgs.join('; ')
  }
  return fallback
}

const STATUS_FALLBACK: Record<number, string> = {
  400: 'Проверьте введённые данные',
  401: 'Требуется вход в аккаунт',
  403: 'Недостаточно прав для этого действия',
  404: 'Не найдено',
  409: 'Действие сейчас недоступно',
  422: 'Ошибка в данных запроса',
  429: 'Слишком много запросов, попробуйте позже',
}

type Body = unknown
interface RequestOptions {
  body?: Body
  form?: FormData
  blob?: boolean
}

export class ApiClient {
  private token: string | null = null
  private base: string
  /** Один общий refresh на все параллельные запросы, получившие 401. */
  private refreshing: Promise<boolean> | null = null
  /** Вызывается, когда сессию не удалось восстановить (refresh не прошёл). */
  onSessionExpired: (() => void) | null = null

  constructor(base: string = API_BASE) {
    this.base = base
  }

  // --- токены ---

  setTokens(pair: Pick<TokenPair, 'access_token'> & { refresh_token?: string }) {
    this.token = pair.access_token
    const s = safeStorage()
    s?.setItem(ACCESS_KEY, pair.access_token)
    if (pair.refresh_token) s?.setItem(REFRESH_KEY, pair.refresh_token)
  }

  clearTokens() {
    this.token = null
    const s = safeStorage()
    s?.removeItem(ACCESS_KEY)
    s?.removeItem(REFRESH_KEY)
  }

  getAccessToken(): string | null {
    return this.token || safeStorage()?.getItem(ACCESS_KEY) || null
  }

  url(path: string): string {
    return `${this.base}${path}`
  }

  private headers(json: boolean): Record<string, string> {
    const h: Record<string, string> = {}
    if (json) h['Content-Type'] = 'application/json'
    const tok = this.getAccessToken()
    if (tok) h['Authorization'] = `Bearer ${tok}`
    return h
  }

  private send(method: string, path: string, opts: RequestOptions): Promise<Response> {
    const isJson = opts.body !== undefined && !opts.form
    return fetch(this.url(path), {
      method,
      headers: this.headers(isJson),
      body: opts.form ? opts.form : isJson ? JSON.stringify(opts.body) : undefined,
    })
  }

  private async request<T>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
    let res = await this.send(method, path, opts)

    // Автоматический refresh при 401 и повтор исходного запроса
    if (res.status === 401 && !path.startsWith('/auth/refresh') && !path.startsWith('/auth/login')) {
      const ok = await this.tryRefresh()
      if (ok) {
        res = await this.send(method, path, opts)
      } else {
        this.onSessionExpired?.()
      }
    }

    if (!res.ok) {
      const err = (await res.json().catch(() => ({}))) as ApiErrorBody
      const fallback = STATUS_FALLBACK[res.status] || res.statusText || 'Ошибка сервера'
      throw new ApiError(extractErrorMessage(err, fallback), res.status, err.error_code ?? null)
    }
    if (opts.blob) return (await res.blob()) as T
    if (res.status === 204) return undefined as T
    const text = await res.text()
    return (text ? JSON.parse(text) : undefined) as T
  }

  private tryRefresh(): Promise<boolean> {
    if (!this.refreshing) {
      this.refreshing = (async () => {
        const rt = safeStorage()?.getItem(REFRESH_KEY)
        if (!rt) return false
        try {
          const data = await this.refresh(rt)
          this.setTokens(data)
          return true
        } catch {
          this.clearTokens()
          return false
        }
      })().finally(() => {
        this.refreshing = null
      })
    }
    return this.refreshing
  }

  // ================= /auth =================

  register(data: RegisterInput) {
    return this.request<RegisterResponse>('POST', '/auth/register', { body: data })
  }
  /** Экспресс-тест для жюри: гостевой кандидат без регистрации */
  guest(data: GuestInput) {
    return this.request<TokenPair>('POST', '/auth/guest', { body: data })
  }
  login(email: string, password: string) {
    return this.request<TokenPair>('POST', '/auth/login', { body: { email, password } })
  }
  refresh(refreshToken: string) {
    return this.request<TokenPair>('POST', '/auth/refresh', { body: { refresh_token: refreshToken } })
  }
  verifyEmail(token: string) {
    return this.request<MessageResponse>('GET', `/auth/verify/${encodeURIComponent(token)}`)
  }
  resendVerification() {
    return this.request<MessageResponse>('POST', '/auth/resend-verification')
  }
  me() {
    return this.request<User>('GET', '/auth/me')
  }
  /** Вне контракта v1, но поддерживается сервером: выход с инвалидацией refresh-токена. */
  logout(refreshToken: string) {
    return this.request<void>('POST', '/auth/logout', { body: { refresh_token: refreshToken } })
  }
  /** Вне контракта v1, но поддерживается сервером: смена пароля. */
  changePassword(current_password: string, new_password: string) {
    return this.request<MessageResponse>('PUT', '/auth/me/password', { body: { current_password, new_password } })
  }

  // ================= /catalog =================

  catalog() {
    return this.request<Catalog>('GET', '/catalog')
  }

  // ================= /candidate =================

  getCandidateProfile() {
    return this.request<CandidateProfile>('GET', '/candidate/profile')
  }
  getConsents() {
    return this.request<ConsentLog>('GET', '/candidate/consents')
  }
  updateCandidateProfile(data: CandidateProfileUpdate) {
    return this.request<CandidateProfile>('PUT', '/candidate/profile', { body: data })
  }
  uploadResume(file: File) {
    const form = new FormData()
    form.append('file', file)
    return this.request<ResumeParseResult>('POST', '/candidate/profile/resume', { form })
  }
  downloadProfilePdf() {
    return this.request<Blob>('GET', '/candidate/profile/pdf', { blob: true })
  }
  updateCandidateSettings(data: CandidateSettingsUpdate) {
    return this.request<CandidateProfile>('PUT', '/candidate/settings', { body: data })
  }
  getFsp() {
    return this.request<FspSummary>('GET', '/candidate/fsp')
  }

  submitSurvey(data: SurveyInput) {
    return this.request<CandidateProfile>('POST', '/candidate/assessment/survey', { body: data })
  }
  getEligibility() {
    return this.request<Eligibility>('GET', '/candidate/assessment/eligibility')
  }
  startAttempt(grade: Grade) {
    return this.request<AttemptView>('POST', '/candidate/assessment/start', { body: { grade } })
  }
  saveAnswer(attemptId: string, itemId: string, answer: AnswerValue) {
    return this.request<{ saved: boolean }>('POST', `/candidate/assessment/${attemptId}/answer`, {
      body: { item_id: itemId, answer },
    })
  }
  finishAttempt(attemptId: string) {
    return this.request<AttemptResult>('POST', `/candidate/assessment/${attemptId}/finish`)
  }
  getAssessmentHistory() {
    return this.request<AttemptResult[]>('GET', '/candidate/assessment/history')
  }

  getCandidateInvitations() {
    return this.request<Invitation[]>('GET', '/candidate/invitations')
  }
  viewInvitation(id: string) {
    return this.request<Invitation>('POST', `/candidate/invitations/${id}/view`)
  }
  acceptInvitation(id: string) {
    return this.request<Invitation>('POST', `/candidate/invitations/${id}/accept`)
  }
  declineInvitation(id: string, reason?: string) {
    return this.request<Invitation>('POST', `/candidate/invitations/${id}/decline`, { body: reason ? { reason } : {} })
  }
  getPublishedVacancies(q: VacancyQuery = {}) {
    return this.request<Vacancy[]>('GET', `/candidate/vacancies${buildQuery({ ...q })}`)
  }
  applyToVacancy(id: string, message?: string) {
    return this.request<Application>('POST', `/candidate/vacancies/${id}/apply`, { body: message ? { message } : {} })
  }
  getCandidateApplications() {
    return this.request<Application[]>('GET', '/candidate/applications')
  }
  getCandidateChallenges() {
    return this.request<Challenge[]>('GET', '/candidate/challenges')
  }
  submitChallenge(id: string, answer: string) {
    return this.request<ChallengeSubmission>('POST', `/candidate/challenges/${id}/submit`, { body: { answer } })
  }

  // ================= /employer =================

  getCompany() {
    return this.request<Company>('GET', '/employer/company')
  }
  updateCompany(data: CompanyUpdate) {
    return this.request<Company>('PUT', '/employer/company', { body: data })
  }
  getEmployerVacancies() {
    return this.request<Vacancy[]>('GET', '/employer/vacancies')
  }
  createVacancy(data: VacancyInput) {
    return this.request<Vacancy>('POST', '/employer/vacancies', { body: data })
  }
  getVacancy(id: string) {
    return this.request<Vacancy>('GET', `/employer/vacancies/${id}`)
  }
  updateVacancy(id: string, data: VacancyInput) {
    return this.request<Vacancy>('PUT', `/employer/vacancies/${id}`, { body: data })
  }
  deleteVacancy(id: string) {
    return this.request<void>('DELETE', `/employer/vacancies/${id}`)
  }
  getMatches(vacancyId: string, q: MatchQuery = {}) {
    return this.request<MatchResult>('GET', `/employer/vacancies/${vacancyId}/matches${buildQuery({ ...q })}`)
  }
  getVacancyAssessment(vacancyId: string) {
    return this.request<VacancyAssessment>('GET', `/employer/vacancies/${vacancyId}/assessment`)
  }
  searchCandidates(q: CandidateQuery = {}) {
    return this.request<CandidatePage>('GET', `/employer/candidates${buildQuery({ ...q })}`)
  }
  getCandidate(id: string) {
    return this.request<CandidateCard>('GET', `/employer/candidates/${id}`)
  }
  getFavorites(vacancyId?: string) {
    return this.request<FavoriteItem[]>('GET', `/employer/favorites${buildQuery({ vacancy_id: vacancyId })}`)
  }
  addFavorite(profileId: string, data: { vacancy_id?: string | null; note?: string | null } = {}) {
    return this.request<{ is_favorite: true }>('PUT', `/employer/favorites/${profileId}`, { body: data })
  }
  removeFavorite(profileId: string) {
    return this.request<void>('DELETE', `/employer/favorites/${profileId}`)
  }
  getCategories() {
    return this.request<CategoryStat[]>('GET', '/employer/categories')
  }
  createInvitation(data: InvitationInput) {
    return this.request<Invitation>('POST', '/employer/invitations', { body: data })
  }
  getEmployerInvitations() {
    return this.request<Invitation[]>('GET', '/employer/invitations')
  }
  getEmployerApplications() {
    return this.request<Application[]>('GET', '/employer/applications')
  }
  setApplicationStatus(id: string, status: Exclude<ApplicationStatus, 'sent'>) {
    return this.request<Application>('POST', `/employer/applications/${id}/status`, { body: { status } })
  }
  getEmployerChallenges() {
    return this.request<Challenge[]>('GET', '/employer/challenges')
  }
  createChallenge(data: ChallengeInput) {
    return this.request<Challenge>('POST', '/employer/challenges', { body: data })
  }
  getChallengeSubmissions(id: string) {
    return this.request<ChallengeSubmission[]>('GET', `/employer/challenges/${id}/submissions`)
  }

  // ================= служебное =================

  /** /health живёт вне /api/v1. */
  health() {
    return fetch('/health').then((r) => r.json() as Promise<{ status: string }>)
  }

  // ── Code Arena ──
  getArenaSandbox() {
    return this.request<ArenaSandbox>('GET', '/arena/sandbox')
  }
  getArenaProblems() {
    return this.request<ArenaProblemRef[]>('GET', '/arena/problems')
  }
  getArenaRounds() {
    return this.request<ArenaRound[]>('GET', '/arena/rounds')
  }
  getArenaRound(id: string) {
    return this.request<ArenaRoundDetail>('GET', `/arena/rounds/${id}`)
  }
  joinArenaRound(id: string) {
    return this.request<ArenaParticipation>('POST', `/arena/rounds/${id}/join`)
  }
  runArena(id: string, problem: string, language: ArenaLanguage, code: string) {
    return this.request<ArenaRunResult>('POST', `/arena/rounds/${id}/run`, { body: { problem, language, code } })
  }
  submitArena(id: string, problem: string, language: ArenaLanguage, code: string, signals: Record<string, number>) {
    return this.request<{ submission: ArenaSubmission; participation: ArenaParticipation }>('POST', `/arena/rounds/${id}/submit`, {
      body: { problem, language, code, signals },
    })
  }
  finishArena(id: string) {
    return this.request<ArenaParticipation>('POST', `/arena/rounds/${id}/finish`)
  }
  getArenaBoard(id: string) {
    return this.request<ArenaBoard>('GET', `/arena/rounds/${id}/leaderboard`)
  }
  getArenaEditorial(id: string) {
    return this.request<{ round_id: string; problems: ArenaEditorialItem[] }>('GET', `/arena/rounds/${id}/editorial`)
  }
  getArenaMe() {
    return this.request<ArenaMe>('GET', '/arena/me')
  }
  setArenaSettings(show_arena: boolean) {
    return this.request<{ show_arena: boolean; display_name: string }>('PUT', '/arena/me/settings', { body: { show_arena } })
  }
  createArenaRound(data: ArenaRoundInput) {
    return this.request<ArenaRound>('POST', '/arena/rounds', { body: data })
  }
  getArenaTop(params: { specialization?: string; grade?: string; has_fsp?: boolean; min_rating?: number } = {}) {
    return this.request<{ total: number; items: ArenaTopItem[] }>('GET', `/arena/top${buildQuery(params)}`)
  }
  getArenaCandidate(profileId: string) {
    return this.request<ArenaCandidate>('GET', `/arena/candidates/${profileId}`)
  }

  /**
   * Поток изменений таблицы (SSE через fetch: EventSource не умеет заголовок Authorization).
   * Возвращает функцию остановки. При обрыве переподключается.
   */
  watchArenaBoard(id: string, onChange: (version: string) => void): () => void {
    const ctrl = new AbortController()
    const loop = async () => {
      while (!ctrl.signal.aborted) {
        try {
          const res = await fetch(this.url(`/arena/rounds/${id}/stream`), { headers: this.headers(false), signal: ctrl.signal })
          if (!res.ok || !res.body) throw new Error(String(res.status))
          const reader = res.body.getReader()
          const dec = new TextDecoder()
          let buf = ''
          for (;;) {
            const { value, done } = await reader.read()
            if (done) break
            buf += dec.decode(value, { stream: true })
            let idx
            while ((idx = buf.indexOf('\n\n')) >= 0) {
              const chunk = buf.slice(0, idx)
              buf = buf.slice(idx + 2)
              const data = chunk.split('\n').find((l) => l.startsWith('data: '))
              if (data) {
                try {
                  onChange((JSON.parse(data.slice(6)) as { version: string }).version)
                } catch {
                  /* пропускаем битое событие */
                }
              }
            }
          }
        } catch {
          if (ctrl.signal.aborted) return
        }
        await new Promise((r) => setTimeout(r, 3000))
      }
    }
    void loop()
    return () => ctrl.abort()
  }
}

export const api = new ApiClient()
