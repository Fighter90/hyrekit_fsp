import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import type { AttemptItem, AttemptView } from '../api/types'
import {
  countAnswered, formatCountdown, isAnswered, msLeft, neighbourGrade, nextUnanswered, sanitizeNumberInput, toggleMulti,
} from '../lib/assessment'
import TestRunner from '../components/assessment/TestRunner'
import { mockFetch, renderWithProviders } from './helpers'

const single: AttemptItem = { id: 'a', topic: 'algorithms', difficulty: 2, kind: 'single', stem: 'Сколько шагов?', code: 'print(1)', options: ['1', '2', '3'] }
const multi: AttemptItem = { id: 'b', topic: 'http', difficulty: 3, kind: 'multi', stem: 'Идемпотентные методы?', code: null, options: ['GET', 'POST', 'PUT'] }
const num: AttemptItem = { id: 'c', topic: 'sql', difficulty: 4, kind: 'number', stem: 'Сколько строк?', code: null, options: [] }

describe('логика теста', () => {
  it('определяет, отвечено ли задание', () => {
    expect(isAnswered(single, undefined)).toBe(false)
    expect(isAnswered(single, '0')).toBe(true)
    expect(isAnswered(multi, [])).toBe(false)
    expect(isAnswered(multi, ['1'])).toBe(true)
    expect(isAnswered(num, '  ')).toBe(false)
  })

  it('переключает варианты множественного выбора с сортировкой', () => {
    let v = toggleMulti(undefined, 2)
    v = toggleMulti(v, 0)
    expect(v).toEqual(['0', '2'])
    expect(toggleMulti(v, 2)).toEqual(['0'])
  })

  it('чистит числовой ввод', () => {
    expect(sanitizeNumberInput('-12,5abc.3')).toBe('-12,53')
    expect(sanitizeNumberInput('4-2')).toBe('42')
  })

  it('считает прогресс и ищет следующее неотвеченное по кругу', () => {
    const items = [single, multi, num]
    const answers = { a: '1', c: '7' }
    expect(countAnswered(items, answers)).toBe(2)
    expect(nextUnanswered(items, answers, 2)).toBe(1)
    expect(nextUnanswered(items, { ...answers, b: ['0'] }, 0)).toBe(-1)
  })

  it('форматирует обратный отсчёт', () => {
    expect(formatCountdown(125_000)).toBe('02:05')
    expect(formatCountdown(3_725_000)).toBe('1:02:05')
    expect(formatCountdown(-5)).toBe('00:00')
    expect(msLeft('2026-01-01T00:01:00Z', Date.parse('2026-01-01T00:00:00Z'))).toBe(60_000)
  })

  it('находит соседний грейд', () => {
    expect(neighbourGrade('middle', -1)).toBe('junior')
    expect(neighbourGrade('lead', 1)).toBeNull()
  })
})

describe('TestRunner', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('автосохраняет выбранный вариант индексом', async () => {
    const fetchMock = mockFetch({ '/answer': { saved: true } })
    const attempt: AttemptView = {
      id: 'att1', grade: 'middle', specialization: 'backend', started_at: new Date().toISOString(),
      deadline_at: new Date(Date.now() + 600_000).toISOString(), items: [single, multi, num], answers: {},
    }
    renderWithProviders(<TestRunner attempt={attempt} onFinished={() => undefined} specTitle="Backend" />)
    expect(screen.getByText('Сколько шагов?')).toBeInTheDocument()
    expect(screen.getByText('print(1)')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('radio', { name: /2/ }))
    await waitFor(() => expect(screen.getByText('сохранено')).toBeInTheDocument())
    const call = fetchMock.mock.calls.find(([u]) => String(u).includes('/candidate/assessment/att1/answer'))!
    expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({ item_id: 'a', answer: '1' })
    fireEvent.click(screen.getByRole('button', { name: /Далее/ }))
    expect(screen.getByText('Идемпотентные методы?')).toBeInTheDocument()
  })
})

describe('тест под вакансию', () => {
  it('сравнивает профили сложности вариантов', async () => {
    const { sameProfile } = await import('../lib/assessment')
    const base = { specialization: 'backend', grade: 'middle' as const, grade_level: 2, seconds: 900, topics: [] }
    expect(sameProfile({ ...base, variants: [{ items: [], difficulty_profile: [1, 2, 3] }, { items: [], difficulty_profile: [1, 2, 3] }] })).toBe(true)
    expect(sameProfile({ ...base, variants: [{ items: [], difficulty_profile: [1, 2, 3] }, { items: [], difficulty_profile: [1, 3, 3] }] })).toBe(false)
  })
})
