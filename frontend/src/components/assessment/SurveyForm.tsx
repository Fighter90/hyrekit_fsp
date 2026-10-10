import { useState, type FormEvent } from 'react'
import { ArrowRight } from 'lucide-react'
import type { CandidateProfile, Grade, SurveyInput } from '../../api/types'
import { useCatalog } from '../../contexts/CatalogContext'
import Field from '../ui/Field'
import TagInput from '../ui/TagInput'
import { Button } from '../ui/Button'
import { GRADE_ORDER, gradeLabel } from '../../lib/format'

interface Props {
  profile: CandidateProfile
  onSubmit: (data: SurveyInput) => Promise<void>
  onCancel?: () => void
}

/** Опрос перед тестом: отрасль, специализация, опыт, стек и заявленный грейд. */
export default function SurveyForm({ profile, onSubmit, onCancel }: Props) {
  const { catalog } = useCatalog()
  const [industry, setIndustry] = useState(profile.industry ?? '')
  const [spec, setSpec] = useState(profile.specialization ?? '')
  const [exp, setExp] = useState(profile.experience_years === null ? '' : String(profile.experience_years))
  const [stack, setStack] = useState<string[]>(profile.stack ?? [])
  const [grade, setGrade] = useState<Grade | ''>(profile.declared_grade ?? '')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const grades = catalog?.grades.slice().sort((a, b) => a.order - b.order) ??
    GRADE_ORDER.map((g, i) => ({ code: g, title: gradeLabel(g), order: i, years: '' }))
  const specObj = catalog?.specializations.find((s) => s.code === spec)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!industry || !spec || !grade || exp === '') {
      setError('Заполните все поля опроса')
      return
    }
    if (stack.length === 0) {
      setError('Добавьте хотя бы одну технологию в стек')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await onSubmit({ industry, specialization: spec, experience_years: Number(exp), stack, declared_grade: grade })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Не удалось сохранить опрос')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card stack-lg survey" onSubmit={submit}>
      <div>
        <div className="kicker">шаг 1 · опрос</div>
        <h2 className="survey__title">Расскажите о себе</h2>
        <p className="muted small">Ответы определяют, какой тест вы будете проходить.</p>
      </div>

      <fieldset className="survey__set">
        <legend className="field__label">Специализация <span className="field__req">*</span></legend>
        <div className="choice-grid">
          {catalog?.specializations.map((s) => (
            <label key={s.code} className={`choice ${spec === s.code ? 'is-active' : ''}`}>
              <input type="radio" name="spec" value={s.code} checked={spec === s.code} onChange={() => setSpec(s.code)} />
              <strong>{s.title}</strong>
              <small>{s.topics.slice(0, 3).join(' · ')}</small>
            </label>
          )) ?? <p className="muted small">Загружаем справочник…</p>}
        </div>
      </fieldset>

      <div className="form-grid">
        <Field label="Отрасль" htmlFor="sv-ind" required>
          <select id="sv-ind" className="select" value={industry} onChange={(e) => setIndustry(e.target.value)}>
            <option value="">Выберите отрасль</option>
            {catalog?.industries.map((i) => <option key={i.code} value={i.code}>{i.title}</option>)}
          </select>
        </Field>
        <Field label="Опыт в специализации, лет" htmlFor="sv-exp" required>
          <input id="sv-exp" className="input" type="number" min={0} max={50} step={0.5} value={exp} onChange={(e) => setExp(e.target.value)} />
        </Field>
      </div>

      <Field label="Стек" htmlFor="sv-stack" required hint="Технологии, с которыми вы работали">
        <TagInput id="sv-stack" value={stack} onChange={setStack} suggestions={specObj?.stack_hints ?? []} />
      </Field>

      <fieldset className="survey__set">
        <legend className="field__label">Заявленный грейд <span className="field__req">*</span></legend>
        <div className="grade-grid">
          {grades.map((g) => (
            <label key={g.code} className={`choice choice--grade grade--${g.code} ${grade === g.code ? 'is-active' : ''}`}>
              <input type="radio" name="grade" value={g.code} checked={grade === g.code} onChange={() => setGrade(g.code)} />
              <strong>{g.title}</strong>
              {g.years && <small>{g.years}</small>}
            </label>
          ))}
        </div>
        <p className="field__hint">
          Тест подтвердит грейд. Сменить подтверждённый грейд можно не чаще раза в {catalog?.grade_change_cooldown_days ?? 90} дней.
        </p>
      </fieldset>

      {error && <div className="alert alert--error" role="alert">{error}</div>}

      <div className="row end gap-sm">
        {onCancel && <Button variant="ghost" onClick={onCancel}>Отмена</Button>}
        <Button type="submit" loading={busy} iconRight={<ArrowRight size={16} />}>Сохранить и перейти к тесту</Button>
      </div>
    </form>
  )
}
