import { useState, type FormEvent } from 'react'
import { KeyRound, Save } from 'lucide-react'
import { api } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import Field from '../ui/Field'
import { Button } from '../ui/Button'
import { errorMessage, formatDate } from '../../lib/format'

/** Аккаунт и безопасность: данные входа и смена пароля (общая для обеих ролей). */
export default function SecuritySection() {
  const { user } = useAuth()
  const toast = useToast()
  const [form, setForm] = useState({ current: '', next: '', confirm: '' })
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (!form.current || !form.next) return setError('Заполните все поля')
    if (form.next.length < 8) return setError('Новый пароль — минимум 8 символов')
    if (form.next !== form.confirm) return setError('Пароли не совпадают')
    setBusy(true)
    try {
      await api.changePassword(form.current, form.next)
      setForm({ current: '', next: '', confirm: '' })
      toast.success('Пароль изменён')
    } catch (err) {
      setError(errorMessage(err, 'Не удалось сменить пароль'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="card">
      <div className="card__title"><KeyRound size={18} /> Аккаунт и безопасность</div>
      <dl className="kv">
        <dt>Email</dt>
        <dd>{user?.email} {user?.is_verified ? <span className="text-success small">✓ подтверждён</span> : <span className="text-red small">не подтверждён</span>}</dd>
        <dt>Роль</dt>
        <dd>{user?.role === 'employer' ? 'Работодатель' : 'Кандидат'}</dd>
        <dt>С нами с</dt>
        <dd>{formatDate(user?.created_at)}</dd>
      </dl>
      <form className="stack mt-lg" onSubmit={submit}>
        <div className="form-grid">
          <Field label="Текущий пароль" htmlFor="pw-cur" className="span-2">
            <input id="pw-cur" type="password" className="input" autoComplete="current-password" value={form.current} onChange={(e) => setForm({ ...form, current: e.target.value })} />
          </Field>
          <Field label="Новый пароль" htmlFor="pw-new">
            <input id="pw-new" type="password" className="input" autoComplete="new-password" value={form.next} onChange={(e) => setForm({ ...form, next: e.target.value })} />
          </Field>
          <Field label="Повторите пароль" htmlFor="pw-rep">
            <input id="pw-rep" type="password" className="input" autoComplete="new-password" value={form.confirm} onChange={(e) => setForm({ ...form, confirm: e.target.value })} />
          </Field>
        </div>
        {error && <div className="alert alert--error" role="alert">{error}</div>}
        <div className="row end">
          <Button type="submit" variant="secondary" icon={<Save size={16} />} loading={busy}>Сменить пароль</Button>
        </div>
      </form>
    </section>
  )
}
