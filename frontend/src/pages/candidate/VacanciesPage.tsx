import { useEffect, useMemo, useState } from 'react'
import { Search, Send, MapPin, Briefcase, Users } from 'lucide-react'
import { api } from '../../api/client'
import type { Application, CandidateProfile, Grade, Vacancy } from '../../api/types'
import { useAsync, type AsyncState } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Tabs from '../../components/ui/Tabs'
import Modal from '../../components/ui/Modal'
import Field from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { GradePill, StatusChip, Tags } from '../../components/ui/Badges'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { GRADE_ORDER, errorMessage, formatDate, formatSalary, gradeLabel, workFormatLabel } from '../../lib/format'

type TabKey = 'vacancies' | 'applications'

export default function CandidateVacanciesPage() {
  const [tab, setTab] = useState<TabKey>('vacancies')
  const apps = useAsync(() => api.getCandidateApplications())
  const profile = useAsync<CandidateProfile | null>(() => api.getCandidateProfile().catch(() => null))

  return (
    <>
      <PageHeader title="Вакансии" subtitle="Не хотите ждать приглашений — откликнитесь сами. Работодатель увидит вашу категорию и результаты." />
      <div className="toolbar">
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { key: 'vacancies', label: 'Вакансии' },
            { key: 'applications', label: 'Мои отклики', count: apps.data?.length },
          ]}
        />
      </div>
      {tab === 'vacancies' ? (
        <VacancyList
          profile={profile.data ?? null}
          applications={apps.data ?? []}
          onApplied={(a) => apps.setData((d) => [a, ...(d ?? [])])}
        />
      ) : (
        <ApplicationsList state={apps} />
      )}
    </>
  )
}

function VacancyList({ profile, applications, onApplied }: { profile: CandidateProfile | null; applications: Application[]; onApplied: (a: Application) => void }) {
  const { catalog, specTitle } = useCatalog()
  const [spec, setSpec] = useState('')
  const [grade, setGrade] = useState<Grade | ''>('')
  const [q, setQ] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [applyTo, setApplyTo] = useState<Vacancy | null>(null)
  const [initDone, setInitDone] = useState(false)

  // по умолчанию фильтруем по специализации кандидата
  useEffect(() => {
    if (!initDone && profile) {
      if (profile.specialization) setSpec(profile.specialization)
      setInitDone(true)
    }
  }, [profile, initDone])

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(q.trim()), 350)
    return () => clearTimeout(t)
  }, [q])

  const { data, error, loading, reload } = useAsync(() => api.getPublishedVacancies({ specialization: spec, grade, q: debouncedQ }), [spec, grade, debouncedQ])
  const applied = useMemo(() => new Set(applications.map((a) => a.vacancy?.id)), [applications])

  return (
    <>
      <div className="filters card card--flat">
        <div className="input-icon grow">
          <Search size={16} aria-hidden />
          <input className="input" placeholder="Поиск по названию, стеку, компании" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Поиск" />
        </div>
        <select className="select" value={spec} onChange={(e) => setSpec(e.target.value)} aria-label="Специализация">
          <option value="">Все специализации</option>
          {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
        </select>
        <select className="select" value={grade} onChange={(e) => setGrade(e.target.value as Grade | '')} aria-label="Грейд">
          <option value="">Любой грейд</option>
          {GRADE_ORDER.map((g) => <option key={g} value={g}>{gradeLabel(g)}</option>)}
        </select>
      </div>

      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && <SkeletonList count={3} />}
      {!loading && data && data.length === 0 && (
        <EmptyState glyph="//" title="Вакансий не найдено" text="Измените фильтры или загляните позже — работодатели публикуют новые потребности." />
      )}
      {!loading && data && (
        <div className="vacancy-grid">
          {data.map((v, i) => (
            <Reveal key={v.id} delay={(i % 6) * 50}>
              <article className="vacancy card card--glow card--hover">
                <div className="row between gap-sm">
                  <span className="muted small"><Briefcase size={13} style={{ display: 'inline' }} /> {v.company.name}</span>
                  <span className="grade-range">
                    <GradePill grade={v.grade_min} />
                    {v.grade_max !== v.grade_min && <>–<GradePill grade={v.grade_max} /></>}
                  </span>
                </div>
                <h3 className="vacancy__title">{v.title}</h3>
                <div className="vacancy__salary">{formatSalary(v.salary_from, v.salary_to)}</div>
                <div className="vacancy__meta small muted">
                  <span>{specTitle(v.specialization)}</span>
                  <span>{workFormatLabel(v.work_format)}</span>
                  {v.city && <span><MapPin size={12} style={{ display: 'inline' }} /> {v.city}</span>}
                </div>
                <p className="muted small clamp-3">{v.description}</p>
                <Tags items={v.stack} highlight={profile?.stack ?? []} limit={8} />
                <div className="vacancy__foot">
                  <span className="tiny muted"><Users size={12} style={{ display: 'inline' }} /> {v.applications_count} откликов</span>
                  {applied.has(v.id) ? (
                    <span className="status status--accepted">Вы откликнулись</span>
                  ) : (
                    <Button size="sm" icon={<Send size={14} />} onClick={() => setApplyTo(v)}>Откликнуться</Button>
                  )}
                </div>
              </article>
            </Reveal>
          ))}
        </div>
      )}

      {applyTo && <ApplyModal vacancy={applyTo} onClose={() => setApplyTo(null)} onApplied={onApplied} />}
    </>
  )
}

