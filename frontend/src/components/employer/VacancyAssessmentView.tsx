import { Clock, Layers, Equal } from 'lucide-react'
import { api } from '../../api/client'
import type { AttemptItem } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { ErrorState } from '../ui/States'
import { SkeletonCard } from '../ui/Skeleton'
import { DIFFICULTY_LABEL, sameProfile } from '../../lib/assessment'
import { gradeLabel } from '../../lib/format'

/**
 * «Тест под вакансию»: какие темы система выбрала из описания и стека вакансии
 * и два варианта заданий — разные формулировки при одинаковом профиле сложности.
 */
export default function VacancyAssessmentView({ vacancyId }: { vacancyId: string }) {
  const { specTitle } = useCatalog()
  const { data, error, loading, reload } = useAsync(() => api.getVacancyAssessment(vacancyId), [vacancyId])

  if (error) return <ErrorState message={error} onRetry={reload} />
  if (loading || !data) return <div className="grid-2"><SkeletonCard lines={5} /><SkeletonCard lines={5} /></div>

  const equal = sameProfile(data)
  const minutes = Math.round(data.seconds / 60)

  return (
    <div className="stack-lg va">
      <div className="card va__summary">
        <div className="va__facts">
          <span><Layers size={16} /> {specTitle(data.specialization)} · {gradeLabel(data.grade)} (уровень {data.grade_level})</span>
          <span><Clock size={16} /> {minutes} мин на попытку</span>
          <span className={equal ? 'text-success' : 'text-red'}><Equal size={16} /> {equal ? 'Сложность вариантов совпадает' : 'Профили сложности различаются'}</span>
        </div>
        <h2 className="va__title">Темы теста и почему они выбраны</h2>
        <ul className="va__topics">
          {data.topics.map((t) => (
            <li key={t.topic}>
              <strong>{t.title}</strong>
              <span className="muted small">{t.reason}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="va__variants">
        {data.variants.map((v, vi) => (
          <section key={vi} className="card va__variant">
            <header className="va__variant-head">
              <h3>Вариант {String.fromCharCode(65 + vi)}</h3>
              <DifficultyProfile profile={v.difficulty_profile} />
            </header>
            <ol className="va__items">
              {v.items.map((it, i) => (
                <VariantItem key={it.id} item={it} n={i + 1} />
              ))}
            </ol>
          </section>
        ))}
      </div>
      <p className="muted small">
        Задания параметрические: у каждого кандидата свои числа, данные и порядок вариантов, а сложность позиций одинакова —
        поэтому результаты разных кандидатов сравнимы, а «слитые» ответы бесполезны.
      </p>
    </div>
  )
}

function DifficultyProfile({ profile }: { profile: number[] }) {
  return (
    <div className="dprof" aria-label={`Профиль сложности: ${profile.join(', ')}`}>
      {profile.map((d, i) => (
        <span key={i} className="dprof__bar" style={{ height: `${(d / 5) * 100}%` }} title={`${i + 1}: ${DIFFICULTY_LABEL[d] ?? d}`} />
      ))}
    </div>
  )
}

function VariantItem({ item, n }: { item: AttemptItem; n: number }) {
  return (
    <li className="va__item">
      <div className="row between gap-sm small">
        <span className="muted">{n}. {item.topic}</span>
        <span className="difficulty" title={`Сложность ${item.difficulty} из 5`}>
          {Array.from({ length: 5 }, (_, i) => <i key={i} className={i < item.difficulty ? 'is-on' : ''} />)}
        </span>
      </div>
      <p className="va__stem">{item.stem}</p>
      {item.code && <pre className="code-block code-block--sm"><code>{item.code}</code></pre>}
      {item.options.length > 0 && (
        <ul className="va__opts">
          {item.options.map((o, i) => <li key={i}>{String.fromCharCode(65 + i)}. {o}</li>)}
        </ul>
      )}
    </li>
  )
}
