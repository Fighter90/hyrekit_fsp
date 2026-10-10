import { Check } from 'lucide-react'

export interface Step {
  label: string
  done: boolean
  hint?: string
}

/** Горизонтальный степпер статуса; первый незавершённый шаг — текущий. */
export default function Stepper({ steps }: { steps: Step[] }) {
  const current = steps.findIndex((s) => !s.done)
  return (
    <ol className="stepper">
      {steps.map((s, i) => {
        const state = s.done ? 'done' : i === current ? 'current' : 'todo'
        return (
          <li key={s.label} className={`stepper__step is-${state}`} aria-current={state === 'current' ? 'step' : undefined}>
            <span className="stepper__dot">{s.done ? <Check size={14} /> : i + 1}</span>
            <span className="stepper__label">{s.label}</span>
            {s.hint && <span className="stepper__hint">{s.hint}</span>}
          </li>
        )
      })}
    </ol>
  )
}
