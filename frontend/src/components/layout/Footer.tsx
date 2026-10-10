import { Link } from 'react-router-dom'
import Logo from '../ui/Logo'

export default function Footer() {
  return (
    <footer className="footer">
      <div className="container footer__inner">
        <div className="footer__brand">
          <Logo plain />
          <p className="footer__tag">Платформа подбора при поддержке ФСП</p>
        </div>
        <nav className="footer__nav" aria-label="Документы">
          <Link to="/privacy">Политика конфиденциальности</Link>
          <Link to="/terms">Пользовательское соглашение</Link>
          <a href="/#faq">Вопросы и ответы</a>
        </nav>
        <div className="footer__meta">
          <img className="footer__fsp" src="/brand/fsp-logo-ru-full-dark.svg" alt="Федерация спортивного программирования России" height={34} />
          <span>© {new Date().getFullYear()} hyrekit.ru</span>
        </div>
      </div>
    </footer>
  )
}
