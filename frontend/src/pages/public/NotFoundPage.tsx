import { LinkButton } from '../../components/ui/Button'

export default function NotFoundPage({ inApp = false }: { inApp?: boolean }) {
  return (
    <div className="notfound">
      <div className="notfound__code notfound__glitch" aria-hidden>404</div>
      <h1 className="display-sm">Страница не найдена</h1>
      <p className="muted">{'// такого маршрута нет — возможно, ссылка устарела'}</p>
      <LinkButton to={inApp ? '/app/dashboard' : '/'}>{inApp ? 'В кабинет' : 'На главную'}</LinkButton>
    </div>
  )
}
