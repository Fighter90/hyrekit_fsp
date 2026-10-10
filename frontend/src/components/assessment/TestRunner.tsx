import { useCallback, useEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Clock, Flag, Check, CloudOff, Loader2 } from 'lucide-react'
import type { AnswerValue, AttemptItem, AttemptResult, AttemptView } from '../../api/types'
import { api } from '../../api/client'
import { useNow } from '../../hooks/useNow'
import {
  DIFFICULTY_LABEL, countAnswered, formatCountdown, isAnswered, isOptionSelected, msLeft, nextUnanswered,
  sanitizeNumberInput, toggleMulti,
} from '../../lib/assessment'
import { Button } from '../ui/Button'
import Modal from '../ui/Modal'
import { errorMessage, gradeLabel } from '../../lib/format'
import { useToast } from '../../contexts/ToastContext'

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

interface Props {
  attempt: AttemptView
  onFinished: (r: AttemptResult) => void
  /** Сохранение локального снимка ответов (восстановление после перезагрузки). */
  onAnswersChange?: (answers: Record<string, AnswerValue>) => void
  specTitle?: string
}

/**
 * Прохождение теста: одно задание на экран, автосохранение каждого ответа,
 * обратный отсчёт до deadline_at, автоматическое завершение по таймеру.
 */
