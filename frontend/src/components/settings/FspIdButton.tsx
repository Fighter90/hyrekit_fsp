import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import type { FspFlowMode } from '../../api/types'
import { Button } from '../ui/Button'
import { errorMessage } from '../../lib/format'

/**
 * Кнопка входа или привязки через ФСП ID (FSP-20). Бэкенд готовит запрос
 * авторизации (state, nonce, PKCE в HttpOnly-cookie), браузер уходит на
 * страницу провайдера и возвращается на /fsp-callback.
 */
export default function FspIdButton({
  mode,
  label,
  variant = 'secondary',
  size,
  block,
  onError,
}: {
  mode: FspFlowMode
  label?: string
  variant?: 'primary' | 'secondary' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
  block?: boolean
  onError?: (message: string) => void
}) {
  const [enabled, setEnabled] = useState<boolean | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    api.fspConfig()
      .then((c) => alive && setEnabled(c.enabled))
      .catch(() => alive && setEnabled(false))
    return () => {
      alive = false
    }
  }, [])

  if (!enabled) return null

  const go = async () => {
    setBusy(true)
    try {
      const { authorize_url } = await api.fspStart(mode)
      window.location.assign(authorize_url)
    } catch (e) {
      setBusy(false)
      onError?.(errorMessage(e, 'Не удалось открыть вход ФСП ID'))
    }
  }

  return (
    <Button
      type="button"
      variant={variant}
      size={size}
      block={block}
      loading={busy}
      icon={<img src="/brand/fsp-star-dark.svg" alt="" width={18} height={17} />}
      onClick={go}
    >
      {label ?? (mode === 'login' ? 'Войти через ФСП ID' : 'Привязать через ФСП ID')}
    </Button>
  )
}
