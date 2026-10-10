/*
 * Фирменная полоса кодовых глифов ФСП: { } < / > // ▲ ● |
 * Бесконечная прокрутка (marquee): контент дублируется, анимация сдвигает на 50%.
 */

type Tone = 'b' | 'r' | 'w'
const PATTERN: [string, Tone][] = [
  ['●', 'r'], ['{', 'b'], ['•', 'w'], ['}', 'b'], ['▲', 'b'], ['</>', 'b'], ['//', 'r'], ['[ ]', 'b'],
  ['>|<', 'w'], ['—', 'b'], ['▲', 'w'], ['{', 'r'], ['/', 'w'], ['}', 'r'], ['●', 'w'], ['<', 'b'],
  ['/', 'r'], ['>', 'b'], ['|', 'r'], ['::', 'w'], ['{•}', 'b'], ['▲', 'r'], ['//', 'w'], ['●', 'b'],
]

interface Props {
  reverse?: boolean
  speed?: number // секунд на цикл
  className?: string
}

export default function GlyphStrip({ reverse = false, speed = 40, className = '' }: Props) {
  const row = PATTERN.map(([g, t], i) => (
    <span key={i} className={`glyph glyph--${t}`}>{g}</span>
  ))
  return (
    <div className={`glyph-strip ${className}`} aria-hidden>
      <div className={`glyph-strip__track ${reverse ? 'is-reverse' : ''}`} style={{ animationDuration: `${speed}s` }}>
        <div className="glyph-strip__row">{row}</div>
        <div className="glyph-strip__row">{row}</div>
      </div>
    </div>
  )
}
