import { afterEach, describe, expect, it, vi } from 'vitest'
import { screen, fireEvent, waitFor } from '@testing-library/react'
import type { AttemptItem, AttemptResult, AttemptView } from '../api/types'
import {
  countAnswered, formatCountdown, isAnswered, msLeft, neighbourGrade, nextUnanswered, sanitizeNumberInput, toggleMulti,
} from '../lib/assessment'
import TestRunner from '../components/assessment/TestRunner'
import ResultView from '../components/assessment/ResultView'
import { parseServerDate } from '../lib/format'
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

describe('время сервера и результат', () => {
  it('читает время без пояса как UTC, а не как местное', () => {
    const now = Date.parse('2026-10-10T18:55:47Z')
    expect(msLeft('2026-10-10T19:00:47.610972', now)).toBe(300_610)
    expect(parseServerDate('2026-10-10T18:55:47').toISOString()).toBe('2026-10-10T18:55:47.000Z')
    expect(parseServerDate('2026-10-10T21:55:47+03:00').toISOString()).toBe('2026-10-10T18:55:47.000Z')
  })

  const failed: AttemptResult = {
    id: 'a1', grade_tested: 'intern', specialization: 'frontend', score: 0, ability: -3.05, correct: 0, total: 5,
    passed: false, assigned_grade: 'intern', suggestion: 'keep', by_topic: [], finished_at: '2026-10-10T18:55:47',
  }

  it('не пишет «категория подтверждена», если тест не сдан', () => {
    renderWithProviders(<ResultView result={failed} specTitle="Frontend" allowedGrades={['intern']} onStart={() => {}} onBack={() => {}} />)
    expect(screen.getByText('Пока не подтверждён')).toBeInTheDocument()
    expect(screen.queryByText(/Категория подтверждена/)).toBeNull()
    expect(screen.queryByText('Присвоена категория')).toBeNull()
    expect(screen.getByText('Остаётся категория прошлого теста')).toBeInTheDocument()
    expect(screen.getByText(/попробуйте снова/)).toBeInTheDocument()
  })

  it('показывает присвоенную категорию при сданном тесте', () => {
    renderWithProviders(
      <ResultView result={{ ...failed, passed: true, correct: 4, score: 80 }} specTitle="Frontend" allowedGrades={['intern']} onStart={() => {}} onBack={() => {}} />,
    )
    expect(screen.getByText('Присвоена категория')).toBeInTheDocument()
    expect(screen.getByText(/Категория подтверждена/)).toBeInTheDocument()
  })
})
