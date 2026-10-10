import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import AuthPage from '../pages/auth/AuthPage'
import { mockFetch, renderWithProviders } from './helpers'

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('AuthPage', () => {
  it('переключает роль при регистрации', () => {
    mockFetch()
    renderWithProviders(<AuthPage />, '/auth?mode=register')
    expect(screen.getByRole('button', { name: /Начать как кандидат/ })).toBeInTheDocument()
    fireEvent.click(screen.getByLabelText(/Работодатель/))
    expect(screen.getByRole('button', { name: /Зарегистрировать компанию/ })).toBeInTheDocument()
    expect(screen.getByLabelText(/Имя контактного лица/)).toBeInTheDocument()
  })

  it('роль из query-параметра выбрана заранее', () => {
    mockFetch()
    renderWithProviders(<AuthPage />, '/auth?mode=register&role=employer')
    expect(screen.getByRole('radio', { name: /Работодатель/ })).toBeChecked()
  })

  it('отправляет роль в теле регистрации', async () => {
    const fetchMock = mockFetch({ '/auth/register': { message: 'Проверьте почту' } })
    renderWithProviders(<AuthPage />, '/auth?mode=register&role=employer')
    fireEvent.change(screen.getByLabelText(/Имя контактного лица/), { target: { value: 'Ольга' } })
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'hr@corp.ru' } })
    fireEvent.change(screen.getByLabelText(/^Пароль/), { target: { value: 'secret123' } })
    fireEvent.click(screen.getByRole('checkbox'))
    fireEvent.click(screen.getByRole('button', { name: /Зарегистрировать компанию/ }))
    await waitFor(() => expect(screen.getByText('Проверьте почту')).toBeInTheDocument())
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/auth/register'))!
    expect(JSON.parse(String((call[1] as RequestInit).body))).toMatchObject({ role: 'employer', email: 'hr@corp.ru', full_name: 'Ольга' })
  })

  it('валидирует пароль', () => {
    mockFetch()
    renderWithProviders(<AuthPage />, '/auth?mode=register')
    fireEvent.change(screen.getByLabelText(/Имя и фамилия/), { target: { value: 'Иван' } })
    fireEvent.change(screen.getByLabelText(/Email/), { target: { value: 'a@b.ru' } })
    fireEvent.change(screen.getByLabelText(/^Пароль/), { target: { value: '123' } })
    fireEvent.click(screen.getByRole('button', { name: /Начать как кандидат/ }))
    expect(screen.getByRole('alert')).toHaveTextContent('минимум 8')
  })
})
