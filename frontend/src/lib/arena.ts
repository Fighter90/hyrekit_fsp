import type { ArenaVerdict } from '../api/types'

export const VERDICT_LABEL: Record<ArenaVerdict, string> = {
  OK: 'Верно',
  WA: 'Неверный ответ',
  TLE: 'Превышено время',
  MLE: 'Превышена память',
  RE: 'Ошибка выполнения',
  CE: 'Ошибка компиляции',
}

export function formatClock(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const mm = String(m).padStart(2, '0')
  const ss = String(sec).padStart(2, '0')
  return h ? `${h}:${mm}:${ss}` : `${mm}:${ss}`
}