export default function TestRunner({ attempt, onFinished, onAnswersChange, specTitle }: Props) {
  const toast = useToast()
  const items = attempt.items
  const [index, setIndex] = useState(() => {
    const first = items.findIndex((it) => !isAnswered(it, attempt.answers?.[it.id]))
    return first === -1 ? 0 : first
  })
  const [answers, setAnswers] = useState<Record<string, AnswerValue>>(() => ({ ...(attempt.answers ?? {}) }))
  const [saveState, setSaveState] = useState<Record<string, SaveState>>({})
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [finishing, setFinishing] = useState(false)
  const now = useNow(1000)
  const left = msLeft(attempt.deadline_at, now)
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const finishedRef = useRef(false)

  const item = items[index]
  const answered = countAnswered(items, answers)
  const progress = items.length ? (answered / items.length) * 100 : 0

  const persist = useCallback(
    async (itemId: string, value: AnswerValue) => {
      setSaveState((s) => ({ ...s, [itemId]: 'saving' }))
      try {
        await api.saveAnswer(attempt.id, itemId, value)
        setSaveState((s) => ({ ...s, [itemId]: 'saved' }))
      } catch {
        setSaveState((s) => ({ ...s, [itemId]: 'error' }))
      }
    },
    [attempt.id],
  )

  /** Обновляет ответ; для числового ввода сохранение откладывается (debounce). */
  const setAnswer = (it: AttemptItem, value: AnswerValue, debounce = 0) => {
    setAnswers((a) => {
      const next = { ...a, [it.id]: value }
      onAnswersChange?.(next)
      return next
    })
    clearTimeout(timers.current[it.id])
    if (debounce) timers.current[it.id] = setTimeout(() => void persist(it.id, value), debounce)
    else void persist(it.id, value)
  }

  // сбросить отложенные сохранения при размонтировании
  useEffect(() => {
    const t = timers.current
    return () => Object.values(t).forEach(clearTimeout)
  }, [])

  const finish = useCallback(async () => {
    if (finishedRef.current) return
    finishedRef.current = true
    setFinishing(true)
    setConfirmOpen(false)
    try {
      // дождаться отложенных сохранений числовых ответов
      const pending = Object.entries(timers.current)
      pending.forEach(([, t]) => clearTimeout(t))
      await Promise.all(
        pending.map(([id]) => (answers[id] !== undefined ? api.saveAnswer(attempt.id, id, answers[id]).catch(() => undefined) : undefined)),
      )
      const res = await api.finishAttempt(attempt.id)
      onFinished(res)
    } catch (e) {
      finishedRef.current = false
      toast.error(errorMessage(e, 'Не удалось завершить тест'))
    } finally {
      setFinishing(false)
    }
  }, [answers, attempt.id, onFinished, toast])

  // время вышло — завершаем автоматически
  useEffect(() => {
    if (left <= 0 && !finishedRef.current) {
      toast.info('Время вышло — отправляем ответы')
      void finish()
    }
  }, [left, finish, toast])

  // клавиатура: стрелки — навигация, 1..9 — выбор варианта
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA' || confirmOpen) return
      if (e.key === 'ArrowRight') setIndex((i) => Math.min(items.length - 1, i + 1))
      else if (e.key === 'ArrowLeft') setIndex((i) => Math.max(0, i - 1))
      else if (/^[1-9]$/.test(e.key) && item && item.kind !== 'number') {
        const opt = Number(e.key) - 1
        if (opt < item.options.length) {
          setAnswer(item, item.kind === 'multi' ? toggleMulti(answers[item.id], opt) : String(opt))
        }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  if (!item) return null
  const value = answers[item.id]
  const st = saveState[item.id] ?? 'idle'
  const urgent = left < 60_000

  const goNext = () => {
    if (index < items.length - 1) setIndex(index + 1)
    else {
      const n = nextUnanswered(items, answers, index)
      if (n === -1) setConfirmOpen(true)
      else setIndex(n)
    }
  }

  return (
    <div className="runner">
      <div className="runner__top card">
        <div className="runner__meta">
          <span className="kicker">{specTitle ?? attempt.specialization} · {gradeLabel(attempt.grade)}</span>
          <span className="runner__count mono-num">
            Задание {index + 1} / {items.length}
          </span>
        </div>
        <div className={`runner__timer ${urgent ? 'is-urgent' : ''}`} role="timer" aria-live={urgent ? 'assertive' : 'off'}>
          <Clock size={16} aria-hidden />
          <span className="mono-num">{formatCountdown(left)}</span>
        </div>
        <div className="runner__progress" role="progressbar" aria-valuenow={answered} aria-valuemin={0} aria-valuemax={items.length} aria-label="Отвечено заданий">
          <div className="runner__progress-fill" style={{ width: `${progress}%` }} />
        </div>
      </div>

      <div className="runner__body">
        <article className="card runner__item" key={item.id}>
          <div className="runner__item-head">
            <span className="tag">{item.topic}</span>
            <span className="difficulty" title={`Сложность ${item.difficulty} из 5`}>
              {Array.from({ length: 5 }, (_, i) => (
                <i key={i} className={i < item.difficulty ? 'is-on' : ''} />
              ))}
              <small>{DIFFICULTY_LABEL[item.difficulty] ?? ''}</small>
            </span>
            <SaveIndicator state={st} />
          </div>
          <h2 className="runner__stem">{item.stem}</h2>
          {item.code && (
            <pre className="code-block"><code>{item.code}</code></pre>
          )}

          {item.kind === 'number' ? (
            <div className="runner__number">
              <label className="field__label" htmlFor={`num-${item.id}`}>Ваш ответ (число)</label>
              <input
                id={`num-${item.id}`}
                className="input input--big"
                inputMode="decimal"
                autoComplete="off"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => setAnswer(item, sanitizeNumberInput(e.target.value), 600)}
                onKeyDown={(e) => e.key === 'Enter' && goNext()}
                placeholder="0"
              />
            </div>
          ) : (
            <div className={`options ${item.kind === 'multi' ? 'options--multi' : ''}`} role={item.kind === 'multi' ? 'group' : 'radiogroup'}>
              {item.kind === 'multi' && <p className="muted small">Выберите все верные варианты</p>}
              {item.options.map((opt, i) => {
                const selected = isOptionSelected(value, i)
                return (
                  <button
                    type="button"
                    key={i}
                    role={item.kind === 'multi' ? 'checkbox' : 'radio'}
                    aria-checked={selected}
                    className={`option ${selected ? 'is-selected' : ''}`}
                    onClick={() => setAnswer(item, item.kind === 'multi' ? toggleMulti(value, i) : String(i))}
                  >
                    <span className="option__key">{item.kind === 'multi' ? (selected ? <Check size={14} /> : '') : String.fromCharCode(65 + i)}</span>
                    <span className="option__text">{opt}</span>
                    <kbd className="option__kbd">{i + 1}</kbd>
                  </button>
                )
              })}
            </div>
          )}

          <div className="runner__nav">
            <Button variant="ghost" icon={<ChevronLeft size={16} />} disabled={index === 0} onClick={() => setIndex(index - 1)}>
              Назад
            </Button>
            <Button variant="secondary" icon={<Flag size={16} />} onClick={() => setConfirmOpen(true)} loading={finishing}>
              Завершить
            </Button>
            <Button iconRight={<ChevronRight size={16} />} onClick={goNext}>
              {index < items.length - 1 ? 'Далее' : 'К неотвеченным'}
            </Button>
          </div>
        </article>

        <aside className="card runner__map" aria-label="Карта заданий">
          <div className="card__title">Задания <small>{answered}/{items.length}</small></div>
          <div className="qmap">
            {items.map((it, i) => (
              <button
                key={it.id}
                className={`qmap__cell ${i === index ? 'is-current' : ''} ${isAnswered(it, answers[it.id]) ? 'is-done' : ''} ${saveState[it.id] === 'error' ? 'is-error' : ''}`}
                onClick={() => setIndex(i)}
                aria-label={`Задание ${i + 1}${isAnswered(it, answers[it.id]) ? ', отвечено' : ''}`}
              >
                {i + 1}
              </button>
            ))}
          </div>
          <p className="muted tiny mt">Ответы сохраняются автоматически. Клавиши: ← → и 1–9.</p>
        </aside>
      </div>

      <Modal
        open={confirmOpen}
        title="Завершить тест?"
        onClose={() => setConfirmOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>Продолжить</Button>
            <Button onClick={() => void finish()} loading={finishing}>Завершить и узнать результат</Button>
          </>
        }
      >
        <p>
          Отвечено <strong>{answered}</strong> из <strong>{items.length}</strong>.
          {answered < items.length && ' Неотвеченные задания засчитаются как неверные.'}
        </p>
        <p className="muted small mt">До конца отведённого времени: {formatCountdown(left)}</p>
      </Modal>
    </div>
  )
}

function SaveIndicator({ state }: { state: SaveState }) {
  if (state === 'saving') return <span className="save-ind"><Loader2 size={12} className="spin" /> сохраняем</span>
  if (state === 'saved') return <span className="save-ind is-ok"><Check size={12} /> сохранено</span>
  if (state === 'error') return <span className="save-ind is-err"><CloudOff size={12} /> не сохранено</span>
  return <span className="save-ind" />
}
