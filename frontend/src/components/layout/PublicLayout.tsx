import { useEffect, useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Logo from '../ui/Logo'
import { LinkButton } from '../ui/Button'
import Footer from './Footer'
import { useAuth } from '../../contexts/AuthContext'

const NAV = [
  { href: '/#how', label: 'Как это работает' },
  { href: '/#testing', label: 'Тестирование' },
  { href: '/#fsp', label: 'ФСП' },
  { href: '/#faq', label: 'FAQ' },
]

export default function PublicLayout() {
  const { isAuthenticated } = useAuth()
  const [open, setOpen] = useState(false)
  const [scrolled, setScrolled] = useState(false)
  const loc = useLocation()

  useEffect(() => setOpen(false), [loc.pathname, loc.hash])

  // Шапка становится «стеклянной» после начала прокрутки
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 12)
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Прокрутка к якорю после перехода
  useEffect(() => {
    if (!loc.hash) return
    const el = document.getElementById(loc.hash.slice(1))
    el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, [loc.hash])

  return (
    <div className="public">
      <div className="bg-grid" aria-hidden />
      <header className={`topbar ${scrolled ? 'is-scrolled' : ''}`}>
        <div className="container topbar__inner">
          <Logo />
          <nav className={`topbar__nav ${open ? 'is-open' : ''}`} aria-label="Основная навигация">
            {NAV.map((n) => (
              <Link key={n.href} to={n.href} className="topbar__link">
                {n.label}
              </Link>
            ))}
            <div className="topbar__cta-mobile">
              {isAuthenticated ? (
                <LinkButton to="/app" block>Открыть кабинет</LinkButton>
              ) : (
                <>
                  <LinkButton to="/auth" variant="ghost" block>Войти</LinkButton>
                  <LinkButton to="/auth?mode=register" block>Регистрация</LinkButton>
                </>
              )}
            </div>
          </nav>
          <div className="topbar__cta">
            {isAuthenticated ? (
              <LinkButton to="/app" size="sm">Открыть кабинет</LinkButton>
            ) : (
              <>
                <Link to="/auth" className="topbar__link">Войти</Link>
                <LinkButton to="/auth?mode=register" size="sm">Регистрация</LinkButton>
              </>
            )}
          </div>
          <button className="icon-btn topbar__burger" onClick={() => setOpen(!open)} aria-label="Меню" aria-expanded={open}>
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>
      <main className="public__main">
        <Outlet />
      </main>
      <Footer />
    </div>
  )
}
