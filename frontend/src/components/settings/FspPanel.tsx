import { Trophy, Medal, ShieldCheck } from 'lucide-react'
import type { FspSummary } from '../../api/types'
import { useCatalog } from '../../contexts/CatalogContext'

/** Достижения ФСП: список соревнований с местами и релевантностью специализациям. */
export default function FspPanel({ fsp, compact = false }: { fsp: FspSummary; compact?: boolean }) {
  const { specTitle } = useCatalog()
  if (!fsp.has_history) {
    return (
      <div className="alert alert--info">
        <Trophy size={16} />
        <div>
          <strong>ФСП ID {fsp.fsp_id} привязан, но соревновательной истории пока нет.</strong> <FspVerified fsp={fsp} />
          <div className="small muted">Это не влияет на категорию: рейтинг считается по тесту. Достижения подтянутся после участия в соревнованиях.</div>
        </div>
      </div>
    )
  }
  const items = compact ? fsp.achievements.slice(0, 3) : fsp.achievements
  return (
    <div className="fsp-panel">
      <div className="fsp-panel__head">
        <img src="/brand/fsp-star-dark.svg" alt="" width={34} height={32} />
        <div className="grow">
          <strong>{fsp.athlete_name || 'Спортсмен ФСП'}</strong>
          <div className="muted small">ФСП ID {fsp.fsp_id} · {fsp.achievements.length} достижений <FspVerified fsp={fsp} /></div>
        </div>
        <div className="fsp-panel__score">
          <span className="display">{Math.round(fsp.score)}</span>
          <small>баллы ФСП</small>
        </div>
      </div>
      <ul className="achievements">
        {items.map((a, i) => (
          <li key={`${a.event}-${a.year}-${i}`} className="achievement">
            <span className={`achievement__place ${a.place && a.place <= 3 ? `is-top place-${a.place}` : ''}`}>
              {a.place ? (a.place <= 3 ? <Medal size={16} /> : `#${a.place}`) : '—'}
              {a.place && a.place <= 3 ? <b>{a.place}</b> : null}
            </span>
            <div className="grow">
              <strong>{a.event}</strong>
              <div className="muted small">
                {a.discipline} · {a.level} · {a.year}
                {a.role && ` · ${a.role}`}
              </div>
            </div>
            {a.relevant_to.length > 0 && (
              <div className="tags">
                {a.relevant_to.map((r) => <span className="tag tag--hit" key={r}>{specTitle(r)}</span>)}
              </div>
            )}
          </li>
        ))}
      </ul>
      {compact && fsp.achievements.length > items.length && <p className="muted tiny">и ещё {fsp.achievements.length - items.length}</p>}
    </div>
  )
}

/** Отметка источника ФСП ID: подтверждён входом через ФСП ID или введён вручную (FSP-20). */
export function FspVerified({ fsp }: { fsp: FspSummary }) {
  return fsp.verified ? (
    <span className="fsp-verified is-on" title="Кандидат вошёл через ФСП ID: идентификатор принадлежит ему">
      <ShieldCheck size={12} /> подтверждён ФСП ID
    </span>
  ) : (
    <span className="fsp-verified muted" title="Идентификатор введён вручную, владение не проверялось">введён вручную</span>
  )
}
