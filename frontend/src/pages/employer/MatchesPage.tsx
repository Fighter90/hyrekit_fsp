import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Check, Filter, RotateCcw, Send, Sparkles, UserRound, Pencil } from 'lucide-react'
import { api } from '../../api/client'
import type { Grade, Invitation, MatchBreakdown, MatchItem, MatchQuery, MatchResult, Vacancy } from '../../api/types'
import { useCatalog } from '../../contexts/CatalogContext'
import PageHeader from '../../components/ui/PageHeader'
import Toggle from '../../components/ui/Toggle'
import Bar from '../../components/ui/Bar'
import { Button, LinkButton } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import CandidateCardView from '../../components/employer/CandidateCardView'
import InviteModal from '../../components/employer/InviteModal'
import VacancyAssessmentView from '../../components/employer/VacancyAssessmentView'
import Tabs from '../../components/ui/Tabs'
import { errorMessage, formatSalary, gradeLabel, GRADE_ORDER, plural } from '../../lib/format'
import { invitationPending } from '../../lib/candidate'

const BREAKDOWN_LABEL: Record<keyof MatchBreakdown, string> = {
  category: 'Категория',
  stack: 'Стек',
  test: 'Уровень по тесту',
  fsp: 'ФСП',
  freshness: 'Активность',
}

/** Компоненты оценки приходят в шкале 0..100; обрезаем на всякий случай. */
function toPct(b: MatchBreakdown): MatchBreakdown {
  const c = (v: number) => Math.max(0, Math.min(100, v))
  return { category: c(b.category), stack: c(b.stack), test: c(b.test), fsp: c(b.fsp), freshness: c(b.freshness) }
}

interface Filters {
  grade: Grade | ''
  stack: string[]
  has_fsp: boolean
  minScore: number
  hideInvited: boolean
}
const NO_FILTERS: Filters = { grade: '', stack: [], has_fsp: false, minScore: 0, hideInvited: false }
const isDefault = (f: Filters) => !f.grade && !f.stack.length && !f.has_fsp && !f.minScore && !f.hideInvited

