import { Link } from 'react-router-dom'
import { CalendarClock, Users, Trophy, Timer, AlertTriangle, Snowflake } from 'lucide-react'
import type { ArenaBoard, ArenaBoardRow, ArenaRatingInfo, ArenaRound, ArenaVerdict } from '../../api/types'
import { formatDateTime, plural } from '../../lib/format'
import { VERDICT_LABEL, formatClock } from '../../lib/arena'

export function VerdictChip({ verdict }: { verdict: ArenaVerdict | null }) {
  if (!verdict) return <span className="verdict verdict--wait">Проверяется</span>
  return (
    <span className={`verdict verdict--${verdict === 'OK' ? 'ok' : 'bad'}`} title={VERDICT_LABEL[verdict]}>
      {verdict}
    </span>
  )
}

const STATE_LABEL = { running: 'Идёт', upcoming: 'Скоро', finished: 'Завершён' } as const

export function RoundCard({ round: r }: { round: ArenaRound }) {
  const p = r.participation
  return (
    <Link to={`/app/arena/${r.id}`} className="card card--hover arena-round">
      <div className="row between wrap gap-sm">
        <span className={`arena-state arena-state--${r.state}`}>{r.is_open ? 'Открыт всегда' : STATE_LABEL[r.state]}</span>
        {r.sponsor && <span className="small muted">Раунд компании {r.sponsor}</span>}
      </div>
      <h3 className="arena-round__title">{r.title}</h3>
      {r.description && <p className="small muted">{r.description}</p>}
      <div className="row wrap gap-sm small muted mt-sm">
        {r.is_open ? (
          <span><Timer size={14} /> {r.duration_minutes} мин на участника</span>
        ) : (
          <span><CalendarClock size={14} /> {formatDateTime(r.starts_at)} · {r.duration_minutes} мин</span>
        )}
        <span><Users size={14} /> {r.participants} {plural(r.participants, ['участник', 'участника', 'участников'])}</span>
        <span>{r.problems.length} {plural(r.problems.length, ['задача', 'задачи', 'задач'])}</span>
        {r.specialization_title && <span className="tag">{r.specialization_title}</span>}
      </div>
      {r.prize && <div className="small mt-sm"><Trophy size={14} /> {r.prize}</div>}
      {p && (
        <div className="small mt-sm">
          {p.active ? `Вы участвуете: осталось ${formatClock(p.seconds_left)}` : `Решено ${p.solved}, штраф ${p.penalty}`}
          {p.rating_after !== null && ` · рейтинг ${Math.round(p.rating_after)}`}
        </div>
      )}
    </Link>
  )
}

export function RatingChart({ history }: { history: ArenaRatingInfo['history'] }) {
  if (history.length === 0) return null
  const pts = [{ rating: 1500 }, ...history]
  const values = pts.map((p) => p.rating)
  const lo = Math.min(...values) - 40
  const hi = Math.max(...values) + 40
  const w = 320
  const h = 90
  const x = (i: number) => (pts.length === 1 ? w / 2 : (i * w) / (pts.length - 1))
  const y = (v: number) => h - ((v - lo) / (hi - lo)) * h
  const d = pts.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.rating).toFixed(1)}`).join(' ')
  return (
    <svg className="rating-chart" viewBox={`0 0 ${w} ${h}`} role="img" aria-label="История рейтинга Arena" preserveAspectRatio="none">
      <path d={d} fill="none" strokeWidth="2" />
      {pts.map((p, i) => (
        <circle key={i} cx={x(i)} cy={y(p.rating)} r="3">
          <title>{Math.round(p.rating)}</title>
        </circle>
      ))}
    </svg>
  )
}

interface BoardProps {
  board: ArenaBoard
  onInvite?: (row: ArenaBoardRow) => void
}

export function Leaderboard({ board, onInvite }: BoardProps) {
  return (
    <div className="card arena-board">
      {board.frozen && (
        <div className="alert alert--info small">
          <Snowflake size={14} /> Таблица заморожена до конца раунда: чужие результаты после заморозки скрыты, свои видны.
        </div>
      )}
      {board.rows.length === 0 ? (
        <p className="muted small">Пока никто не участвует.</p>
      ) : (
        <div className="table-wrap">
          <table className="table arena-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Участник</th>
                {board.problems.map((p, i) => (
                  <th key={p.code} title={p.title}>{String.fromCharCode(65 + i)}</th>
                ))}
                <th title="Решено задач">Решено</th>
                <th title="Штраф в минутах">Штраф</th>
                {onInvite && <th />}
              </tr>
            </thead>
            <tbody>
              {board.rows.map((r) => (
                <tr key={r.participant_id} className={r.me ? 'is-me' : ''}>
                  <td>{r.rank}</td>
                  <td>
                    <div className="row gap-sm">
                      <span>{r.name}</span>
                      {r.me && <span className="tag">вы</span>}
                      {r.suspicious && (
                        <span className="text-warn" title="Решение почти совпадает с решением другого участника">
                          <AlertTriangle size={14} />
                        </span>
                      )}
                    </div>
                    <div className="tiny muted">
                      {r.category_title ?? 'без категории'}
                      {r.arena_rating !== null && ` · ${r.arena_rating}`}
                    </div>
                  </td>
                  {board.problems.map((p) => {
                    const c = r.cells[p.code]
                    return (
                      <td key={p.code} className={c?.solved ? 'cell-ok' : c?.attempts ? 'cell-bad' : ''}>
                        {c?.solved ? `+${c.attempts || ''}` : c?.attempts ? `−${c.attempts}` : ''}
                        {c?.solved && <div className="tiny muted">{c.minute} мин</div>}
                      </td>
                    )
                  })}
                  <td><strong>{r.solved}</strong></td>
                  <td>{r.penalty}</td>
                  {onInvite && (
                    <td>
                      {r.profile_id && (
                        <button className="btn btn--sm btn--secondary" onClick={() => onInvite(r)} disabled={r.invitation_status === 'sent' || r.invitation_status === 'viewed'}>
                          {r.invitation_status === 'accepted' ? 'Принято' : r.invitation_status === 'sent' || r.invitation_status === 'viewed' ? 'Отправлено' : 'Пригласить'}
                        </button>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