function ApplyModal({ vacancy, onClose, onApplied }: { vacancy: Vacancy; onClose: () => void; onApplied: (a: Application) => void }) {
  const toast = useToast()
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)
  const submit = async () => {
    setBusy(true)
    try {
      const a = await api.applyToVacancy(vacancy.id, message.trim() || undefined)
      onApplied(a)
      toast.success('Отклик отправлен')
      onClose()
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось откликнуться'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <Modal
      open
      title={`Отклик: ${vacancy.title}`}
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button icon={<Send size={16} />} loading={busy} onClick={submit}>Отправить отклик</Button>
        </>
      }
    >
      <div className="stack">
        <div className="row between wrap gap-sm">
          <span className="muted">{vacancy.company.name}</span>
          <strong className="text-success">{formatSalary(vacancy.salary_from, vacancy.salary_to)}</strong>
        </div>
        <Field label="Сопроводительное сообщение" htmlFor="apply-msg" hint="Необязательно. Коротко: почему вам интересна эта позиция.">
          <textarea id="apply-msg" className="textarea" value={message} onChange={(e) => setMessage(e.target.value)} maxLength={2000} />
        </Field>
        <p className="muted small">Работодатель увидит вашу карточку: категорию, стек и результаты теста. Контакты — только после принятия.</p>
      </div>
    </Modal>
  )
}

function ApplicationsList({ state }: { state: AsyncState<Application[]> }) {
  const { data, error, loading, reload } = state
  if (error) return <ErrorState message={error} onRetry={reload} />
  if (loading && !data) return <SkeletonList count={2} lines={2} />
  if (!data?.length) return <EmptyState glyph="→" title="Откликов пока нет" text="Откликайтесь на вакансии — статусы появятся здесь." />
  return (
    <div className="stack">
      {data.map((a) => (
        <div key={a.id} className="card row between wrap gap app-row">
          <div className="grow">
            <strong>{a.vacancy.title}</strong>
            <div className="muted small">{a.vacancy.company.name} · {formatDate(a.created_at)}</div>
          </div>
          <span className="salary-sm">{formatSalary(a.vacancy.salary_from, a.vacancy.salary_to)}</span>
          <StatusChip status={a.status} />
        </div>
      ))}
    </div>
  )
}
