import type { Grade, InvitationStatus, Suggestion, WorkFormat } from '../api/types'

export const GRADE_ORDER: Grade[] = ['intern', 'junior', 'middle', 'senior', 'lead']

export const GRADE_LABEL: Record<Grade, string> = {
  intern: 'Intern',
  junior: 'Junior',
  middle: 'Middle',
  senior: 'Senior',
  lead: 'Lead',
}

export const WORK_FORMAT_LABEL: Record<WorkFormat, string> = {
  office: 'Офис',
  hybrid: 'Гибрид',
  remote: 'Удалённо',
}

export const STATUS_LABEL: Record<InvitationStatus, string> = {
  sent: 'Отправлено',
  viewed: 'Просмотрено',
  accepted: 'Принято',
  declined: 'Отклонено',
}

export const SUGGESTION_LABEL: Record<Suggestion, string> = {
  keep: 'Категория подтверждена — можно ждать приглашений',
  retry_lower: 'Рекомендуем пересдать на грейд ниже',
  try_higher: 'Отличный результат — попробуйте грейд выше',
}

export function gradeLabel(g: string | null | undefined): string {
  if (!g) return '—'
  return GRADE_LABEL[g as Grade] ?? g
}

export function workFormatLabel(f: string | null | undefined): string {
  if (!f) return '—'
  return WORK_FORMAT_LABEL[f as WorkFormat] ?? f
}

const rub = new Intl.NumberFormat('ru-RU', { maximumFractionDigits: 0 })

export function formatMoney(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  return `${rub.format(n)} ₽`
}

/** Вилка зарплаты: «150 000 – 220 000 ₽», «от 150 000 ₽», «до 220 000 ₽». */
export function formatSalary(from: number | null | undefined, to: number | null | undefined): string {
  const hasFrom = from !== null && from !== undefined
  const hasTo = to !== null && to !== undefined
  if (hasFrom && hasTo) {
    if (from === to) return formatMoney(from)
    return `${rub.format(from!)} – ${rub.format(to!)} ₽`
  }
  if (hasFrom) return `от ${formatMoney(from)}`
  if (hasTo) return `до ${formatMoney(to)}`
  return 'не указана'
}

/**
 * Дата из ответа API. Бэкенд хранит время в UTC без пояса («2026-10-10T18:55:47»),
 * а `new Date()` читает такую строку как местное время. Без пояса считаем UTC.
 */
export function parseServerDate(iso: string): Date {
  const utc = /T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(iso) ? `${iso}Z` : iso
  return new Date(utc)
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = parseServerDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = parseServerDate(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}

/** Склонение: plural(5, ['кандидат','кандидата','кандидатов']). */
export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100
  const b = a % 10
  if (a > 10 && a < 20) return forms[2]
  if (b > 1 && b < 5) return forms[1]
  if (b === 1) return forms[0]
  return forms[2]
}

export function experienceLabel(years: number | null | undefined): string {
  if (years === null || years === undefined) return 'опыт не указан'
  if (years < 1) return 'менее года'
  return `${years} ${plural(years, ['год', 'года', 'лет'])}`
}

/** Нормализация тега стека: обрезка пробелов, схлопывание. */
export function normalizeTag(s: string): string {
  return s.trim().replace(/\s+/g, ' ')
}

/** Скачивание Blob как файла. */
export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function errorMessage(e: unknown, fallback = 'Что-то пошло не так'): string {
  if (e instanceof Error && e.message) return e.message
  return fallback
}
