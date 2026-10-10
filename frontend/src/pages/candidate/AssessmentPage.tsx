import { useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { Lock, Play, PencilLine, History, Timer, ListChecks, Shuffle, RotateCw } from 'lucide-react'
import { api } from '../../api/client'
import type { AnswerValue, AttemptResult, AttemptView, CandidateProfile, Eligibility, Grade, SurveyInput } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { ErrorState, EmptyState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { CategoryBadge, GradePill, Tags } from '../../components/ui/Badges'
import Reveal from '../../components/ui/Reveal'
import SurveyForm from '../../components/assessment/SurveyForm'
import TestRunner from '../../components/assessment/TestRunner'
import ResultView from '../../components/assessment/ResultView'
import { errorMessage, experienceLabel, formatDate, formatDateTime, gradeLabel } from '../../lib/format'
import { msLeft } from '../../lib/assessment'

const SNAPSHOT_KEY = 'hk_active_attempt'

// Снимок активной попытки в localStorage — чтобы продолжить тест после перезагрузки
function loadSnapshot(): AttemptView | null {
  try {
    const raw = localStorage.getItem(SNAPSHOT_KEY)
    return raw ? (JSON.parse(raw) as AttemptView) : null
  } catch {
    return null
  }
}
function saveSnapshot(a: AttemptView | null) {
  try {
    if (a) localStorage.setItem(SNAPSHOT_KEY, JSON.stringify(a))
    else localStorage.removeItem(SNAPSHOT_KEY)
  } catch {
    /* storage недоступен — не критично */
  }
}

interface PageData {
  profile: CandidateProfile
  eligibility: Eligibility
  history: AttemptResult[]
}

type View = { kind: 'overview' } | { kind: 'survey' } | { kind: 'running'; attempt: AttemptView } | { kind: 'result'; result: AttemptResult }

export default function AssessmentPage() {
  const { specTitle } = useCatalog()
  const toast = useToast()
  const { data, error, loading, reload, setData } = useAsync<PageData>(async () => {
    const profile = await api.getCandidateProfile()
    const [eligibility, history] = await Promise.all([
      api.getEligibility(),
      api.getAssessmentHistory().catch(() => [] as AttemptResult[]),
    ])
    return { profile, eligibility, history }
  })
  const [view, setView] = useState<View>({ kind: 'overview' })
  const [starting, setStarting] = useState<Grade | null>(null)
  const [snapshot, setSnapshot] = useState<AttemptView | null>(() => loadSnapshot())
  const location = useLocation()
  const navigate = useNavigate()
  const autostarted = useRef(false)

  const start = async (grade: Grade) => {
    setStarting(grade)
    try {
      const attempt = await api.startAttempt(grade)
      saveSnapshot(attempt)
      setSnapshot(attempt)
      setView({ kind: 'running', attempt })
      window.scrollTo({ top: 0 })
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось начать тест'))
      void reload()
    } finally {
      setStarting(null)
    }
  }

  // Экспресс-тест жюри: после гостевого входа тест стартует сразу (FSP-32)
  const autostart = (location.state as { autostart?: Grade } | null)?.autostart
  useEffect(() => {
    if (!autostart || !data || autostarted.current) return
    autostarted.current = true
    navigate(location.pathname, { replace: true, state: null })
    if (data.profile.is_guest) void start(autostart)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autostart, data])

  const onFinished = (result: AttemptResult) => {
    saveSnapshot(null)
    setSnapshot(null)
    setView({ kind: 'result', result })
    window.scrollTo({ top: 0 })
    void reload()
  }

  const finishSnapshot = async (a: AttemptView) => {
    try {
      onFinished(await api.finishAttempt(a.id))
    } catch (e) {
      toast.error(errorMessage(e, 'Попытка уже закрыта'))
      saveSnapshot(null)
      setSnapshot(null)
    }
  }

  const submitSurvey = async (input: SurveyInput) => {
    const profile = await api.submitSurvey(input)
    const eligibility = await api.getEligibility()
    setData((d) => (d ? { ...d, profile, eligibility } : d))
    toast.success('Опрос сохранён')
    setView({ kind: 'overview' })
  }

  if (view.kind === 'running') {
    return (
      <TestRunner
        attempt={view.attempt}
        specTitle={specTitle(view.attempt.specialization)}
        onFinished={onFinished}
        onAnswersChange={(answers: Record<string, AnswerValue>) => saveSnapshot({ ...view.attempt, answers })}
      />
    )
  }

  return (
    <>
      <PageHeader title="Тестирование" subtitle="Опрос и тест подтверждают грейд и присваивают категорию." />
      {data?.profile.is_guest && <ExpressNote />}
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonCard lines={6} />}
      {data && view.kind === 'result' && (
        <ResultView
          result={view.result}
          specTitle={specTitle(view.result.specialization)}
          allowedGrades={data.eligibility.allowed_grades}
          onStart={start}
          starting={starting !== null}
          onBack={() => setView({ kind: 'overview' })}
        />
      )}
      {data && view.kind !== 'result' && (
        <>
          {snapshot && (
            <ResumeBanner
              attempt={snapshot}
              onResume={() => setView({ kind: 'running', attempt: snapshot })}
              onFinish={() => finishSnapshot(snapshot)}
            />
          )}
          {view.kind === 'survey' || !data.profile.specialization || !data.profile.declared_grade ? (
            <SurveyForm
              profile={data.profile}
              onSubmit={submitSurvey}
              onCancel={data.profile.specialization ? () => setView({ kind: 'overview' }) : undefined}
            />
          ) : (
            <Overview data={data} onEditSurvey={() => setView({ kind: 'survey' })} onStart={start} starting={starting} />
          )}
        </>
      )}
    </>
  )
}

function ExpressNote() {
  return (
    <div className="alert alert--info">
      <Timer size={18} />
      <div className="grow small">
        <strong>Демо-режим: экспресс-тест для жюри.</strong> 5 заданий за 5 минут вместо 10 за 20, тот же банк и та же
        оценка. Грейд можно пересдавать без ожидания 90 дней. После теста войдите демо-работодателем
        (employer@hyrekit.ru · HyreKit2026) — гостевой кандидат будет в подборке и поиске.
      </div>
    </div>
  )
}

function ResumeBanner({ attempt, onResume, onFinish }: { attempt: AttemptView; onResume: () => void; onFinish: () => void }) {
  const expired = msLeft(attempt.deadline_at) <= 0
  return (
    <div className="alert alert--info resume-banner">
      <Timer size={18} />
      <div className="grow">
        <strong>Незавершённый тест · {gradeLabel(attempt.grade)}</strong>
        <div className="small muted">
          {expired ? 'Время вышло — отправьте ответы, чтобы получить результат.' : `Можно продолжить до ${formatDateTime(attempt.deadline_at)}.`}
        </div>
      </div>
      {expired ? <Button size="sm" onClick={onFinish}>Получить результат</Button> : <Button size="sm" icon={<Play size={14} />} onClick={onResume}>Продолжить</Button>}
    </div>
  )
}

function Overview({ data, onEditSurvey, onStart, starting }: { data: PageData; onEditSurvey: () => void; onStart: (g: Grade) => void; starting: Grade | null }) {
  const { specTitle, industryTitle, catalog } = useCatalog()
  const { profile: p, eligibility: el, history } = data
  const locked = el.allowed_grades.length === 0
  const topics = catalog?.specializations.find((s) => s.code === p.specialization)?.topics ?? []

  return (
    <div className="stack-lg">
      <div className="grid-2">
        <Reveal className="card">
          <div className="card__title row between">
            <span>Опрос</span>
            <Button variant="ghost" size="sm" icon={<PencilLine size={14} />} onClick={onEditSurvey}>Изменить</Button>
          </div>
          <dl className="kv">
            <dt>Специализация</dt><dd>{specTitle(p.specialization)}</dd>
            <dt>Отрасль</dt><dd>{industryTitle(p.industry)}</dd>
            <dt>Опыт</dt><dd>{experienceLabel(p.experience_years)}</dd>
            <dt>Заявленный грейд</dt><dd><GradePill grade={p.declared_grade} /></dd>
            <dt>Подтверждённый</dt><dd>{p.grade ? <CategoryBadge title={p.category_title} grade={p.grade} /> : <span className="muted">ещё нет</span>}</dd>
          </dl>
          {p.stack.length > 0 && <div className="mt"><Tags items={p.stack} limit={12} /></div>}
        </Reveal>

        <Reveal className={`card ${locked ? '' : 'card--spin'}`} delay={80}>
          <div className="card__title">{locked ? <Lock size={18} /> : <Play size={18} />} Тест</div>
          {locked ? (
            <div className="lock">
              <div className="lock__icon"><Lock size={28} /></div>
              <p><strong>Сдача временно недоступна</strong></p>
              {el.reason && <p className="muted small">{el.reason}</p>}
              {el.locked_until && (
                <p className="lock__date">
                  Откроется <strong>{formatDate(el.locked_until)}</strong>
                </p>
              )}
            </div>
          ) : (
            <>
              <ul className="test-facts">
                <li><ListChecks size={16} /> Задания по темам: {topics.length ? topics.join(', ') : specTitle(p.specialization)}</li>
                <li><Shuffle size={16} /> Уникальный вариант для каждой попытки</li>
                <li><Timer size={16} /> Ограничение по времени, ответы сохраняются сразу</li>
              </ul>
              {el.reason && <p className="muted small">{el.reason}</p>}
              <div className="grade-start">
                {el.allowed_grades.map((g) => (
                  <Button
                    key={g}
                    variant={g === el.declared_grade ? 'primary' : 'secondary'}
                    icon={<Play size={14} />}
                    loading={starting === g}
                    disabled={starting !== null}
                    onClick={() => onStart(g)}
                  >
                    Сдавать {gradeLabel(g)}
                  </Button>
                ))}
              </div>
            </>
          )}
        </Reveal>
      </div>

      <Reveal className="card">
        <div className="card__title"><History size={18} /> История попыток</div>
        {history.length === 0 ? (
          <EmptyState glyph="▲" title="Попыток пока нет" text="После первого теста здесь появятся результаты и разбор." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Дата</th>
                  <th>Тест</th>
                  <th>Баллы</th>
                  <th>Верно</th>
                  <th>Итог</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td className="small">{formatDateTime(h.finished_at)}</td>
                    <td>{specTitle(h.specialization)} · <GradePill grade={h.grade_tested} /></td>
                    <td className="mono-num"><strong>{Math.round(h.score)}</strong></td>
                    <td className="mono-num muted">{h.correct}/{h.total}</td>
                    <td>
                      {h.assigned_grade ? (
                        <span className="text-success small">✓ {gradeLabel(h.assigned_grade)}</span>
                      ) : (
                        <span className="muted small"><RotateCw size={12} style={{ display: 'inline' }} /> не подтверждён</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Reveal>
    </div>
  )
}
