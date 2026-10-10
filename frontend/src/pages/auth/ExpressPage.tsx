import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ArrowRight, Timer, ListChecks, Building2 } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useCatalog } from '../../contexts/CatalogContext'
import { Button } from '../../components/ui/Button'
import Field from '../../components/ui/Field'
import type { Grade } from '../../api/types'
import { errorMessage } from '../../lib/format'

/** Экспресс-тест для жюри (FSP-32): гостевой кандидат, 5 заданий, 5 минут. */
export default function ExpressPage() {
  const { catalog } = useCatalog()
  const { startGuest } = useAuth()
  const navigate = useNavigate()
  const [specialization, setSpecialization] = useState('backend')
  const [grade, setGrade] = useState<Grade>('junior')
  const [agree, setAgree] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (!agree) {
      setError('Нужно согласие на обработку данных гостевого профиля')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await startGuest({ specialization, grade, consent: true })
      navigate('/app/assessment', { replace: true, state: { autostart: grade } })
    } catch (err) {
      setError(errorMessage(err, 'Не удалось начать экспресс-тест'))
      setBusy(false)
    }
  }

  return (
    <div className="auth card card--glow">
      <div className="auth__head">
        <h1 className="auth__title display">Экспресс-тест</h1>
        <p className="muted small">Для экспертов жюри: без регистрации и почты.</p>
      </div>

      <ul className="test-facts">
        <li><ListChecks size={16} /> 5 заданий, по одному на тему специализации</li>
        <li><Timer size={16} /> 5 минут, тот же банк заданий и та же оценка, что в полном тесте</li>
        <li><Building2 size={16} /> После теста гостевой кандидат появится в подборке работодателя</li>
      </ul>

      <form className="stack" onSubmit={onSubmit} noValidate>
        <Field label="Специализация" htmlFor="express-spec" required>
          <select id="express-spec" className="input" value={specialization} onChange={(e) => setSpecialization(e.target.value)}>
            {(catalog?.specializations ?? [{ code: 'backend', title: 'Backend' }]).map((s) => (
              <option key={s.code} value={s.code}>{s.title}</option>
            ))}
          </select>
        </Field>
        <Field label="Грейд" htmlFor="express-grade" required>
          <select id="express-grade" className="input" value={grade} onChange={(e) => setGrade(e.target.value as Grade)}>
            {(catalog?.grades ?? [{ code: 'junior', title: 'Junior' }]).map((g) => (
              <option key={g.code} value={g.code}>{g.title}</option>
            ))}
          </select>
        </Field>

        <label className="checkbox small">
          <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
          <span>
            Согласен на обработку данных гостевого профиля по{' '}
            <Link to="/privacy" target="_blank">политике конфиденциальности</Link>
          </span>
        </label>

        {error && <div className="alert alert--error" role="alert">{error}</div>}

        <Button type="submit" size="lg" block loading={busy} iconRight={<ArrowRight size={18} />}>
          Начать экспресс-тест
        </Button>
      </form>

      <p className="auth__switch muted small">
        Это демо-режим. Полный тест — 10 заданий и 20 минут, грейд можно менять раз в 90 дней.
        Демо-работодатель: employer@hyrekit.ru · HyreKit2026, <Link to="/auth">вход</Link>.
      </p>
    </div>
  )
}
