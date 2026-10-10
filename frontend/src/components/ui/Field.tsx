import type { ReactNode } from 'react'

interface Props {
  label: string
  htmlFor?: string
  hint?: ReactNode
  error?: string | null
  required?: boolean
  children: ReactNode
  className?: string
}

/** Обёртка поля формы: подпись, подсказка, ошибка. */
export default function Field({ label, htmlFor, hint, error, required, children, className }: Props) {
  return (
    <div className={`field ${error ? 'field--error' : ''} ${className ?? ''}`}>
      <label className="field__label" htmlFor={htmlFor}>
        {label}
        {required && <span className="field__req" aria-hidden> *</span>}
      </label>
      {children}
      {error ? (
        <div className="field__error" role="alert">{error}</div>
      ) : hint ? (
        <div className="field__hint">{hint}</div>
      ) : null}
    </div>
  )
}
