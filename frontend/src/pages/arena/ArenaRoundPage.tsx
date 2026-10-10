import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ArrowLeft, Play, Send, Flag, CheckCircle2, XCircle, Sparkles, BookOpen, Timer } from 'lucide-react'
import { api } from '../../api/client'
import type {
  ArenaBoard,
  ArenaBoardRow,
  ArenaEditorialItem,
  ArenaLanguage,
  ArenaRoundDetail,
  ArenaRunResult,
  ArenaSubmission,
  ArenaTask,
  CandidateCard,
} from '../../api/types'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { useAsync } from '../../hooks/useAsync'
import PageHeader from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import Modal from '../../components/ui/Modal'
import Tabs from '../../components/ui/Tabs'
import { ErrorState, Spinner } from '../../components/ui/States'
import CodeEditor from '../../components/arena/CodeEditor'
import { Leaderboard, VerdictChip } from '../../components/arena/parts'
import { VERDICT_LABEL, formatClock } from '../../lib/arena'
import InviteModal from '../../components/employer/InviteModal'
import { errorMessage, formatDateTime } from '../../lib/format'

const TEMPLATES: Record<ArenaLanguage, string> = {
  python: 'import sys\n\ndata = sys.stdin.read().split()\n# ваше решение\n\nprint()\n',
  javascript: "const data = require('fs').readFileSync(0, 'utf8').trim().split(/\\s+/)\n// ваше решение\n\nconsole.log()\n",
}
const LANG_TITLE: Record<ArenaLanguage, string> = { python: 'Python 3', javascript: 'JavaScript' }

/** Условие с разметкой **жирный** и `код` без HTML-вставок. */
function Statement({ text }: { text: string }) {
  return (
    <div className="arena-statement">
      {text.split('\n\n').map((para, i) => (
        <p key={i}>
          {para.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).map((part, j) => {
            if (part.startsWith('**')) return <strong key={j}>{part.slice(2, -2)}</strong>
            if (part.startsWith('`')) return <code key={j}>{part.slice(1, -1)}</code>
            return <span key={j}>{part}</span>
          })}
        </p>
      ))}
    </div>
  )
}

function draftKey(roundId: string, problem: string, lang: ArenaLanguage) {
  return `arena:${roundId}:${problem}:${lang}`
}

function loadDraft(key: string, fallback: string): string {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function saveDraft(key: string, code: string) {
  try {
    localStorage.setItem(key, code)
  } catch {
    /* приватный режим: черновик живёт только в памяти */
  }
}

export default function ArenaRoundPage() {
  const { roundId = '' } = useParams()
  const { user } = useAuth()
  const isEmployer = user?.role === 'employer'
  const round = useAsync(() => api.getArenaRound(roundId), [roundId])
  const [board, setBoard] = useState<ArenaBoard | null>(null)
  const [editorial, setEditorial] = useState<ArenaEditorialItem[] | null>(null)
  const [offset, setOffset] = useState(0)
  const [now, setNow] = useState(Date.now())

  const loadBoard = useCallback(() => {
    api.getArenaBoard(roundId).then(setBoard).catch(() => undefined)
  }, [roundId])

  useEffect(() => {
    loadBoard()
    return api.watchArenaBoard(roundId, () => loadBoard())
  }, [roundId, loadBoard])

  useEffect(() => {
    if (round.data) setOffset(new Date(round.data.server_time + 'Z').getTime() - Date.now())
  }, [round.data])

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(t)
  }, [])

  const r = round.data
  const part = r?.participation ?? null
  const endsAt = part ? new Date(part.ends_at + 'Z').getTime() : null
  const left = endsAt ? Math.max(0, (endsAt - (now + offset)) / 1000) : 0
  const active = !!part && part.active && left > 0
  const over = !!part && !active
  const canEditorial = isEmployer ? r?.mine || r?.state === 'finished' : over || r?.state === 'finished'

  useEffect(() => {
    if (canEditorial && !editorial) api.getArenaEditorial(roundId).then((d) => setEditorial(d.problems)).catch(() => undefined)
  }, [canEditorial, editorial, roundId])

  // время вышло на глазах у участника — подтягиваем итог и рейтинг
  const reloadedAtEnd = useRef(false)
  useEffect(() => {
    if (part?.active && left === 0 && !reloadedAtEnd.current) {
      reloadedAtEnd.current = true
      void round.reload()
    }
  }, [left, part?.active, round])

  if (round.error) return <ErrorState message={round.error} onRetry={round.reload} />
  if (!r) return <Spinner />

  return (
    <>
      <Link to="/app/arena" className="back-link small muted">
        <ArrowLeft size={14} /> Все раунды
      </Link>
      <PageHeader
        title={r.title}
        subtitle={
          <>
            {r.sponsor && <>Раунд компании {r.sponsor} · </>}
            {r.is_open ? `${r.duration_minutes} минут с момента входа` : `${formatDateTime(r.starts_at)} – ${formatDateTime(r.ends_at)}`}
            {r.prize && <> · Приз: {r.prize}</>}
          </>
        }
        actions={
          active ? (
            <div className="row gap-sm">
              <span className={`arena-timer ${left < 300 ? 'is-low' : ''}`} aria-live="polite">
                <Timer size={16} /> {formatClock(left)}
              </span>
              <FinishButton roundId={roundId} onDone={() => void round.reload()} />
            </div>
          ) : null
        }
      />
      {r.description && <p className="muted">{r.description}</p>}

      {!isEmployer && !part && <JoinPanel round={r} onJoined={() => void round.reload()} />}
      {!isEmployer && part && over && <ResultPanel round={r} />}
      {!isEmployer && part && r.tasks.length > 0 && (
        <Workspace round={r} active={active} onSubmitted={() => { void round.reload(); loadBoard() }} />
      )}

      <h2 className="section-title mt-lg">Таблица</h2>
      {board ? <BoardWithInvite board={board} employer={isEmployer} onChange={loadBoard} /> : <Spinner />}

      {editorial && <Editorial items={editorial} />}
    </>
  )
}

