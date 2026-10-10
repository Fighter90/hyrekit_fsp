import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import type { CandidateCard, InvitationStatus } from '../api/types'
import { invitationPending } from '../lib/candidate'
import CandidatesPage from '../pages/employer/CandidatesPage'
import { mockFetch, renderWithProviders } from './helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

const card = (name: string, status: InvitationStatus | null): CandidateCard => ({
  id: name,
  display_name: name,
  headline: null,
  category: 'backend:middle',
  category_title: 'Backend · Middle',
  specialization: 'backend',
  grade: 'middle',
  stack: ['Python'],
  roles: [],
  soft_skills: [],
  experience_years: 3,
  test_score: 70,
  rating: 60,
  fsp: null,
  salary_from: null,
  salary_to: null,
  work_format: null,
  contacts: null,
  contacts_unlocked: status === 'accepted',
  invitation_status: status,
} as CandidateCard)

describe('повторное приглашение', () => {
  it('блокирует только приглашение без ответа — как 409 на бэкенде', () => {
    expect(invitationPending('sent')).toBe(true)
    expect(invitationPending('viewed')).toBe(true)
    expect(invitationPending('accepted')).toBe(false)
    expect(invitationPending('declined')).toBe(false)
    expect(invitationPending(null)).toBe(false)
    expect(invitationPending(undefined)).toBe(false)
  })

  it('в банке кандидатов принявшего или отклонившего можно пригласить снова', async () => {
    const items = [card('Ждёт', 'sent'), card('Смотрел', 'viewed'), card('Принял', 'accepted'), card('Отказал', 'declined'), card('Новый', null)]
    mockFetch({
      '/catalog': { specializations: [], grades: [], industries: [], work_formats: [], grade_change_cooldown_days: 90 },
      '/employer/vacancies': [],
      '/employer/candidates': { total: items.length, items },
    })
    renderWithProviders(<CandidatesPage />, '/app/candidates')
    const button = async (name: string) => within((await screen.findByText(name)).closest('article')!).getByRole('button', { name: /Приглаш|Пригласить/ })
    for (const name of ['Ждёт', 'Смотрел']) {
      const b = await button(name)
      expect(b).toBeDisabled()
      expect(b).toHaveTextContent('Приглашён')
    }
    for (const name of ['Принял', 'Отказал', 'Новый']) {
      const b = await button(name)
      expect(b).toBeEnabled()
      expect(b).toHaveTextContent('Пригласить')
    }
  })
})
