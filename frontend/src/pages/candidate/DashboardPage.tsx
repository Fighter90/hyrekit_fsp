import { Link } from 'react-router-dom'
import { ArrowRight, Eye, EyeOff, Gauge, Star, Trophy, Mail, ClipboardCheck } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateProfile, Challenge, Invitation } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useAuth } from '../../contexts/AuthContext'
import PageHeader from '../../components/ui/PageHeader'
import Stepper, { type Step } from '../../components/ui/Stepper'
import { candidateSteps } from '../../lib/candidate'
import Stat from '../../components/ui/Stat'
import { CategoryBadge, StatusChip } from '../../components/ui/Badges'
import { LinkButton } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { formatDate, formatSalary } from '../../lib/format'

interface DashData {
  profile: CandidateProfile
  invitations: Invitation[]
  challenges: Challenge[]
}

function nextAction(steps: Step[]) {
  const i = steps.findIndex((s) => !s.done)
  switch (i) {
    case 0:
      return { to: '/app/profile', label: 'Заполнить профиль', text: 'Загрузите резюме — поля заполнятся автоматически.' }
    case 1:
      return { to: '/app/assessment', label: 'Пройти опрос', text: 'Выберите специализацию и заявите грейд.' }
    case 2:
      return { to: '/app/assessment', label: 'Начать тест', text: 'Тест подтвердит грейд и откроет профиль работодателям.' }
    case 3:
      return { to: '/app/assessment', label: 'Пересдать тест', text: 'Категория не присвоена — попробуйте другой грейд.' }
    case 4:
      return { to: '/app/vacancies', label: 'Смотреть вакансии', text: 'Пока ждёте приглашений — откликнитесь сами.' }
    default:
      return { to: '/app/invitations', label: 'К приглашениям', text: 'Работодатели уже пишут вам.' }
  }
}

export default function CandidateDashboardPage() {
  const { user } = useAuth()
  const { data, error, loading, reload } = useAsync<DashData>(async () => {
    // профиль обязателен и запрашивается первым (сервер создаёт его при первом обращении),
    // остальное — параллельно и по возможности
    const profile = await api.getCandidateProfile()
    const [inv, ch] = await Promise.all([
      api.getCandidateInvitations().catch(() => [] as Invitation[]),
      api.getCandidateChallenges().catch(() => [] as Challenge[]),
    ])
    return { profile, invitations: inv, challenges: ch }
  })

  const firstName = user?.full_name?.split(' ')[0]

  return (
    <>
      <PageHeader title={firstName ? `Привет, ${firstName}` : 'Обзор'} subtitle="Ваш путь к приглашениям: профиль → опрос → тест → категория." />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && (
        <div className="grid-2">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={4} />
        </div>
      )}
      {data && <Dashboard {...data} />}
    </>
  )
}

function Dashboard({ profile: p, invitations, challenges }: DashData) {
  const steps = candidateSteps(p, invitations)
  const action = nextAction(steps)
  const fresh = invitations.filter((i) => i.status === 'sent').length
  const challenge = challenges.find((c) => !c.submitted) ?? challenges[0]

  return (
    <div className="stack-lg">
      <Reveal>
        <div className="card">
          <Stepper steps={steps} />
        </div>
      </Reveal>

      <div className="dash-hero">
        <Reveal className="card card--spin dash-hero__main">
          <div className="kicker">ваша категория</div>
          <div className="dash-hero__cat">
            <CategoryBadge title={p.category_title} grade={p.grade} size="lg" />
          </div>
          <div className={`visibility ${p.is_visible ? 'is-on' : ''}`}>
            {p.is_visible ? <Eye size={16} /> : <EyeOff size={16} />}
            {p.is_visible
              ? 'Профиль виден работодателям'
              : !p.category
                ? 'Профиль скрыт: нет подтверждённой категории'
                : 'Профиль скрыт: нужно согласие на обработку данных'}
            {!p.is_visible && p.category && !p.consent_given_at && <Link to="/app/settings">дать согласие →</Link>}
          </div>
          {p.next_grade_change_at && (
            <p className="muted small">Сменить грейд можно с {formatDate(p.next_grade_change_at)}</p>
          )}
          <div className="dash-hero__next">
            <div>
              <strong>Следующий шаг</strong>
              <p className="muted small">{action.text}</p>
            </div>
            <LinkButton to={action.to} iconRight={<ArrowRight size={16} />}>{action.label}</LinkButton>
          </div>
        </Reveal>
        <div className="dash-hero__stats">
          <Stat label="Рейтинг в категории" value={p.rating} icon={<Star size={16} />} hint="из 100" />
          <Stat label="Последний тест" value={p.test_score} icon={<Gauge size={16} />} hint="баллов из 100" tone="white" />
          <Stat
            label="Баллы ФСП"
            value={p.fsp?.has_history ? p.fsp.score : null}
            icon={<Trophy size={16} />}
            tone="red"
            hint={p.fsp_id ? (p.fsp?.has_history ? `${p.fsp.achievements.length} достижений` : 'истории нет') : <Link to="/app/settings">привязать ФСП ID</Link>}
          />
          <Stat label="Новые приглашения" value={fresh} icon={<Mail size={16} />} hint={`всего ${invitations.length}`} />
        </div>
      </div>

      <div className="grid-2">
        <Reveal className="card">
          <div className="card__title row between">
            <span>Последние приглашения</span>
            <Link to="/app/invitations" className="small">все →</Link>
          </div>
          {invitations.length === 0 ? (
            <EmptyState glyph="@" title="Пока пусто" text="Приглашения появятся, когда профиль станет виден работодателям." />
          ) : (
            <ul className="mini-list">
              {invitations.slice(0, 4).map((inv) => (
                <li key={inv.id}>
                  <Link to="/app/invitations" className="mini-list__item">
                    <div className="grow">
                      <strong>{inv.title}</strong>
                      <span className="muted small">{inv.company.name}</span>
                    </div>
                    <span className="salary-sm">{formatSalary(inv.salary_from, inv.salary_to)}</span>
                    <StatusChip status={inv.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Reveal>

        <Reveal className="card card--glow challenge-card" delay={100}>
          <div className="card__title">
            <ClipboardCheck size={18} /> Регулярный челлендж
          </div>
          {challenge ? (
            <>
              <h3 className="challenge-card__title">{challenge.title}</h3>
              <p className="muted small clamp-3">{challenge.description}</p>
              <div className="row between wrap gap-sm mt">
                <span className="small muted">
                  {challenge.company_name}
                  {challenge.due_at && ` · до ${formatDate(challenge.due_at)}`}
                </span>
                <LinkButton to="/app/challenges" size="sm" variant={challenge.submitted ? 'ghost' : 'primary'}>
                  {challenge.submitted ? 'Ответ отправлен' : 'Решить'}
                </LinkButton>
              </div>
            </>
          ) : (
            <EmptyState glyph="</>" title="Челленджей нет" text="Короткие задания от компаний появятся здесь." />
          )}
        </Reveal>
      </div>
    </div>
  )
}
