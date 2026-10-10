import type { ReactNode } from 'react'
import Counter from './Counter'

interface Props {
  label: string
  value: number | null | undefined
  suffix?: string
  icon?: ReactNode
  hint?: ReactNode
  tone?: 'blue' | 'red' | 'white'
}

/** Карточка показателя с анимированным числом. */
export default function Stat({ label, value, suffix, icon, hint, tone = 'blue' }: Props) {
  return (
    <div className={`stat card card--glow stat--${tone}`}>
      <div className="stat__head">
        <span className="stat__label">{label}</span>
        {icon && <span className="stat__icon">{icon}</span>}
      </div>
      <div className="stat__value">
        {value === null || value === undefined ? '—' : <Counter value={value} suffix={suffix} />}
      </div>
      {hint && <div className="stat__hint">{hint}</div>}
    </div>
  )
}
