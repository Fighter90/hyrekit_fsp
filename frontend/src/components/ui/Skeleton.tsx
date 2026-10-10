interface Props {
  lines?: number
  height?: number | string
  className?: string
}

export function Skeleton({ height = 14, className = '' }: { height?: number | string; className?: string }) {
  return <div className={`skeleton ${className}`} style={{ height }} aria-hidden />
}

/** Скелетон карточки — пока данные загружаются. */
export function SkeletonCard({ lines = 3, className = '' }: Props) {
  return (
    <div className={`card skeleton-card ${className}`} aria-busy="true" aria-label="Загрузка">
      <Skeleton height={20} className="w-40" />
      {Array.from({ length: lines }, (_, i) => (
        <Skeleton key={i} className={i === lines - 1 ? 'w-60' : 'w-100'} />
      ))}
    </div>
  )
}

export function SkeletonList({ count = 3, lines = 3 }: { count?: number; lines?: number }) {
  return (
    <div className="stack">
      {Array.from({ length: count }, (_, i) => <SkeletonCard key={i} lines={lines} />)}
    </div>
  )
}
