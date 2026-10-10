import { useState } from 'react'
import { api } from '../../api/client'
import { useToast } from '../../contexts/ToastContext'

/** Напоминание подтвердить почту с повторной отправкой письма. */
export default function VerifyBanner() {
  const toast = useToast()
  const [sent, setSent] = useState(false)
  return (
    <div className="banner">
      <span>Подтвердите почту — ссылка отправлена при регистрации.</span>
      <button
        className="banner__btn"
        disabled={sent}
        onClick={() =>
          api.resendVerification()
            .then((r) => {
              setSent(true)
              toast.success(r?.message || 'Письмо отправлено')
            })
            .catch((e: Error) => toast.error(e.message))
        }
      >
        {sent ? 'Отправлено' : 'Отправить письмо ещё раз'}
      </button>
    </div>
  )
}
