import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Check, X, Eye, MessageSquare } from 'lucide-react'
import { api } from '../../api/client'
import type { Application, ApplicationStatus, Invitation, InvitationStatus } from '../../api/types'
import { useAsync, type AsyncState } from '../../hooks/useAsync'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Tabs from '../../components/ui/Tabs'
import { Button } from '../../components/ui/Button'
import { CategoryBadge, StatusChip } from '../../components/ui/Badges'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { STATUS_LABEL, errorMessage, formatDate, formatSalary } from '../../lib/format'

type TabKey = 'sent' | 'applications'

export default function EmployerInvitationsPage() {
  const [tab, setTab] = useState<TabKey>('sent')
  const invites = useAsync(() => api.getEmployerInvitations())
  const apps = useAsync(() => api.getEmployerApplications())

  return (
    <>
      <PageHeader title="Приглашения и отклики" subtitle="Статусы обновляются, когда кандидат открывает приглашение и отвечает на него." />
      <div className="toolbar">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { key: 'sent', label: 'Отправленные', count: invites.data?.length },
            { key: 'applications', label: 'Входящие отклики', count: apps.data?.filter((a) => a.status === 'sent').length },
          ]}
        />
      </div>
      {tab === 'sent' ? <SentList state={invites} /> : <ApplicationsList state={apps} />}
    </>
  )
}

function SentList({ state }: { state: AsyncState<Invitation[]> }) {
  const { data, error, loading, reload } = state
  const [status, setStatus] = useState<InvitationStatus | ''>('')
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (loading && !data) return <SkeletonList count={3} lines={2} />
  if (!data?.length) {
    return <EmptyState glyph="@" title="Вы ещё никого не пригласили" text="Откройте подборку по потребности или банк кандидатов и нажмите «Пригласить»." />
  }
  const shown = status ? data.filter((i) => i.status === status) : data
  return (
    <div className="stack">
      <div className="row wrap gap-xs">
        <button className={`chip-filter ${status === '' ? 'is-active' : ''}`} onClick={() => setStatus('')}>Все · {data.length}</button>
        {(['sent', 'viewed', 'accepted', 'declined'] as const).map((s) => (
          <button key={s} className={`chip-filter ${status === s ? 'is-active' : ''}`} onClick={() => setStatus(s)}>
            {STATUS_LABEL[s]} · {data.filter((i) => i.status === s).length}
          </button>
        ))}
      </div>
      <div className="card table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Кандидат</th>
              <th>Позиция</th>
              <th>Зарплата</th>
              <th>Статус</th>
              <th>Дата</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((i) => (
              <tr key={i.id}>
                <td>
                  <Link to={`/app/candidates/${i.candidate.id}`}><strong>{i.candidate.display_name}</strong></Link>
                  <div><CategoryBadge title={i.candidate.category_title} grade={i.candidate.grade} /></div>
                </td>
                <td>{i.title}</td>
                <td className="text-success nowrap">{formatSalary(i.salary_from, i.salary_to)}</td>
                <td><StatusChip status={i.status} /></td>
                <td className="small muted nowrap">{formatDate(i.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ApplicationsList({ state }: { state: AsyncState<Application[]> }) {
  const { data, error, loading, reload, setData } = state
  const toast = useToast()
  const [busy, setBusy] = useState<string | null>(null)

  const setStatus = async (a: Application, status: Exclude<ApplicationStatus, 'sent'>) => {
    setBusy(a.id + status)
    try {
      const res = await api.setApplicationStatus(a.id, status)
      setData((d) => d?.map((x) => (x.id === a.id ? (res?.id ? res : { ...x, status }) : x)) ?? d)
      if (status !== 'viewed') toast.success(status === 'accepted' ? 'Отклик принят' : 'Отклик отклонён')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  if (error) return <ErrorState message={error} onRetry={reload} />
  if (loading && !data) return <SkeletonList count={3} lines={3} />
  if (!data?.length) return <EmptyState glyph="→" title="Откликов пока нет" text="Опубликуйте потребность — кандидаты смогут откликнуться на неё." />

  return (
    <div className="stack">
      {data.map((a, i) => {
        const final = a.status === 'accepted' || a.status === 'declined'
        return (
          <Reveal key={a.id} delay={i * 40}>
            <article className={`card app-card ${a.status === 'sent' ? 'is-new' : ''}`}>
              <div className="row between wrap gap-sm">
                <div>
                  <Link to={`/app/candidates/${a.candidate.id}`} className="cand__name">{a.candidate.display_name}</Link>
                  <div className="muted small">на «{a.vacancy.title}» · {formatDate(a.created_at)}</div>
                </div>
                <div className="row gap-sm">
                  <CategoryBadge title={a.candidate.category_title} grade={a.candidate.grade} />
                  <StatusChip status={a.status} />
                </div>
              </div>
              {a.message && (
                <p className="app-card__msg"><MessageSquare size={14} /> {a.message}</p>
              )}
              <div className="row between wrap gap-sm">
                <span className="small muted">
                  {a.candidate.test_score !== null && `тест ${Math.round(a.candidate.test_score)} · `}
                  {a.candidate.stack.slice(0, 5).join(', ')}
                </span>
                {!final && (
                  <div className="row gap-sm">
                    {a.status === 'sent' && (
                      <Button variant="ghost" size="sm" icon={<Eye size={14} />} loading={busy === a.id + 'viewed'} onClick={() => setStatus(a, 'viewed')}>
                        Просмотрено
                      </Button>
                    )}
                    <Button variant="danger" size="sm" icon={<X size={14} />} loading={busy === a.id + 'declined'} onClick={() => setStatus(a, 'declined')}>Отклонить</Button>
                    <Button size="sm" icon={<Check size={14} />} loading={busy === a.id + 'accepted'} onClick={() => setStatus(a, 'accepted')}>Принять</Button>
                  </div>
                )}
              </div>
            </article>
          </Reveal>
        )
      })}
    </div>
  )
}
