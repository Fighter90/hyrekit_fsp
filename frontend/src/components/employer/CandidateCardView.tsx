import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { MapPin, Gauge, Star } from 'lucide-react'
import type { CandidateCard } from '../../api/types'
import { CategoryBadge, FspBadge, StatusChip, Tags } from '../ui/Badges'
import { experienceLabel, formatSalary, workFormatLabel } from '../../lib/format'

interface Props {
  c: CandidateCard
  highlight?: string[]
  missing?: string[]
  actions?: ReactNode
  aside?: ReactNode
  children?: ReactNode
  rank?: number
}

/** Карточка кандидата для работодателя (банк, подборка). */
export default function CandidateCardView({ c, highlight = [], missing = [], actions, aside, children, rank }: Props) {
  return (
    <article className="card card--glow card--hover cand">
      {rank !== undefined && <span className="cand__rank">#{rank}</span>}
      <div className="cand__head">
        <span className="avatar">{c.display_name.replace(/[^\p{L}\d]/gu, '').slice(0, 2).toUpperCase() || '?'}</span>
        <div className="grow">
          <Link to={`/app/candidates/${c.id}`} className="cand__name">{c.display_name}</Link>
          <div className="muted small">{c.headline ?? 'Заголовок не указан'}</div>
        </div>
        {aside}
      </div>
      <div className="row wrap gap-sm">
        <CategoryBadge title={c.category_title} grade={c.grade} />
        {c.fsp?.has_history && <FspBadge score={c.fsp.score} />}
        {c.invitation_status && <StatusChip status={c.invitation_status} />}
      </div>
      <div className="cand__meta small muted">
        {c.test_score !== null && <span><Gauge size={13} /> тест {Math.round(c.test_score)}</span>}
        {c.rating !== null && <span><Star size={13} /> рейтинг {Math.round(c.rating)}</span>}
        <span>{experienceLabel(c.experience_years)}</span>
        {c.city && <span><MapPin size={13} /> {c.city}</span>}
        {c.work_format && <span>{workFormatLabel(c.work_format)}</span>}
        {(c.salary_from || c.salary_to) && <span className="text-success">{formatSalary(c.salary_from, c.salary_to)}</span>}
      </div>
      <Tags items={c.stack} highlight={highlight} missing={missing} limit={12} />
      {children}
      {actions && <div className="cand__actions">{actions}</div>}
    </article>
  )
}
