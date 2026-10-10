import type { AnswerValue, AttemptItem, Grade, VacancyAssessment } from '../api/types'
import { GRADE_ORDER } from './format'

/*
 * Чистая логика прохождения теста — вынесена из компонента для тестируемости.
 * Формат ответа (согласован с банком заданий на бэкенде):
 *   single — индекс выбранного варианта строкой: "2"
 *   multi  — отсортированный массив индексов строками: ["0", "3"]
 *   number — число строкой: "42" (запятая допускается, сервер её нормализует)
 */

export function isAnswered(item: AttemptItem, value: AnswerValue | undefined): boolean {
  if (value === undefined || value === null) return false
  if (item.kind === 'multi') return Array.isArray(value) && value.length > 0
  if (Array.isArray(value)) return value.length > 0
  return value.trim() !== ''
}

/** Переключает вариант в множественном выборе, сохраняя сортировку по индексу. */
export function toggleMulti(current: AnswerValue | undefined, optionIndex: number): string[] {
  const set = new Set(Array.isArray(current) ? current : current ? [current] : [])
  const key = String(optionIndex)
  if (set.has(key)) set.delete(key)
  else set.add(key)
  return [...set].sort((a, b) => Number(a) - Number(b))
}

export function isOptionSelected(value: AnswerValue | undefined, optionIndex: number): boolean {
  const key = String(optionIndex)
  if (Array.isArray(value)) return value.includes(key)
  return value === key
}

/** Допустимый ввод для числового ответа: цифры, минус, одна точка/запятая. */
export function sanitizeNumberInput(raw: string): string {
  let s = raw.replace(/[^\d.,-]/g, '')
  // минус только в начале
  s = s.replace(/(?!^)-/g, '')
  // только один десятичный разделитель
  const m = s.match(/[.,]/)
  if (m && m.index !== undefined) {
    s = s.slice(0, m.index + 1) + s.slice(m.index + 1).replace(/[.,]/g, '')
  }
  return s
}

export function countAnswered(items: AttemptItem[], answers: Record<string, AnswerValue>): number {
  return items.reduce((acc, it) => acc + (isAnswered(it, answers[it.id]) ? 1 : 0), 0)
}

/** Индекс следующего неотвеченного задания после `from` (по кругу) или -1. */
export function nextUnanswered(items: AttemptItem[], answers: Record<string, AnswerValue>, from: number): number {
  const n = items.length
  for (let step = 1; step <= n; step++) {
    const i = (from + step) % n
    if (!isAnswered(items[i], answers[items[i].id])) return i
  }
  return -1
}

export function msLeft(deadlineIso: string, now: number = Date.now()): number {
  const t = new Date(deadlineIso).getTime()
  if (Number.isNaN(t)) return 0
  return Math.max(0, t - now)
}

/** 125000 → "02:05", 3725000 → "1:02:05". */
export function formatCountdown(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000))
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const pad = (n: number) => String(n).padStart(2, '0')
  return h > 0 ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`
}

export const DIFFICULTY_LABEL = ['', 'Лёгкое', 'Базовое', 'Среднее', 'Сложное', 'Экспертное']

/** Соседний грейд для рекомендации «пересдать ниже / попробовать выше». */
export function neighbourGrade(g: Grade, dir: -1 | 1): Grade | null {
  const i = GRADE_ORDER.indexOf(g)
  return GRADE_ORDER[i + dir] ?? null
}


/** Совпадают ли профили сложности всех вариантов (поэлементно). */
export function sameProfile(a: VacancyAssessment): boolean {
  const [first, ...rest] = a.variants.map((v) => v.difficulty_profile.join(','))
  return rest.every((p) => p === first)
}

