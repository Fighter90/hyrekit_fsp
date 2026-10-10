import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import App from '../App'
import { mockFetch, renderWithProviders } from './helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('App', () => {
  it('рендерит лендинг с призывом к действию', async () => {
    mockFetch({ '/catalog': { specializations: [], grades: [], industries: [], work_formats: [], grade_change_cooldown_days: 90 } })
    renderWithProviders(<App />, '/')
    expect(await screen.findByText('Не ищи работу.')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Я кандидат/ })[0]).toHaveAttribute('href', '/auth?mode=register&role=candidate')
    expect(screen.getByRole('heading', { name: 'Вопросы и ответы' })).toBeInTheDocument()
    expect(screen.getByText(/^HyreKit v\d+\.\d+\.\d+/)).toBeInTheDocument()
  })

  it('неавторизованного пользователя уводит из кабинета на вход', async () => {
    mockFetch()
    renderWithProviders(<App />, '/app/dashboard')
    expect(await screen.findByRole('heading', { name: 'С возвращением' })).toBeInTheDocument()
  })

  it('показывает 404 на неизвестном маршруте', async () => {
    mockFetch()
    renderWithProviders(<App />, '/nope')
    expect(await screen.findByText('Страница не найдена')).toBeInTheDocument()
  })
})

describe('версия сборки', () => {
  it('подписывает номер и коммит', async () => {
    const { versionLabel } = await import('../lib/version')
    expect(versionLabel('0.1.0', 'a7b191c')).toBe('v0.1.0 · a7b191c')
    expect(versionLabel('0.1.0', 'dev')).toBe('v0.1.0')
  })
})
