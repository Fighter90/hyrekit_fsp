import type { Grade, WorkFormat } from '../api/types'
import { GRADE_ORDER } from './format'

export interface VacancyFormState {
  title: string
  description: string
  team_description: string
  specialization: string
  grade_min: Grade
  grade_max: Grade
  stack: string[]
  salary_from: string
  salary_to: string
  work_format: WorkFormat
  city: string
  is_published: boolean
}

export const EMPTY_VACANCY: VacancyFormState = {
  title: '', description: '', team_description: '', specialization: '', grade_min: 'junior', grade_max: 'middle',
  stack: [], salary_from: '', salary_to: '', work_format: 'remote', city: '', is_published: true,
}

export type Errors = Partial<Record<keyof VacancyFormState, string>>

/** Проверка формы потребности: зарплатная вилка обязательна, from ≤ to, грейды по порядку. */
export function validateVacancy(f: VacancyFormState): Errors {
  const e: Errors = {}
  if (f.title.trim().length < 3) e.title = 'Название — минимум 3 символа'
  if (!f.description.trim()) e.description = 'Опишите задачи'
  if (!f.specialization) e.specialization = 'Выберите специализацию'
  if (GRADE_ORDER.indexOf(f.grade_min) > GRADE_ORDER.indexOf(f.grade_max)) e.grade_max = 'Максимальный грейд ниже минимального'
  const from = Number(f.salary_from)
  const to = Number(f.salary_to)
  if (f.salary_from === '' || !(from > 0)) e.salary_from = 'Укажите зарплату «от»'
  if (f.salary_to === '' || !(to > 0)) e.salary_to = 'Укажите зарплату «до»'
  else if (from > to) e.salary_to = '«До» должно быть не меньше «от»'
  return e
}

