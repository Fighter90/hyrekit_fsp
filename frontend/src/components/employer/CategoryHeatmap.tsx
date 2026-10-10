import type { CSSProperties } from 'react'
import { useNavigate } from 'react-router-dom'
import type { CategoryStat, Grade } from '../../api/types'
import { useCatalog } from '../../contexts/CatalogContext'
import { GRADE_ORDER, gradeLabel } from '../../lib/format'

/**
 * Тепловая карта «специализация × грейд»: яркость ячейки пропорциональна
 * числу кандидатов (корень — чтобы малые значения тоже были заметны).
 */
export default function CategoryHeatmap({ stats }: { stats: CategoryStat[] }) {
  const { catalog, specTitle } = useCatalog()
  const navigate = useNavigate()
  const specs = catalog?.specializations.map((s) => s.code) ?? [...new Set(stats.map((s) => s.specialization))]
  const grades: Grade[] = catalog?.grades.slice().sort((a, b) => a.order - b.order).map((g) => g.code) ?? GRADE_ORDER
  const byKey = new Map(stats.map((s) => [`${s.specialization}:${s.grade}`, s]))
  const max = Math.max(1, ...stats.map((s) => s.count))

  return (
    <div className="heatmap" style={{ gridTemplateColumns: `minmax(90px, 140px) repeat(${grades.length}, minmax(52px, 1fr))` }}>
      <span />
      {grades.map((g) => <span key={g} className="heatmap__col">{gradeLabel(g)}</span>)}
      {specs.map((sp) => (
        <div className="heatmap__row" key={sp} style={{ display: 'contents' }}>
          <span className="heatmap__rowhead">{specTitle(sp)}</span>
          {grades.map((g) => {
            const st = byKey.get(`${sp}:${g}`)
            const count = st?.count ?? 0
            const alpha = count ? 0.15 + 0.85 * Math.sqrt(count / max) : 0
            return (
              <button
                key={g}
                className={`heatmap__cell ${count ? '' : 'is-empty'}`}
                style={{ '--a': alpha } as CSSProperties}
                title={`${st?.title ?? `${specTitle(sp)} · ${gradeLabel(g)}`}: ${count} канд.${st?.with_fsp ? `, с ФСП: ${st.with_fsp}` : ''}`}
                onClick={() => navigate(`/app/candidates?specialization=${sp}&grade=${g}`)}
                disabled={!count}
              >
                <span className="heatmap__count">{count || ''}</span>
                {st?.with_fsp ? <span className="heatmap__fsp">★{st.with_fsp}</span> : null}
              </button>
            )
          })}
        </div>
      ))}
    </div>
  )
}
