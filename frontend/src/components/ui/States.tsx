import type { ReactNode } from 'react'
import { AlertTriangle, RotateCw } from 'lucide-react'
import { Button } from './Button'

interface EmptyProps {
  glyph?: string
  title: string
  text?: ReactNode
  action?: ReactNode
}

/** Пустое состояние с фирменным кодовым глифом. */
export function EmptyState({ glyph = '{ }', title, text, action }: EmptyProps) {
  return (
    <div className="empty">
      <div className="empty__glyph" aria-hidden>{glyph}</div>
      <h3 className="empty__title">{title}</h3>
      {text && <p className="empty__text">{text}</p>}
      {action && <div className="empty__action">{action}</div>}
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-state" role="alert">
      <AlertTriangle size={20} aria-hidden />
      <div className="error-state__text">
        <strong>Не удалось загрузить</strong>
        <span>{message}</span>
      </div>
      {onRetry && (
        <Button variant="ghost" size="sm" icon={<RotateCw size={14} />} onClick={onRetry}>
          Повторить
        </Button>
      )}
    </div>
  )
}

export function Spinner({ label = 'Загрузка' }: { label?: string }) {
  return (
    <div className="spinner-wrap" role="status" aria-label={label}>
      <span className="spinner" />
    </div>
  )
}
