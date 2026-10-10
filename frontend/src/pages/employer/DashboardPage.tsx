import { Link } from 'react-router-dom'
import { Briefcase, Send, Inbox, CheckCircle2, Plus, Search } from 'lucide-react'
import { api } from '../../api/client'
import type { Application, CategoryStat, Company, Invitation, Vacancy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import PageHeader from '../../components/ui/PageHeader'
import Stat from '../../components/ui/Stat'
import Bar from '../../components/ui/Bar'
import { LinkButton } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import CategoryHeatmap from '../../components/employer/CategoryHeatmap'
import { STATUS_LABEL, formatSalary } from '../../lib/format'

interface Data {
  company: Company | null
  vacancies: Vacancy[]
  invitations: Invitation[]
  applications: Application[]
  categories: CategoryStat[]
}

const safe = <T,>(p: Promise<T>, fallback: T) => p.catch(() => fallback)

export default function EmployerDashboardPage() {
  const { data, error, loading, reload } = useAsync<Data>(async () => {
    const [company, vacancies, invitations, applications, categories] = await Promise.all([
      safe(api.getCompany(), null),
      api.getEmployerVacancies(),
      safe(api.getEmployerInvitations(), [] as Invitation[]),
      safe(api.getEmployerApplications(), [] as Application[]),
      safe(api.getCategories(), [] as CategoryStat[]),
    ])
    return { company, vacancies, invitations, applications, categories }
  })

  return (
    <>
      <PageHeader
        
        title={data?.company?.name || 'Обзор'}
        subtitle="Опишите потребность — система подберёт кандидатов с подтверждённой категорией."
        actions={<LinkButton to="/app/vacancies/new" icon={<Plus size={16} />}>Новая потребность</LinkButton>}
      />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <div className="grid-4">{[0, 1, 2, 3].map((i) => <SkeletonCard key={i} lines={1} />)}</div>}
      {data && <Body {...data} />}
    </>
  )
}

function Body({ company, vacancies, invitations, applications, categories }: Data) {
  const published = vacancies.filter((v) => v.is_published).length
  const byStatus = (s: Invitation['status']) => invitations.filter((i) => i.status === s).length
  const newApps = applications.filter((a) => a.status === 'sent').length
  const totalCandidates = categories.reduce((a, c) => a + c.count, 0)
  const withFsp = categories.reduce((a, c) => a + c.with_fsp, 0)

  return (
    <div className="stack-lg">
      {!company?.name && (
        <div className="alert alert--warn">
          <Briefcase size={16} />
          <div className="grow">Заполните профиль компании — кандидаты увидят его в приглашениях.</div>
          <Link to="/app/company">Заполнить →</Link>
        </div>
      )}

      <div className="grid-4">
        <Stat label="Потребности" value={vacancies.length} icon={<Briefcase size={16} />} hint={`опубликовано ${published}`} />
        <Stat label="Приглашения" value={invitations.length} icon={<Send size={16} />} hint={`принято ${byStatus('accepted')}`} tone="white" />
        <Stat label="Отклики" value={applications.length} icon={<Inbox size={16} />} hint={`новых ${newApps}`} tone="red" />
        <Stat label="Кандидатов в банке" value={totalCandidates} icon={<CheckCircle2 size={16} />} hint={`с достижениями ФСП ${withFsp}`} />
      </div>

      <div className="grid-2-1">
        <Reveal className="card">
          <div className="card__title row between">
            <span>Категории кандидатов</span>
            <Link to="/app/candidates" className="small">банк кандидатов →</Link>
          </div>
          {categories.length ? (
            <>
              <CategoryHeatmap stats={categories} />
              <p className="muted tiny mt">Число — кандидаты с подтверждённой категорией, ★ — из них с достижениями ФСП. Нажмите на ячейку, чтобы открыть список.</p>
            </>
          ) : (
            <EmptyState glyph="[ ]" title="Кандидатов пока нет" text="Как только кандидаты подтвердят категории, здесь появится карта." />
          )}
        </Reveal>

        <Reveal className="card" delay={100}>
          <div className="card__title">Воронка приглашений</div>
          {invitations.length ? (
            <div className="stack">
              {(['sent', 'viewed', 'accepted', 'declined'] as const).map((s) => (
                <Bar key={s} label={STATUS_LABEL[s]} value={byStatus(s)} max={invitations.length} suffix={String(byStatus(s))} tone={s === 'declined' ? 'white' : s === 'accepted' ? 'blue' : 'blue'} />
              ))}
            </div>
          ) : (
            <EmptyState glyph="@" title="Приглашений ещё нет" text="Откройте подборку по потребности и пригласите кандидатов." />
          )}
        </Reveal>
      </div>

      <Reveal className="card">
        <div className="card__title row between">
          <span>Потребности</span>
          <Link to="/app/vacancies" className="small">все →</Link>
        </div>
        {vacancies.length === 0 ? (
          <EmptyState
            glyph="+"
            title="Создайте первую потребность"
            text="Укажите специализацию, грейды, стек и зарплатную вилку — и получите ранжированную подборку."
            action={<LinkButton to="/app/vacancies/new" icon={<Plus size={16} />}>Создать</LinkButton>}
          />
        ) : (
          <ul className="mini-list">
            {vacancies.slice(0, 5).map((v) => (
              <li key={v.id}>
                <Link to={`/app/vacancies/${v.id}/matches`} className="mini-list__item">
                  <div className="grow">
                    <strong>{v.title}</strong>
                    <span className="muted small">{v.is_published ? 'опубликована' : 'черновик'} · откликов {v.applications_count}</span>
                  </div>
                  <span className="salary-sm">{formatSalary(v.salary_from, v.salary_to)}</span>
                  <span className="btn btn--ghost btn--sm"><Search size={14} /> Подборка</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Reveal>
    </div>
  )
}
