import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'
import { Spinner } from '../../components/ui/States'
import { errorMessage } from '../../lib/format'

/** Возврат от провайдера ФСП ID: обмен кода на вход или привязку (FSP-20). */
export default function FspCallbackPage() {
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const { acceptTokens, isAuthenticated } = useAuth()
  const [error, setError] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (started.current) return // код одноразовый: StrictMode не должен обменять его дважды
    started.current = true
    const code = params.get('code')
    const state = params.get('state')
    const providerError = params.get('error')
    if (providerError) {
      setError(providerError === 'access_denied' ? 'Вход через ФСП ID отменён.' : params.get('error_description') || providerError)
      return
    }
    if (!code || !state) {
      setError('Провайдер ФСП ID не передал код авторизации.')
      return
    }
    api.fspCallback(code, state)
      .then(async (res) => {
        if (res.mode === 'login' && res.tokens) {
          await acceptTokens(res.tokens)
          navigate(res.created ? '/app/profile' : '/app/dashboard', { replace: true, state: { fspLinked: res.fsp_id } })
        } else {
          navigate('/app/settings', { replace: true, state: { fspLinked: res.fsp_id } })
        }
      })
      .catch((e) => setError(errorMessage(e, 'Не удалось завершить вход через ФСП ID')))
  }, [params, navigate, acceptTokens])

  return (
    <div className="auth card card--glow">
      <div className="auth__head">
        <h1 className="auth__title display">ФСП ID</h1>
      </div>
      {error ? (
        <div className="stack">
          <div className="alert alert--error" role="alert">{error}</div>
          <Link className="btn btn--primary" to={isAuthenticated ? '/app/settings' : '/auth'}>
            {isAuthenticated ? 'Вернуться в настройки' : 'Вернуться ко входу'}
          </Link>
        </div>
      ) : (
        <div className="row gap-sm center">
          <Spinner />
          <span className="muted">Проверяем вход через ФСП ID…</span>
        </div>
      )}
    </div>
  )
}
