import { Link } from 'react-router-dom'

interface Props {
  to?: string
  /** Без логотипа ФСП: узкие места, где он уже стоит рядом. */
  plain?: boolean
  /** Короткий знак ФСП вместо полного (боковое меню, мобильная шапка). */
  short?: boolean
}

/** Словесный знак HyreKit в связке с официальным логотипом Федерации спортивного программирования. */
export default function Logo({ to = '/', plain = false, short = false }: Props) {
  return (
    <span className="logo-lockup">
      <Link to={to} className="logo" aria-label="HyreKit — на главную">
        <span className="logo__word">
          Hyre<span className="logo__accent">Kit</span>
        </span>
      </Link>
      {!plain && (
        <>
          <span className="logo-lockup__sep" aria-hidden />
          <a
            href="https://fsp-russia.com"
            target="_blank"
            rel="noreferrer"
            className={`logo-fsp ${short ? 'logo-fsp--short' : ''}`}
            aria-label="Федерация спортивного программирования России"
          >
            <img className="logo-fsp__full" src="/brand/fsp-logo-ru-full-dark.svg" alt="" />
            <img className="logo-fsp__short" src="/brand/fsp-logo-ru-short-dark.svg" alt="" />
          </a>
        </>
      )}
    </span>
  )
}