function JoinPanel({ round: r, onJoined }: { round: ArenaRoundDetail; onJoined: () => void }) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  if (r.state === 'upcoming') return <div className="alert alert--info">Раунд начнётся {formatDateTime(r.starts_at)}. Возвращайтесь к старту.</div>
  if (r.state === 'finished') return <div className="alert alert--info">Раунд завершён. Ниже — итоговая таблица и разбор задач.</div>
  const join = async () => {
    setBusy(true)
    try {
      await api.joinArenaRound(r.id)
      onJoined()
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось войти в раунд'))
    } finally {
      setBusy(false)
    }
  }
  return (
    <div className="card card--glow arena-join">
      <p>
        {r.problems.length} задачи: {r.problems.map((p) => p.title).join(', ')}. Таймер{' '}
        {r.is_open ? `на ${r.duration_minutes} минут запустится сразу после нажатия` : 'общий для всех участников'}.
        У каждого участника свой вариант данных. Штраф — минуты до верного решения и 20 минут за каждую неверную попытку до него.
      </p>
      <Button icon={<Play size={16} />} loading={busy} onClick={join}>Участвовать</Button>
    </div>
  )
}

function ResultPanel({ round: r }: { round: ArenaRoundDetail }) {
  const p = r.participation!
  return (
    <div className="alert alert--success">
      <CheckCircle2 size={16} />
      <div>
        <strong>Участие завершено.</strong> Решено {p.solved} из {r.problems.length}, штраф {p.penalty}.
        {p.rating_after !== null && p.rating_before !== null && (
          <> Рейтинг Arena: {Math.round(p.rating_before)} → <strong>{Math.round(p.rating_after)}</strong>.</>
        )}
        {p.rated && p.rating_after === null && ' Без отправок рейтинг не меняется.'}
        {!p.rated && ' Рейтинг пересчитается в течение минуты.'}
      </div>
    </div>
  )
}

function FinishButton({ roundId, onDone }: { roundId: string; onDone: () => void }) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const finish = async () => {
    setBusy(true)
    try {
      await api.finishArena(roundId)
      setOpen(false)
      onDone()
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }
  return (
    <>
      <Button variant="secondary" icon={<Flag size={16} />} onClick={() => setOpen(true)}>Завершить</Button>
      <Modal
        open={open}
        title="Завершить участие?"
        onClose={() => setOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Продолжить решать</Button>
            <Button onClick={finish} loading={busy}>Завершить и пересчитать рейтинг</Button>
          </>
        }
      >
        <p>После завершения отправки не принимаются, откроются эталонные решения и пересчитается рейтинг.</p>
      </Modal>
    </>
  )
}

