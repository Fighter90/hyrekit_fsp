import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  LayoutDashboard, UserRound, ClipboardCheck, Mail, Briefcase, Trophy, Settings, LogOut, Menu, X,
  Building2, Users, Send, Search, Bookmark,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import Logo from '../ui/Logo'
import { useAuth } from '../../contexts/AuthContext'
import type { Role } from '../../api/types'
import VerifyBanner from './VerifyBanner'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

// Навигация зависит от роли: у кандидата и работодателя разные кабинеты
const NAV_BY_ROLE: Record<Role, NavItem[]> = {
  candidate: [
    { to: '/app/dashboard', label: 'Обзор', icon: LayoutDashboard },
    { to: '/app/profile', label: 'Профиль', icon: UserRound },
    { to: '/app/assessment', label: 'Тестирование', icon: ClipboardCheck },
    { to: '/app/invitations', label: 'Приглашения', icon: Mail },
    { to: '/app/vacancies', label: 'Вакансии', icon: Briefcase },
    { to: '/app/challenges', label: 'Челленджи', icon: Trophy },
    { to: '/app/settings', label: 'Настройки', icon: Settings },
  ],
  employer: [
    { to: '/app/dashboard', label: 'Обзор', icon: LayoutDashboard },
    { to: '/app/company', label: 'Компания', icon: Building2 },
    { to: '/app/vacancies', label: 'Потребности', icon: Briefcase },
    { to: '/app/candidates', label: 'Банк кандидатов', icon: Search },
    { to: '/app/favorites', label: 'Избранное', icon: Bookmark },
    { to: '/app/invitations', label: 'Приглашения и отклики', icon: Send },
    { to: '/app/challenges', label: 'Челленджи', icon: Trophy },
    { to: '/app/settings', label: 'Настройки', icon: Settings },
  ],
}

const ROLE_LABEL: Record<Role, string> = { candidate: 'Кандидат', employer: 'Работодатель' }

export default function AppLayout() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const loc = useLocation()
  const navigate = useNavigate()

  useEffect(() => setOpen(false), [loc.pathname])

  if (!user) return null
  const nav = NAV_BY_ROLE[user.role]
  const initials = (user.full_name || user.email).split(/[\s@]/).filter(Boolean).slice(0, 2).map((s) => s[0]?.toUpperCase()).join('')

  return (
    <div className="shell">
      <div className="bg-grid bg-grid--faint" aria-hidden />
      <aside className={`sidebar ${open ? 'is-open' : ''}`}>
        <div className="sidebar__top">
          <Logo to="/app/dashboard" short />
          <button className="icon-btn sidebar__close" onClick={() => setOpen(false)} aria-label="Закрыть меню">
            <X size={18} />
          </button>
        </div>
        <div className="sidebar__role">
          <span className={`role-dot role-dot--${user.role}`} />
          {ROLE_LABEL[user.role]}
        </div>
        <nav className="sidebar__nav" aria-label="Кабинет">
          {nav.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={({ isActive }) => `sidebar__link ${isActive ? 'is-active' : ''}`}>
              <Icon size={18} aria-hidden />
              <span>{label}</span>
            </NavLink>
          ))}
        </nav>
        <div className="sidebar__foot">
          <div className="sidebar__user">
            <span className="avatar">{initials || <Users size={14} />}</span>
            <div className="sidebar__user-text">
              <strong>{user.full_name || 'Без имени'}</strong>
              <small>{user.email}</small>
            </div>
          </div>
          <button
            className="sidebar__link sidebar__logout"
            onClick={() => {
              logout()
              navigate('/')
            }}
          >
            <LogOut size={18} aria-hidden />
            <span>Выйти</span>
          </button>
        </div>
      </aside>
      {open && <div className="sidebar-scrim" onClick={() => setOpen(false)} aria-hidden />}

      <div className="shell__main">
        <header className="mobilebar">
          <button className="icon-btn" onClick={() => setOpen(true)} aria-label="Открыть меню">
            <Menu size={20} />
          </button>
          <Logo to="/app/dashboard" short />
          <span className="avatar avatar--sm">{initials}</span>
        </header>
        {!user.is_verified && <VerifyBanner />}
        <main className="shell__content" key={loc.pathname}>
          <Outlet />
        </main>
      </div>
    </div>
  )
}
