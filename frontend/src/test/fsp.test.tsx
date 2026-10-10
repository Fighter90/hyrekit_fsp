import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { render } from '@testing-library/react'
import Providers from '../Providers'
import FspCallbackPage from '../pages/auth/FspCallbackPage'
import FspIdButton from '../components/settings/FspIdButton'
import FspPanel from '../components/settings/FspPanel'
import { mockFetch, renderWithProviders } from './helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

function renderCallback(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Providers>
        <Routes>
          <Route path="/fsp-callback" element={<FspCallbackPage />} />
          <Route path="/app/profile" element={<p>профиль</p>} />
          <Route path="/app/dashboard" element={<p>обзор</p>} />
          <Route path="/app/settings" element={<p>настройки</p>} />
        </Routes>
      </Providers>
    </MemoryRouter>,
  )
}

describe('ФСП ID', () => {
  it('кнопка скрыта, если вход через ФСП ID не настроен', async () => {
    const fetchMock = mockFetch({ '/auth/fsp/config': { enabled: false, test_provider: false } })
    renderWithProviders(<FspIdButton mode="login" />)
    await waitFor(() => expect(fetchMock).toHaveBeenCalled())
    expect(screen.queryByRole('button', { name: /ФСП ID/ })).toBeNull()
  })

  it('кнопка начинает вход и уводит на провайдера', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const fetchMock = mockFetch({
      '/auth/fsp/config': { enabled: true, test_provider: true },
      '/auth/fsp/start': { authorize_url: 'https://id.example/authorize?state=s' },
    })
    renderWithProviders(<FspIdButton mode="link" />)
    fireEvent.click(await screen.findByRole('button', { name: 'Привязать через ФСП ID' }))
    await waitFor(() => expect(assign).toHaveBeenCalledWith('https://id.example/authorize?state=s'))
    const start = fetchMock.mock.calls.find(([u]) => String(u).includes('/auth/fsp/start'))!
    expect(JSON.parse(String((start[1] as RequestInit).body))).toEqual({ mode: 'link' })
  })

  it('возврат с кодом: обмен один раз и вход нового кандидата', async () => {
    const fetchMock = mockFetch({
      '/auth/fsp/callback': {
        mode: 'login',
        fsp_id: 'FSP-123457',
        created: true,
        tokens: { access_token: 'a', refresh_token: 'r', token_type: 'bearer' },
      },
      '/auth/me': { id: 'u', email: 'x@fsp-id.hyrekit.ru', role: 'candidate', full_name: 'Участник' },
    })
    renderCallback('/fsp-callback?code=c1&state=s1')
    expect(await screen.findByText('профиль')).toBeInTheDocument()
    const calls = fetchMock.mock.calls.filter(([u]) => String(u).includes('/auth/fsp/callback'))
    expect(calls).toHaveLength(1)
    expect(JSON.parse(String((calls[0][1] as RequestInit).body))).toEqual({ code: 'c1', state: 's1' })
  })

  it('отказ на странице провайдера показывает понятную ошибку', async () => {
    const fetchMock = mockFetch()
    renderCallback('/fsp-callback?error=access_denied&state=s1')
    expect(await screen.findByRole('alert')).toHaveTextContent('Вход через ФСП ID отменён')
    expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/auth/fsp/callback'))).toBe(false)
  })

  it('отметка подтверждения в достижениях', () => {
    renderWithProviders(
      <FspPanel fsp={{ fsp_id: 'FSP-123450', athlete_name: null, achievements: [], score: 0, has_history: false, verified: true }} />,
    )
    expect(screen.getByText(/подтверждён ФСП ID/)).toBeInTheDocument()
  })
})