function Workspace({ round: r, active, onSubmitted }: { round: ArenaRoundDetail; active: boolean; onSubmitted: () => void }) {
  const toast = useToast()
  const [taskCode, setTaskCode] = useState(r.tasks[0].code)
  const task = r.tasks.find((t) => t.code === taskCode) as ArenaTask
  const [language, setLanguage] = useState<ArenaLanguage>(r.languages[0] ?? 'python')
  const key = draftKey(r.id, taskCode, language)
  const [code, setCode] = useState(() => loadDraft(key, TEMPLATES[language]))
  const [run, setRun] = useState<ArenaRunResult | null>(null)
  const [busy, setBusy] = useState<'run' | 'submit' | null>(null)
  const [subs, setSubs] = useState<ArenaSubmission[]>(r.submissions)
  const signals = useRef<Record<string, { paste_chars: number; paste_events: number }>>({})
  const blurs = useRef(0)

  useEffect(() => setSubs(r.submissions), [r.submissions])

  // черновик своей задачи и языка
  useEffect(() => {
    setCode(loadDraft(key, TEMPLATES[language]))
    setRun(null)
  }, [key, language])

  useEffect(() => {
    const onVis = () => {
      if (document.visibilityState === 'hidden') blurs.current += 1
    }
    document.addEventListener('visibilitychange', onVis)
    return () => document.removeEventListener('visibilitychange', onVis)
  }, [])

  const change = (c: string) => {
    setCode(c)
    saveDraft(key, c)
  }

  const onPaste = (chars: number) => {
    const s = (signals.current[taskCode] ??= { paste_chars: 0, paste_events: 0 })
    s.paste_chars += chars
    s.paste_events += 1
  }

  const runSamples = async () => {
    setBusy('run')
    try {
      setRun(await api.runArena(r.id, taskCode, language, code))
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось запустить'))
    } finally {
      setBusy(null)
    }
  }

  const submit = async () => {
    if (!active || busy) return
    setBusy('submit')
    try {
      const s = signals.current[taskCode] ?? { paste_chars: 0, paste_events: 0 }
      const res = await api.submitArena(r.id, taskCode, language, code, { ...s, blur_count: blurs.current })
      setSubs((cur) => [res.submission, ...cur])
      if (res.submission.verdict === 'OK') toast.success('Верно! Все тесты пройдены')
      onSubmitted()
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось отправить'))
    } finally {
      setBusy(null)
    }
  }

  const status = useMemo(() => {
    const m: Record<string, 'ok' | 'bad' | undefined> = {}
    for (const s of [...subs].reverse()) {
      if (s.verdict === 'OK') m[s.problem] = 'ok'
      else if (s.verdict && m[s.problem] !== 'ok') m[s.problem] = 'bad'
    }
    return m
  }, [subs])

  const taskSubs = subs.filter((s) => s.problem === taskCode)
  const last = taskSubs[0]

  return (
    <section className="arena-work mt">
      <Tabs
        tabs={r.tasks.map((t, i) => ({ key: t.code, label: `${String.fromCharCode(65 + i)}. ${t.title}${status[t.code] === 'ok' ? ' ✓' : ''}` }))}
        value={taskCode}
        onChange={setTaskCode}
      />
      <div className="arena-split">
        <article className="card arena-task">
          <div className="row gap-sm small muted wrap">
            <span className={`tag level-${task.level}`}>{task.level_title}</span>
            <span>{task.topic}</span>
            <span>{task.tests_total} тестов</span>
          </div>
          <h3 className="arena-task__title">{task.title}</h3>
          <Statement text={task.statement} />
          {task.samples.map((s, i) => (
            <div key={i} className="arena-sample">
              <div>
                <div className="tiny muted">Пример {i + 1}: ввод</div>
                <pre className="code-block"><code>{s.input.length > 400 ? s.input.slice(0, 400) + '…' : s.input}</code></pre>
              </div>
              <div>
                <div className="tiny muted">вывод</div>
                <pre className="code-block"><code>{s.output}</code></pre>
              </div>
            </div>
          ))}
        </article>

        <div className="stack">
          <div className="card arena-editor">
            <div className="row between wrap gap-sm">
              <div className="row gap-sm">
                {r.languages.map((l) => (
                  <button key={l} className={`chip ${l === language ? 'is-active' : ''}`} onClick={() => setLanguage(l)}>{LANG_TITLE[l]}</button>
                ))}
              </div>
              <span className="tiny muted">Черновик сохраняется · Ctrl+Enter — отправить</span>
            </div>
            <CodeEditor value={code} language={language} onChange={change} onPaste={onPaste} onSubmitShortcut={submit} />
            <div className="row end gap-sm">
              <Button variant="ghost" onClick={() => change(TEMPLATES[language])}>Сбросить</Button>
              <Button variant="secondary" icon={<Play size={16} />} loading={busy === 'run'} disabled={!active || !!busy} onClick={runSamples}>
                Запустить на примерах
              </Button>
              <Button icon={<Send size={16} />} loading={busy === 'submit'} disabled={!active || !!busy} onClick={submit}>
                Отправить
              </Button>
            </div>
            {busy === 'submit' && <div className="small muted">Проверяем на {task.tests_total} тестах…</div>}
          </div>

          {run && <RunResult run={run} />}
          {last && <SubmissionResult sub={last} />}
          {taskSubs.length > 1 && (
            <details className="card">
              <summary className="small">Все отправки по задаче ({taskSubs.length})</summary>
              <ul className="arena-history">
                {taskSubs.map((s) => (
                  <li key={s.id} className="row gap-sm small">
                    <VerdictChip verdict={s.verdict} /> {s.passed}/{s.total} · {s.time_ms ?? 0} мс · {s.minute} мин
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      </div>
    </section>
  )
}

function RunResult({ run }: { run: ArenaRunResult }) {
  return (
    <div className="card">
      <div className="row gap-sm">
        <strong>Примеры:</strong> <VerdictChip verdict={run.verdict} /> {run.passed} из {run.total}
      </div>
      {run.tests.map((t, i) => (
        <div key={i} className="mt-sm">
          <div className="small">
            Пример {i + 1}: {VERDICT_LABEL[t.verdict]} · {t.time_ms} мс
          </div>
          {t.output !== null && t.output !== undefined && (
            <pre className="code-block"><code>{t.output || '(пустой вывод)'}</code></pre>
          )}
          {t.message && <pre className="code-block code-block--err"><code>{t.message}</code></pre>}
        </div>
      ))}
    </div>
  )
}

function SubmissionResult({ sub }: { sub: ArenaSubmission }) {
  const ok = sub.verdict === 'OK'
  return (
    <div className={`card arena-result ${ok ? 'is-ok' : 'is-bad'}`} data-testid="arena-result">
      <div className="row gap-sm">
        {ok ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
        <strong>{sub.verdict ? VERDICT_LABEL[sub.verdict] : 'Проверяется'}</strong>
        <span className="small muted">
          пройдено {sub.passed} из {sub.total} · {sub.time_ms ?? 0} мс · {Math.round((sub.memory_kb ?? 0) / 1024)} МБ
        </span>
      </div>
      <div className="arena-tests" aria-label="Тесты">
        {sub.tests.map((t, i) => (
          <span key={i} className={`arena-test ${t.verdict === 'OK' ? 'is-ok' : 'is-bad'}`} title={`Тест ${i + 1}${t.sample ? ' (пример)' : ''}: ${VERDICT_LABEL[t.verdict]}, ${t.time_ms} мс`}>
            {i + 1}
          </span>
        ))}
      </div>
      {sub.message && <pre className="code-block code-block--err"><code>{sub.message}</code></pre>}
      {sub.feedback && (
        <div className="arena-feedback">
          <div className="row gap-sm small">
            <Sparkles size={14} /> <strong>Разбор решения</strong>
            <span className="tag">{sub.feedback.source === 'gigachat' ? 'GigaChat' : sub.feedback.source === 'yandexgpt' ? 'YandexGPT' : 'автоматический разбор'}</span>
          </div>
          <p>{sub.feedback.summary}</p>
          {sub.feedback.points.length > 0 && (
            <ul>
              {sub.feedback.points.map((p, i) => <li key={i}>{p}</li>)}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

function BoardWithInvite({ board, employer, onChange }: { board: ArenaBoard; employer: boolean; onChange: () => void }) {
  const [invite, setInvite] = useState<CandidateCard | null>(null)
  const toast = useToast()
  const openInvite = async (row: ArenaBoardRow) => {
    if (!row.profile_id) return
    try {
      setInvite(await api.getCandidate(row.profile_id))
    } catch (e) {
      toast.error(errorMessage(e, 'Кандидат не открыл профиль для работодателей'))
    }
  }
  return (
    <>
      <Leaderboard board={board} onInvite={employer ? openInvite : undefined} />
      {invite && (
        <InviteModal
          candidate={invite}
          onClose={() => setInvite(null)}
          onSent={() => {
            setInvite(null)
            toast.success('Приглашение отправлено')
            onChange()
          }}
        />
      )}
    </>
  )
}

function Editorial({ items }: { items: ArenaEditorialItem[] }): ReactNode {
  return (
    <section className="mt-lg">
      <h2 className="section-title"><BookOpen size={18} /> Разбор задач</h2>
      <div className="stack">
        {items.map((p, i) => (
          <details key={p.code} className="card">
            <summary>
              <strong>{String.fromCharCode(65 + i)}. {p.title}</strong>{' '}
              <span className="small muted">
                решили {p.solved} из {p.tried}
                {p.solve_rate !== null && ` (${p.solve_rate}%)`} · {p.submissions} отправок
              </span>
            </summary>
            <p className="mt-sm">{p.idea}</p>
            <p className="small muted">Сложность эталона: {p.complexity}. Частые ошибки: {p.pitfalls.join('; ')}.</p>
            <pre className="code-block"><code>{p.reference}</code></pre>
          </details>
        ))}
      </div>
    </section>
  )
}
