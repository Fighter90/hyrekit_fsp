import type { InvitationStatus } from '../../api/types'
import { STATUS_LABEL, gradeLabel } from '../../lib/format'

export function StatusChip({ status }: { status: InvitationStatus }) {
  return <span className={`status status--${status}`}>{STATUS_LABEL[status] ?? status}</span>
}

/** Бейдж категории «Backend · Middle» с подсветкой грейда. */
export function CategoryBadge({ title, grade, size = 'md' }: { title: string | null; grade?: string | null; size?: 'md' | 'lg' }) {
  if (!title) return <span className="cat-badge cat-badge--none">Категория не присвоена</span>
  return (
    <span className={`cat-badge cat-badge--${size} ${grade ? `grade--${grade}` : ''}`}>
      <span className="cat-badge__bracket" aria-hidden>[</span>
      {title}
      <span className="cat-badge__bracket" aria-hidden>]</span>
    </span>
  )
}

export function GradePill({ grade }: { grade: string | null | undefined }) {
  if (!grade) return null
  return <span className={`grade-pill grade--${grade}`}>{gradeLabel(grade)}</span>
}

export function Tags({ items, highlight = [], missing = [], limit }: { items: string[]; highlight?: string[]; missing?: string[]; limit?: number }) {
  const hl = new Set(highlight.map((s) => s.toLowerCase()))
  const shown = limit ? items.slice(0, limit) : items
  const rest = limit ? items.length - shown.length : 0
  return (
    <div className="tags">
      {shown.map((t) => (
        <span key={t} className={`tag ${hl.has(t.toLowerCase()) ? 'tag--hit' : ''}`}>{t}</span>
      ))}
      {missing.map((t) => (
        <span key={`m-${t}`} className="tag tag--miss" title="Нет в стеке кандидата">{t}</span>
      ))}
      {rest > 0 && <span className="tag tag--more">+{rest}</span>}
    </div>
  )
}

export function FspBadge({ score }: { score: number }) {
  return (
    <span className="fsp-badge" title="Достижения в соревнованиях ФСП">
      <img src="/brand/fsp-star-dark.svg" alt="" width={14} height={13} />
      ФСП {Math.round(score)}
    </span>
  )
}
