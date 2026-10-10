import { useEffect, useState } from 'react'
import { useParams, useSearchParams } from 'react-router-dom'
import { CheckCircle2, XCircle } from 'lucide-react'
import { api } from '../../api/client'
import { LinkButton } from '../../components/ui/Button'
import { Spinner } from '../../components/ui/States'
import { useAuth } from '../../contexts/AuthContext'
import { errorMessage } from '../../lib/format'

/** Подтверждение email: токен берётся из /verify/:token или ?token=. */
export default function EmailVerifyPage() {
  const { token: pathToken } = useParams()
  const [params] = useSearchParams()
  const token = pathToken || params.get('token')
  const { isAuthenticated, refreshUser } = useAuth()
  const [state, setState] = useState<'loading' | 'ok' | 'error'>(token ? 'loading' : 'error')
  const [message, setMessage] = useState(token ? '' : 'В ссылке нет токена подтверждения')

  useEffect(() => {
    if (!token) return
    let alive = true
    api.verifyEmail(token)
      .then((r) => {
        if (!alive) return
        setState('ok')
        setMessage(r?.message || 'Почта подтверждена')
        if (isAuthenticated) refreshUser().catch(() => undefined)
      })
      .catch((e) => {
        if (!alive) return
        setState('error')
        setMessage(errorMessage(e, 'Ссылка недействительна или устарела'))
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  return (
    <div className="auth card card--glow verify">
      {state === 'loading' && (
        <>
          <Spinner label="Проверяем ссылку" />
          <p className="muted">Проверяем ссылку…</p>
        </>
      )}
      {state === 'ok' && (
        <>
          <CheckCircle2 size={48} className="text-success" aria-hidden />
          <h1 className="auth__title display">Готово!</h1>
          <p className="muted">{message}</p>
          <LinkButton to={isAuthenticated ? '/app/dashboard' : '/auth'}>{isAuthenticated ? 'В кабинет' : 'Войти'}</LinkButton>
        </>
      )}
      {state === 'error' && (
        <>
          <XCircle size={48} className="text-red" aria-hidden />
          <h1 className="auth__title display">Не получилось</h1>
          <p className="muted">{message}</p>
          <LinkButton to={isAuthenticated ? '/app/dashboard' : '/auth'} variant="ghost">
            {isAuthenticated ? 'В кабинет — отправить письмо повторно' : 'Ко входу'}
          </LinkButton>
        </>
      )}
    </div>
  )
}
