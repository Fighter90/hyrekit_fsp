import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Send, UserRound } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateCard, Vacancy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import PageHeader from '../../components/ui/PageHeader'
import { Button, LinkButton } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import CandidateCardView from '../../components/employer/CandidateCardView'
import InviteModal from '../../components/employer/InviteModal'
import { formatDateTime, plural } from '../../lib/format'

/** Шортлист компании: отмеченные кандидаты, при желании по конкретной потребности. */
export default function FavoritesPage() {
  const [params, setParams] = useSearchParams()
  const vacancyId = params.get('vacancy') ?? ''
  const [vacancies, setVacancies] = useState<Vacancy[]>([])
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null)

  useEffect(() => {
    api.getEmployerVacancies().then(setVacancies).catch(() => undefined)
  }, [])

  const { data, error, loading, reload, setData } = useAsync(() => api.getFavorites(vacancyId || undefined), [vacancyId])
  const title = (id: string | null) => vacancies.find((v) => v.id === id)?.title

  return (
    <>
      <PageHeader title="Избранное" subtitle="Кандидаты, которых вы отметили в подборке или банке. Контакты по-прежнему открываются только после приглашения." />
      <div className="filters card card--flat">
        <select
          className="select"
          value={vacancyId}
          onChange={(e) => setParams(e.target.value ? { vacancy: e.target.value } : {}, { replace: true })}
          aria-label="Потребность"
        >
          <option value="">Все потребности</option>
          {vacancies.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
        </select>
      </div>

      {error && <ErrorState message={error} onRetry={reload} />}
      {data && !loading && (
        <p className="muted small results-count">{data.length} {plural(data.length, ['кандидат', 'кандидата', 'кандидатов'])}</p>
      )}
      {loading ? (
        <div className="cand-grid">{Array.from({ length: 3 }, (_, i) => <SkeletonCard key={i} lines={4} />)}</div>
      ) : data && data.length === 0 ? (
        <EmptyState glyph="[ ]" title="В избранном пока никого" text="Отмечайте кандидатов значком закладки в подборке или банке кандидатов." />
      ) : (
        <div className="cand-grid">
          {data?.map((f) => (
            <CandidateCardView
              key={f.candidate.id}
              c={f.candidate}
              vacancyId={f.vacancy_id ?? undefined}
              onFavoriteChange={(on) => !on && setData((d) => d?.filter((x) => x.candidate.id !== f.candidate.id) ?? d)}
              actions={
                <>
                  <LinkButton to={`/app/candidates/${f.candidate.id}`} variant="ghost" size="sm" icon={<UserRound size={14} />}>Профиль</LinkButton>
                  <Button size="sm" icon={<Send size={14} />} onClick={() => setInviteFor(f.candidate)} disabled={!!f.candidate.invitation_status && f.candidate.invitation_status !== 'declined'}>
                    {f.candidate.invitation_status && f.candidate.invitation_status !== 'declined' ? 'Приглашён' : 'Пригласить'}
                  </Button>
                </>
              }
            >
              <p className="muted small">
                {title(f.vacancy_id) ? `Под потребность «${title(f.vacancy_id)}» · ` : ''}добавлен {formatDateTime(f.added_at)}
              </p>
            </CandidateCardView>
          ))}
        </div>
      )}

      {inviteFor && (
        <InviteModal
          candidate={inviteFor}
          vacancies={vacancies}
          onClose={() => setInviteFor(null)}
          onSent={(inv) => setData((d) => d?.map((x) => (x.candidate.id === inviteFor.id ? { ...x, candidate: { ...x.candidate, invitation_status: inv.status } } : x)) ?? d)}
        />
      )}
    </>
  )
}
