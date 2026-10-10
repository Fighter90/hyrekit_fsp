import { Link } from 'react-router-dom'

interface Props {
  to?: string
  compact?: boolean
}

/** Логотип: звезда ФСП + словесный знак HyreKit акцентным шрифтом TDAText. */
export default function Logo({ to = '/', compact = false }: Props) {
  return (
    <Link to={to} className="logo" aria-label="HyreKit — на главную">
      <img src="/brand/fsp-star-dark.svg" alt="" className="logo__star" width={30} height={28} />
      {!compact && (
        <span className="logo__word">
          Hyre<span className="logo__accent">Kit</span>
        </span>
      )}
    </Link>
  )
}