export default function MatchesPage() {
  const { id = '' } = useParams()
  const [vacancy, setVacancy] = useState<Vacancy | null>(null)
  // исходная подборка хранится отдельно — сброс фильтров возвращает её без нового запроса
  const [original, setOriginal] = useState<MatchResult | null>(null)
  const [serverFiltered, setServerFiltered] = useState<MatchResult | null>(null)
  const [filters, setFilters] = useState<Filters>(NO_FILTERS)
  const [loading, setLoading] = useState(true)
  const [refining, setRefining] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [inviteFor, setInviteFor] = useState<MatchItem | null>(null)
  const [invited, setInvited] = useState<Record<string, Invitation['status']>>({})
  const [tab, setTab] = useState<'matches' | 'test'>('matches')
  // на узких экранах фильтры свёрнуты, чтобы список был виден сразу
  const [filtersOpen, setFiltersOpen] = useState(() => typeof window === 'undefined' || window.innerWidth > 1100)

  const load = async () => {
    setLoading(true)
    setError(null)
    try {
      const [v, m] = await Promise.all([api.getVacancy(id), api.getMatches(id, { limit: 50 })])
      setVacancy(v)
      setOriginal(m)
      setServerFiltered(null)
      setFilters(NO_FILTERS)
    } catch (e) {
      setError(errorMessage(e, 'Не удалось построить подборку'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  // Серверные фильтры (грейд, стек, ФСП) — запрос с параметрами; клиентские (порог, скрыть приглашённых) — поверх
  const serverKey = `${filters.grade}|${filters.stack.join(',')}|${filters.has_fsp}`
  useEffect(() => {
    if (!original) return
    if (!filters.grade && !filters.stack.length && !filters.has_fsp) {
      setServerFiltered(null)
      return
    }
    let alive = true
    setRefining(true)
    const q: MatchQuery = { grade: filters.grade, stack: filters.stack.join(','), has_fsp: filters.has_fsp, limit: 50 }
    api.getMatches(id, q)
      .then((m) => alive && setServerFiltered(m))
      .catch((e) => alive && setError(errorMessage(e)))
      .finally(() => alive && setRefining(false))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [serverKey, original])

  const base = serverFiltered ?? original
  const items = useMemo(() => {
    if (!base) return []
    return base.items.filter((it) => {
      if (it.score < filters.minScore) return false
      const st = invited[it.candidate.id] ?? it.candidate.invitation_status
      if (filters.hideInvited && st) return false
      return true
    })
  }, [base, filters.minScore, filters.hideInvited, invited])

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters((f) => ({ ...f, [k]: v }))
  const toggleStack = (s: string) => set('stack', filters.stack.includes(s) ? filters.stack.filter((x) => x !== s) : [...filters.stack, s])

  return (
    <>
      <Link to="/app/vacancies" className="back-link"><ArrowLeft size={14} /> Все потребности</Link>
      <PageHeader
        
        title={vacancy?.title ?? 'Подборка кандидатов'}
        subtitle={
          vacancy && (
            <>
              {gradeLabel(vacancy.grade_min)}–{gradeLabel(vacancy.grade_max)} · <span className="text-success">{formatSalary(vacancy.salary_from, vacancy.salary_to)}</span>
            </>
          )
        }
        actions={vacancy && <LinkButton to={`/app/vacancies/${vacancy.id}/edit`} variant="ghost" icon={<Pencil size={16} />}>Изменить</LinkButton>}
      />
      {error && <ErrorState message={error} onRetry={load} />}
      {loading && <SkeletonList count={3} lines={4} />}

      {!loading && vacancy && (
        <div className="toolbar">
          <Tabs
            value={tab}
            onChange={setTab}
            tabs={[
              { key: 'matches', label: 'Подборка кандидатов', count: original?.total },
              { key: 'test', label: 'Тест под вакансию' },
            ]}
          />
        </div>
      )}
      {!loading && vacancy && tab === 'test' && <VacancyAssessmentView vacancyId={vacancy.id} />}

      {!loading && original && vacancy && tab === 'matches' && (
        <div className="matches">
          <aside className="matches__filters card">
            <button type="button" className="card__title matches__filters-toggle" onClick={() => setFiltersOpen((v) => !v)} aria-expanded={filtersOpen}>
              <Filter size={16} /> Фильтры{!isDefault(filters) && <span className="tabs__count">вкл</span>}
            </button>
            {filtersOpen && (<>
            <div className="stack">
              <label className="field">
                <span className="field__label">Грейд</span>
                <select className="select" value={filters.grade} onChange={(e) => set('grade', e.target.value as Grade | '')}>
                  <option value="">Любой из диапазона</option>
                  {GRADE_ORDER.map((g) => <option key={g} value={g}>{gradeLabel(g)}</option>)}
                </select>
              </label>
              {vacancy.stack.length > 0 && (
                <div className="field">
                  <span className="field__label">Обязательный стек</span>
                  <div className="tags">
                    {vacancy.stack.map((s) => (
                      <button key={s} type="button" className={`tag tag-toggle ${filters.stack.includes(s) ? 'tag--hit' : ''}`} onClick={() => toggleStack(s)} aria-pressed={filters.stack.includes(s)}>
                        {filters.stack.includes(s) && <Check size={11} />} {s}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              <label className="field">
                <span className="field__label">Минимальный балл совпадения: <strong>{filters.minScore}</strong></span>
                <input type="range" className="range" min={0} max={90} step={5} value={filters.minScore} onChange={(e) => set('minScore', Number(e.target.value))} />
              </label>
              <Toggle checked={filters.has_fsp} onChange={(v) => set('has_fsp', v)} label="Только с достижениями ФСП" />
              <Toggle checked={filters.hideInvited} onChange={(v) => set('hideInvited', v)} label="Скрыть уже приглашённых" />
              {!isDefault(filters) && (
                <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={() => setFilters(NO_FILTERS)}>
                  Сбросить фильтры
                </Button>
              )}
            </div>
            {original.categories.length > 0 && (
              <div className="mt-lg">
                <div className="field__label">Категории в подборке</div>
                <ul className="cat-list">
                  {original.categories.map((c) => (
                    <li key={c.category}>
                      <span>{c.title}</span>
                      <span className="muted">{c.count}{c.with_fsp ? ` · ★${c.with_fsp}` : ''}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            </>)}
          </aside>

          <section className="matches__list">
            <div className="matches__summary">
              <Sparkles size={16} className="text-blue" />
              {isDefault(filters) ? (
                <span>Найдено <strong>{original.total}</strong> {plural(original.total, ['кандидат', 'кандидата', 'кандидатов'])}, показаны лучшие {original.items.length}</span>
              ) : (
                <span>
                  После фильтров: <strong>{items.length}</strong> из {original.items.length}
                  {refining && <span className="muted"> · обновляем…</span>}
                  <button className="link-btn" onClick={() => setFilters(NO_FILTERS)}>сбросить фильтры</button>
                </span>
              )}
            </div>
            {items.length === 0 ? (
              <EmptyState
                glyph="{ }"
                title={original.items.length ? 'Под фильтры никто не подошёл' : 'Подходящих кандидатов пока нет'}
                text={original.items.length ? 'Ослабьте фильтры — исходная подборка сохранена.' : 'Расширьте диапазон грейдов или стек. Новые кандидаты появляются после тестирования.'}
                action={!isDefault(filters) && <Button variant="secondary" icon={<RotateCcw size={14} />} onClick={() => setFilters(NO_FILTERS)}>Вернуть исходную подборку</Button>}
              />
            ) : (
              <div className={`stack ${refining ? 'is-refining' : ''}`} aria-busy={refining}>
                {items.map((it, i) => (
                  <Reveal key={it.candidate.id} delay={Math.min(i, 6) * 50}>
                    <MatchCard
                      item={it}
                      rank={i + 1}
                      vacancyStack={vacancy.stack}
                      vacancyId={vacancy.id}
                      invitedStatus={invited[it.candidate.id]}
                      onInvite={() => setInviteFor(it)}
                    />
                  </Reveal>
                ))}
              </div>
            )}
          </section>
        </div>
      )}

      {inviteFor && vacancy && (
        <InviteModal
          candidate={inviteFor.candidate}
          vacancy={vacancy}
          onClose={() => setInviteFor(null)}
          onSent={(inv) => setInvited((m) => ({ ...m, [inviteFor.candidate.id]: inv.status }))}
        />
      )}
    </>
  )
}

function MatchCard({ item, rank, vacancyStack, vacancyId, invitedStatus, onInvite }: { item: MatchItem; rank: number; vacancyStack: string[]; vacancyId: string; invitedStatus?: Invitation['status']; onInvite: () => void }) {
  const { specTitle } = useCatalog()
  const pct = toPct(item.breakdown)
  const status = invitedStatus ?? item.candidate.invitation_status
  const c = status ? { ...item.candidate, invitation_status: status } : item.candidate
  return (
    <CandidateCardView
      c={c}
      rank={rank}
      vacancyId={vacancyId}
      highlight={vacancyStack}
      missing={item.missing_stack}
      aside={
        <div className="match-score" title="Итоговый балл совпадения">
          <span className="match-score__value display">{Math.round(item.score)}</span>
          <span className="match-score__label">совпадение</span>
        </div>
      }
      actions={
        <>
          <LinkButton to={`/app/candidates/${item.candidate.id}`} variant="ghost" size="sm" icon={<UserRound size={14} />}>Профиль</LinkButton>
          <Button size="sm" icon={<Send size={14} />} onClick={onInvite} disabled={invitationPending(status)}>
            {invitationPending(status) ? 'Приглашён' : 'Пригласить'}
          </Button>
        </>
      }
    >
      <div className="match-explain">
        <div className="match-explain__bars">
          {(Object.keys(BREAKDOWN_LABEL) as (keyof MatchBreakdown)[]).map((k) => (
            <Bar key={k} label={BREAKDOWN_LABEL[k]} value={pct[k]} tone={k === 'fsp' ? 'red' : 'blue'} />
          ))}
        </div>
        <ul className="reasons" aria-label="Почему рекомендован">
          {item.reasons.map((r) => (
            <li key={r}><Check size={14} /> {r}</li>
          ))}
          {item.missing_stack.length > 0 && (
            <li className="reasons__miss">Нет в стеке: {item.missing_stack.join(', ')}</li>
          )}
          {item.reasons.length === 0 && <li className="muted">{specTitle(item.candidate.specialization)}</li>}
        </ul>
      </div>
    </CandidateCardView>
  )
}
