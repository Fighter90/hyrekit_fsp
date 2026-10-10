import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, UserRound, Building2, Mail, Lock, ArrowRight } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { Button } from '../../components/ui/Button'
import Field from '../../components/ui/Field'
import type { Role } from '../../api/types'
import { errorMessage } from '../../lib/format'

type Mode = 'login' | 'register'

const ROLES: { key: Role; title: string; text: string; icon: typeof UserRound }[] = [
  { key: 'candidate', title: 'Кандидат', text: 'Пройду тест, получу категорию и приглашения', icon: UserRound },
  { key: 'employer', title: 'Работодатель', text: 'Ищу специалистов и отправляю приглашения', icon: Building2 },
]

// Демо-аккаунты создаются бэкендом при старте
const DEMO = [
  { label: 'Кандидат', email: 'candidate@hyrekit.ru' },
  { label: 'Работодатель', email: 'employer@hyrekit.ru' },
]
const DEMO_PASSWORD = 'HyreKit2026'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export default function AuthPage() {
  const [params, setParams] = useSearchParams()
  const { login, register, isAuthenticated } = useAuth()
  const navigate = useNavigate()

  const mode: Mode = params.get('mode') === 'register' ? 'register' : 'login'
  const [role, setRole] = useState<Role>(params.get('role') === 'employer' ? 'employer' : 'candidate')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [fullName, setFullName] = useState('')
  const [agree, setAgree] = useState(false)
  const [showPw, setShowPw] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const next = params.get('next')
  const target = next && next.startsWith('/app') ? next : '/app/dashboard'

  if (isAuthenticated && !busy) return <Navigate to={target} replace />

  const switchMode = (m: Mode) => {
    const p = new URLSearchParams(params)
    if (m === 'register') p.set('mode', 'register')
    else p.delete('mode')
    setParams(p, { replace: true })
    setError(null)
    setInfo(null)
  }

  const validate = (): string | null => {
    if (!EMAIL_RE.test(email.trim())) return 'Введите корректный email'
    if (mode === 'register') {
      if (fullName.trim().length < 2) return 'Укажите имя'
      if (password.length < 8) return 'Пароль — минимум 8 символов'
      if (!agree) return 'Нужно принять условия и политику конфиденциальности'
    } else if (!password) return 'Введите пароль'
    return null
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    const v = validate()
    if (v) {
      setError(v)
      return
    }
    setBusy(true)
    setError(null)
    setInfo(null)
    try {
      if (mode === 'login') {
        await login(email.trim(), password)
        navigate(target, { replace: true })
      } else {
        const res = await register({ email: email.trim(), password, full_name: fullName.trim(), role })
        if (res.user) navigate('/app/dashboard', { replace: true })
        else setInfo(res.message || 'Проверьте почту для подтверждения аккаунта')
      }
    } catch (err) {
      setError(errorMessage(err, mode === 'login' ? 'Не удалось войти' : 'Не удалось зарегистрироваться'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth card card--glow">
      <div className="auth__head">
        <h1 className="auth__title display">{mode === 'login' ? 'С возвращением' : 'Создать аккаунт'}</h1>
      </div>

      <div className="tabs auth__tabs" role="tablist">
        <button role="tab" aria-selected={mode === 'login'} className={`tabs__tab ${mode === 'login' ? 'is-active' : ''}`} onClick={() => switchMode('login')}>
          Вход
        </button>
        <button role="tab" aria-selected={mode === 'register'} className={`tabs__tab ${mode === 'register' ? 'is-active' : ''}`} onClick={() => switchMode('register')}>
          Регистрация
        </button>
      </div>

      <form className="stack" onSubmit={onSubmit} noValidate>
        {mode === 'register' && (
          <fieldset className="role-pick">
            <legend className="field__label">Кто вы?</legend>
            <div className="role-pick__grid">
              {ROLES.map((r) => (
                <label key={r.key} className={`role-card ${role === r.key ? 'is-active' : ''} role-card--${r.key}`}>
                  <input type="radio" name="role" value={r.key} checked={role === r.key} onChange={() => setRole(r.key)} />
                  <r.icon size={22} aria-hidden />
                  <strong>{r.title}</strong>
                  <small>{r.text}</small>
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {mode === 'register' && (
          <Field label={role === 'employer' ? 'Имя контактного лица' : 'Имя и фамилия'} htmlFor="full_name" required>
            <input id="full_name" className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" placeholder="Иван Петров" />
          </Field>
        )}

        <Field label="Email" htmlFor="email" required>
          <div className="input-icon">
            <Mail size={16} aria-hidden />
            <input id="email" type="email" className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" placeholder="you@example.ru" />
          </div>
        </Field>

        <Field label="Пароль" htmlFor="password" required hint={mode === 'register' ? 'Минимум 8 символов' : undefined}>
          <div className="input-icon">
            <Lock size={16} aria-hidden />
            <input
              id="password"
              type={showPw ? 'text' : 'password'}
              className="input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            />
            <button type="button" className="input-icon__btn" onClick={() => setShowPw(!showPw)} aria-label={showPw ? 'Скрыть пароль' : 'Показать пароль'}>
              {showPw ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>
        </Field>

        {mode === 'register' && (
          <label className="checkbox small">
            <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
            <span>
              Принимаю <Link to="/terms" target="_blank">пользовательское соглашение</Link> и{' '}
              <Link to="/privacy" target="_blank">политику конфиденциальности</Link>
            </span>
          </label>
        )}

        {error && <div className="alert alert--error" role="alert">{error}</div>}
        {info && <div className="alert alert--success" role="status">{info}</div>}

        <Button type="submit" size="lg" block loading={busy} iconRight={<ArrowRight size={18} />}>
          {mode === 'login' ? 'Войти' : role === 'employer' ? 'Зарегистрировать компанию' : 'Начать как кандидат'}
        </Button>
      </form>

      {mode === 'login' && (
        <div className="demo-hint">
          <span className="muted tiny">Демо-доступ · пароль HyreKit2026</span>
          <div className="row gap-xs wrap">
            {DEMO.map((d) => (
              <button
                key={d.email}
                type="button"
                className="chip-btn"
                onClick={() => {
                  setEmail(d.email)
                  setPassword(DEMO_PASSWORD)
                  setError(null)
                }}
              >
                {d.label}: {d.email}
              </button>
            ))}
          </div>
        </div>
      )}

      <p className="auth__switch muted small">
        {mode === 'login' ? (
          <>Нет аккаунта? <button className="link-btn" onClick={() => switchMode('register')}>Зарегистрироваться</button></>
        ) : (
          <>Уже есть аккаунт? <button className="link-btn" onClick={() => switchMode('login')}>Войти</button></>
        )}
      </p>
    </div>
  )
}
