import { useEffect, useState, type FormEvent } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { Save, Sparkles } from 'lucide-react'
import { api } from '../../api/client'
import type { Grade, VacancyInput, WorkFormat } from '../../api/types'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Field from '../../components/ui/Field'
import TagInput from '../../components/ui/TagInput'
import Toggle from '../../components/ui/Toggle'
import { Button } from '../../components/ui/Button'
import { ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { GRADE_ORDER, errorMessage, formatSalary, gradeLabel } from '../../lib/format'
import { EMPTY_VACANCY as EMPTY, validateVacancy, type Errors, type VacancyFormState as FormState } from '../../lib/vacancy'

export default function VacancyFormPage() {
  const { id } = useParams()
  const isEdit = !!id
  const navigate = useNavigate()
  const toast = useToast()
  const { catalog } = useCatalog()
  const [form, setForm] = useState<FormState>(EMPTY)
  const [errors, setErrors] = useState<Errors>({})
  const [loading, setLoading] = useState(isEdit)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!id) return
    api.getVacancy(id)
      .then((v) =>
        setForm({
          title: v.title, description: v.description, team_description: v.team_description ?? '',
          specialization: v.specialization, grade_min: v.grade_min, grade_max: v.grade_max, stack: v.stack,
          salary_from: String(v.salary_from), salary_to: String(v.salary_to), work_format: v.work_format,
          city: v.city ?? '', is_published: v.is_published,
        }),
      )
      .catch((e) => setLoadError(errorMessage(e)))
      .finally(() => setLoading(false))
  }, [id])

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setForm((f) => ({ ...f, [k]: v }))
    if (errors[k]) setErrors((e) => ({ ...e, [k]: undefined }))
  }

  const submit = async (e: FormEvent, thenMatches = false) => {
    e.preventDefault()
    const errs = validateVacancy(form)
    setErrors(errs)
    if (Object.keys(errs).length) {
      toast.error('Проверьте поля формы')
      return
    }
    const payload: VacancyInput = {
      title: form.title.trim(),
      description: form.description.trim(),
      team_description: form.team_description.trim() || undefined,
      specialization: form.specialization,
      grade_min: form.grade_min,
      grade_max: form.grade_max,
      stack: form.stack,
      salary_from: Number(form.salary_from),
      salary_to: Number(form.salary_to),
      work_format: form.work_format,
      city: form.city.trim() || undefined,
      is_published: form.is_published,
    }
    setBusy(true)
    try {
      const v = isEdit ? await api.updateVacancy(id!, payload) : await api.createVacancy(payload)
      toast.success(isEdit ? 'Потребность обновлена' : 'Потребность создана')
      navigate(thenMatches ? `/app/vacancies/${v.id}/matches` : '/app/vacancies')
    } catch (err) {
      toast.error(errorMessage(err, 'Не удалось сохранить'))
    } finally {
      setBusy(false)
    }
  }

  const grades = catalog?.grades.slice().sort((a, b) => a.order - b.order).map((g) => g.code) ?? GRADE_ORDER
  const hints = catalog?.specializations.find((s) => s.code === form.specialization)?.stack_hints ?? []

  return (
    <>
      <PageHeader title={isEdit ? 'Редактирование' : 'Новая потребность'} subtitle="Зарплатная вилка обязательна — кандидаты видят её в приглашении." />
      {loadError && <ErrorState message={loadError} />}
      {loading && <SkeletonCard lines={8} />}
      {!loading && !loadError && (
        <form className="profile-layout" onSubmit={(e) => submit(e)} noValidate>
          <div className="card stack-lg">
            <section>
              <h2 className="form-section__title">Позиция</h2>
              <div className="form-grid">
                <Field label="Название" htmlFor="v-title" required error={errors.title} className="span-2">
                  <input id="v-title" className="input" value={form.title} onChange={(e) => set('title', e.target.value)} placeholder="Python backend-разработчик" />
                </Field>
                <Field label="Специализация" htmlFor="v-spec" required error={errors.specialization}>
                  <select id="v-spec" className="select" value={form.specialization} onChange={(e) => set('specialization', e.target.value)}>
                    <option value="">Выберите</option>
                    {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
                  </select>
                </Field>
                <Field label="Формат работы" htmlFor="v-wf">
                  <select id="v-wf" className="select" value={form.work_format} onChange={(e) => set('work_format', e.target.value as WorkFormat)}>
                    {(catalog?.work_formats ?? [{ code: 'office', title: 'Офис' }, { code: 'hybrid', title: 'Гибрид' }, { code: 'remote', title: 'Удалённо' }]).map((w) => (
                      <option key={w.code} value={w.code}>{w.title}</option>
                    ))}
                  </select>
                </Field>
                <Field label="Грейд от" htmlFor="v-gmin">
                  <select id="v-gmin" className="select" value={form.grade_min} onChange={(e) => set('grade_min', e.target.value as Grade)}>
                    {grades.map((g) => <option key={g} value={g}>{gradeLabel(g)}</option>)}
                  </select>
                </Field>
                <Field label="Грейд до" htmlFor="v-gmax" error={errors.grade_max}>
                  <select id="v-gmax" className="select" value={form.grade_max} onChange={(e) => set('grade_max', e.target.value as Grade)}>
                    {grades.map((g) => <option key={g} value={g}>{gradeLabel(g)}</option>)}
                  </select>
                </Field>
                <Field label="Город" htmlFor="v-city" hint="Для офиса и гибрида">
                  <input id="v-city" className="input" value={form.city} onChange={(e) => set('city', e.target.value)} />
                </Field>
              </div>
            </section>

            <section>
              <h2 className="form-section__title">Зарплата, ₽ в месяц</h2>
              <div className="form-grid">
                <Field label="От" htmlFor="v-sf" required error={errors.salary_from}>
                  <input id="v-sf" type="number" min={0} step={5000} className="input" value={form.salary_from} onChange={(e) => set('salary_from', e.target.value)} />
                </Field>
                <Field label="До" htmlFor="v-st" required error={errors.salary_to}>
                  <input id="v-st" type="number" min={0} step={5000} className="input" value={form.salary_to} onChange={(e) => set('salary_to', e.target.value)} />
                </Field>
              </div>
            </section>

            <section>
              <h2 className="form-section__title">Требования</h2>
              <div className="stack">
                <Field label="Стек" htmlFor="v-stack" hint="Влияет на ранжирование: совпадения подсвечиваются, недостающее — показывается">
                  <TagInput id="v-stack" value={form.stack} onChange={(v) => set('stack', v)} suggestions={hints} />
                </Field>
                <Field label="Задачи и требования" htmlFor="v-desc" required error={errors.description}>
                  <textarea id="v-desc" className="textarea" rows={6} value={form.description} onChange={(e) => set('description', e.target.value)} />
                </Field>
                <Field label="О команде" htmlFor="v-team">
                  <textarea id="v-team" className="textarea" rows={3} value={form.team_description} onChange={(e) => set('team_description', e.target.value)} />
                </Field>
                <Toggle checked={form.is_published} onChange={(v) => set('is_published', v)} label="Опубликовать" hint="Опубликованные вакансии видят кандидаты и могут откликнуться" />
              </div>
            </section>
          </div>

          <aside className="profile-side">
            <div className="card card--glow sticky-side">
              <div className="kicker">превью</div>
              <h3 className="vacancy__title">{form.title || 'Название позиции'}</h3>
              <div className="vacancy__salary">
                {form.salary_from || form.salary_to ? formatSalary(form.salary_from ? Number(form.salary_from) : null, form.salary_to ? Number(form.salary_to) : null) : 'Вилка не указана'}
              </div>
              <p className="muted small">{gradeLabel(form.grade_min)} – {gradeLabel(form.grade_max)}</p>
              <div className="stack-sm mt">
                <Button type="submit" block icon={<Save size={16} />} loading={busy}>{isEdit ? 'Сохранить' : 'Создать'}</Button>
                <Button variant="secondary" block icon={<Sparkles size={16} />} disabled={busy} onClick={(e) => submit(e, true)}>
                  Сохранить и к подборке
                </Button>
              </div>
            </div>
          </aside>
        </form>
      )}
    </>
  )
}
