import { useCountUp } from '../../hooks/useCountUp'
import { useInView } from '../../hooks/useReveal'

interface Props {
  value: number // 0..100
  size?: number
  label?: string
  stroke?: number
}

/** Кольцевой индикатор результата с анимацией заполнения и счётчиком. */
export default function ScoreRing({ value, size = 160, label = 'баллов', stroke = 10 }: Props) {
  const { ref, inView } = useInView<HTMLDivElement>()
  const v = Math.max(0, Math.min(100, value))
  const shown = useCountUp(v, inView, 1400)
  const r = (size - stroke) / 2
  const c = 2 * Math.PI * r
  const tone = v >= 70 ? 'good' : v >= 45 ? 'mid' : 'low'

  return (
    <div ref={ref} className={`ring ring--${tone}`} style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden>
        <defs>
          <linearGradient id="ringGrad" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--blue-bright)" />
            <stop offset="100%" stopColor="var(--red)" />
          </linearGradient>
        </defs>
        <circle cx={size / 2} cy={size / 2} r={r} className="ring__track" strokeWidth={stroke} fill="none" />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          className="ring__bar"
          strokeWidth={stroke}
          fill="none"
          strokeDasharray={c}
          strokeDashoffset={c - (c * shown) / 100}
          strokeLinecap="round"
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div className="ring__center" role="img" aria-label={`${Math.round(v)} из 100`}>
        <span className="ring__value">{Math.round(shown)}</span>
        <span className="ring__label">{label}</span>
      </div>
    </div>
  )
}
