import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { Search, ChevronLeft, ChevronRight, Send, UserRound, RotateCcw } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateCard, CandidateQuery, Grade, Vacancy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import PageHeader from '../../components/ui/PageHeader'
import Toggle from '../../components/ui/Toggle'
import { Button, LinkButton } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import CandidateCardView from '../../components/employer/CandidateCardView'
import InviteModal from '../../components/employer/InviteModal'
import { GRADE_ORDER, gradeLabel, plural } from '../../lib/format'

const PAGE = 12

export default function CandidatesPage() {
  const { catalog } = useCatalog()
  const [params, setParams] = useSearchParams()
  const spec = params.get('specialization') ?? ''
  const grade = (params.get('grade') ?? '') as Grade | ''
  const category = params.get('category') ?? ''
  const stack = params.get('stack') ?? ''
  const hasFsp = params.get('has_fsp') === 'true'
  const q = params.get('q') ?? ''
  const page = Math.max(0, Number(params.get('page') ?? 0) || 0)

  const [qDraft, setQDraft] = useState(q)
  const [stackDraft, setStackDraft] = useState(stack)
  const [inviteFor, setInviteFor] = useState<CandidateCard | null>(null)
  const [vacancies, setVacancies] = useState<Vacancy[]>([])

  useEffect(() => {
    api.getEmployerVacancies().then(setVacancies).catch(() => undefined)
  }, [])

  // фильтры живут в URL — ссылкой можно поделиться, «назад» работает
  const update = (patch: Record<string, string | boolean | number | null>) => {
    const p = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v === null || v === '' || v === false || (k === 'page' && v === 0)) p.delete(k)
      else p.set(k, String(v))
    }
    if (!('page' in patch)) p.delete('page')
    setParams(p, { replace: true })
  }

  // отложенное применение текстовых полей
  useEffect(() => {
    const t = setTimeout(() => {
      if (qDraft !== q || stackDraft !== stack) update({ q: qDraft.trim(), stack: stackDraft.trim() })
    }, 400)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qDraft, stackDraft])

  const query: CandidateQuery = { specialization: spec, grade, category, stack, has_fsp: hasFsp, q, limit: PAGE, offset: page * PAGE }
  const { data, error, loading, reload, setData } = useAsync(() => api.searchCandidates(query), [spec, grade, category, stack, hasFsp, q, page])

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1
  const anyFilter = spec || grade || category || stack || hasFsp || q

  return (
    <>
      <PageHeader title="Банк кандидатов" subtitle="Только кандидаты с подтверждённой категорией и согласием на показ профиля." />
      <div className="filters card card--flat filters--wrap">
        <div className="input-icon grow">
          <Search size={16} aria-hidden />
          <input className="input" placeholder="Поиск: роль, технология, город" value={qDraft} onChange={(e) => setQDraft(e.target.value)} aria-label="Поиск" />
        </div>
        <select className="select" value={spec} onChange={(e) => update({ specialization: e.target.value, category: null })} aria-label="Специализация">
          <option value="">Все специализации</option>
          {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
        </select>
        <select className="select" value={grade} onChange={(e) => update({ grade: e.target.value, category: null })} aria-label="Грейд">
          <option value="">Любой грейд</option>
          {GRADE_ORDER.map((g) => <option key={g} value={g}>{gradeLabel(g)}</option>)}
        </select>
        <input className="input filters__stack" placeholder="Стек через запятую" value={stackDraft} onChange={(e) => setStackDraft(e.target.value)} aria-label="Стек" />
        <Toggle checked={hasFsp} onChange={(v) => update({ has_fsp: v })} label="С ФСП" />
        {anyFilter && (
          <Button variant="ghost" size="sm" icon={<RotateCcw size={14} />} onClick={() => { setQDraft(''); setStackDraft(''); setParams({}, { replace: true }) }}>
            Сбросить
          </Button>
        )}
      </div>
      {category && <p className="muted small">Категория: <strong>{category}</strong> <button className="link-btn" onClick={() => update({ category: null })}>убрать</button></p>}

      {error && <ErrorState message={error} onRetry={reload} />}
      {data && !loading && (
        <p className="muted small results-count">
          {data.total} {plural(data.total, ['кандидат', 'кандидата', 'кандидатов'])}
        </p>
      )}
      {loading ? (
        <div className="cand-grid">{Array.from({ length: 6 }, (_, i) => <SkeletonCard key={i} lines={4} />)}</div>
      ) : data && data.items.length === 0 ? (
        <EmptyState glyph="[ ]" title="Никого не нашли" text="Ослабьте фильтры или выберите другую категорию." />
      ) : (
        <div className="cand-grid">
          {data?.items.map((c) => (
            <CandidateCardView
              key={c.id}
              c={c}
              highlight={stack ? stack.split(',').map((s) => s.trim()) : []}
              actions={
                <>
                  <LinkButton to={`/app/candidates/${c.id}`} variant="ghost" size="sm" icon={<UserRound size={14} />}>Профиль</LinkButton>
                  <Button size="sm" icon={<Send size={14} />} onClick={() => setInviteFor(c)} disabled={!!c.invitation_status && c.invitation_status !== 'declined'}>
                    {c.invitation_status && c.invitation_status !== 'declined' ? 'Приглашён' : 'Пригласить'}
                  </Button>
                </>
              }
            />
          ))}
        </div>
      )}

      {data && pages > 1 && (
        <nav className="pager" aria-label="Страницы">
          <Button variant="ghost" size="sm" icon={<ChevronLeft size={14} />} disabled={page === 0} onClick={() => update({ page: page - 1 })}>Назад</Button>
          <span className="mono-num small">{page + 1} / {pages}</span>
          <Button variant="ghost" size="sm" iconRight={<ChevronRight size={14} />} disabled={page + 1 >= pages} onClick={() => update({ page: page + 1 })}>Вперёд</Button>
        </nav>
      )}

      {inviteFor && (
        <InviteModal
          candidate={inviteFor}
          vacancies={vacancies}
          onClose={() => setInviteFor(null)}
          onSent={(inv) => setData((d) => (d ? { ...d, items: d.items.map((x) => (x.id === inviteFor.id ? { ...x, invitation_status: inv.status } : x)) } : d))}
        />
      )}
    </>
  )
}
