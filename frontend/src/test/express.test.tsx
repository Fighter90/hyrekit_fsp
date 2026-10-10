import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import ExpressPage from '../pages/auth/ExpressPage'
import { mockFetch, renderWithProviders } from './helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('ExpressPage', () => {
  it('без согласия гость не создаётся', () => {
    const fetchMock = mockFetch()
    renderWithProviders(<ExpressPage />, '/express')
    fireEvent.click(screen.getByRole('button', { name: /Начать экспресс-тест/ }))
    expect(screen.getByRole('alert')).toHaveTextContent('согласие')
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/auth/guest'))).toBe(false)
  })

  it('отправляет специализацию, грейд и согласие', async () => {
    const fetchMock = mockFetch({
      '/auth/guest': { access_token: 'a', refresh_token: 'r', token_type: 'bearer' },
      '/auth/me': { id: 'u', email: 'g@guest.hyrekit.ru', role: 'candidate', full_name: 'Гость' },
    })
    renderWithProviders(<ExpressPage />, '/express')
    fireEvent.change(screen.getByLabelText(/Грейд/), { target: { value: 'junior' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: /Начать экспресс-тест/ }))
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/auth/me'))).toBe(true))
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/auth/guest'))!
    expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({ specialization: 'backend', grade: 'junior', consent: true })
  })
})
