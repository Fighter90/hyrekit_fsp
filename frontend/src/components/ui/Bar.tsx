import { useInView } from '../../hooks/useReveal'

interface Props {
  label: string
  value: number // 0..max
  max?: number
  suffix?: string
  tone?: 'blue' | 'red' | 'white'
}

/** Горизонтальная шкала с анимацией заполнения при появлении. */
export default function Bar({ label, value, max = 100, suffix, tone = 'blue' }: Props) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0
  return (
    <div className="bar" ref={ref}>
      <div className="bar__head">
        <span className="bar__label">{label}</span>
        <span className="bar__value">{suffix ?? `${Math.round(pct)}%`}</span>
      </div>
      <div className="bar__track" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={`bar__fill bar__fill--${tone}`} style={{ width: inView ? `${pct}%` : 0 }} />
      </div>
    </div>
  )
}
