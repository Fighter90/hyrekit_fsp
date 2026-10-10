import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError, buildQuery } from '../api/client'

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } })
}

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('ApiClient', () => {
  it('собирает query без пустых значений', () => {
    expect(buildQuery({ a: '', b: undefined, c: false, d: 'x', e: 0, f: true })).toBe('?d=x&e=0&f=true')
    expect(buildQuery({})).toBe('')
  })

  it('строит URL подборки и банка кандидатов', async () => {
    const f = vi.fn(async () => json({ total: 0, items: [], categories: [], vacancy_id: 'v1' }))
    vi.stubGlobal('fetch', f)
    const api = new ApiClient('/api/v1')
    await api.getMatches('v1', { grade: 'middle', stack: 'Python,Go', has_fsp: true, limit: 20 })
    expect(f.mock.calls[0][0]).toBe('/api/v1/employer/vacancies/v1/matches?grade=middle&stack=Python%2CGo&has_fsp=true&limit=20')
    await api.searchCandidates({ specialization: 'backend', q: 'django', limit: 12, offset: 24 })
    expect(f.mock.calls[1][0]).toBe('/api/v1/employer/candidates?specialization=backend&q=django&limit=12&offset=24')
    await api.getPublishedVacancies({ grade: '', q: 'go' })
    expect(f.mock.calls[2][0]).toBe('/api/v1/candidate/vacancies?q=go')
  })

  it('строит запросы избранного и журнала согласий', async () => {
    const f = vi.fn(async () => json([]))
    vi.stubGlobal('fetch', f)
    const api = new ApiClient('/api/v1')
    await api.getFavorites('v1')
    expect(f.mock.calls[0][0]).toBe('/api/v1/employer/favorites?vacancy_id=v1')
    await api.getFavorites()
    expect(f.mock.calls[1][0]).toBe('/api/v1/employer/favorites')
    await api.addFavorite('p1', { vacancy_id: 'v1' })
    const [url, init] = f.mock.calls[2] as unknown as [string, RequestInit]
    expect([url, init.method, JSON.parse(String(init.body))]).toEqual(['/api/v1/employer/favorites/p1', 'PUT', { vacancy_id: 'v1' }])
    await api.getConsents()
    expect(f.mock.calls[3][0]).toBe('/api/v1/candidate/consents')
  })

  it('передаёт Bearer-токен и тело JSON', async () => {
    const f = vi.fn(async () => json({ saved: true }))
    vi.stubGlobal('fetch', f)
    const api = new ApiClient('/api/v1')
    api.setTokens({ access_token: 'AT', refresh_token: 'RT' })
    await api.saveAnswer('att', 'item', ['0', '2'])
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit]
    expect(url).toBe('/api/v1/candidate/assessment/att/answer')
    expect(init.method).toBe('POST')
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer AT')
    expect(JSON.parse(String(init.body))).toEqual({ item_id: 'item', answer: ['0', '2'] })
  })

  it('обновляет токен при 401 и повторяет запрос', async () => {
    const f = vi.fn()
      .mockResolvedValueOnce(json({ message: 'expired' }, 401))
      .mockResolvedValueOnce(json({ access_token: 'NEW', refresh_token: 'RT2', token_type: 'bearer' }))
      .mockResolvedValueOnce(json({ id: 'u1', role: 'candidate' }))
    vi.stubGlobal('fetch', f)
    const api = new ApiClient('/api/v1')
    api.setTokens({ access_token: 'OLD', refresh_token: 'RT' })
    const me = await api.me()
    expect(me.id).toBe('u1')
    expect(f.mock.calls[1][0]).toBe('/api/v1/auth/refresh')
    const retry = f.mock.calls[2][1] as RequestInit
    expect((retry.headers as Record<string, string>).Authorization).toBe('Bearer NEW')
    expect(localStorage.getItem('refresh_token')).toBe('RT2')
  })

  it('бросает ApiError с сообщением из единого формата ошибок', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => json({ error_code: 'CONFLICT', message: 'Смена грейда раньше срока' }, 409)))
    const api = new ApiClient('/api/v1')
    const err = await api.startAttempt('senior').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(409)
    expect(err.code).toBe('CONFLICT')
    expect(err.message).toBe('Смена грейда раньше срока')
  })

  it('загружает резюме как multipart без Content-Type', async () => {
    const f = vi.fn(async () => json({ fields: {}, source: 'rules', text_length: 10 }))
    vi.stubGlobal('fetch', f)
    const api = new ApiClient('/api/v1')
    await api.uploadResume(new File(['x'], 'cv.pdf', { type: 'application/pdf' }))
    const init = f.mock.calls[0][1] as unknown as RequestInit
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.headers as Record<string, string>)['Content-Type']).toBeUndefined()
  })
})
