import { useCountUp } from '../../hooks/useCountUp'
import { useInView } from '../../hooks/useReveal'

const fmt = new Intl.NumberFormat('ru-RU')

/** Анимированный счётчик: запускается, когда попадает в зону видимости. */
export default function Counter({ value, suffix = '', decimals = 0 }: { value: number; suffix?: string; decimals?: number }) {
  const { ref, inView } = useInView<HTMLSpanElement>()
  const v = useCountUp(value, inView)
  const text = decimals ? v.toFixed(decimals) : fmt.format(Math.round(v))
  return (
    <span ref={ref} className="counter">
      {text}
      {suffix}
    </span>
  )
}
