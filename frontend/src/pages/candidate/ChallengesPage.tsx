import { useState } from 'react'
import { Send, CalendarClock, CheckCircle2, Building2 } from 'lucide-react'
import { api } from '../../api/client'
import type { Challenge, ChallengeSubmission } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import { Button } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { errorMessage, formatDate } from '../../lib/format'

export default function CandidateChallengesPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getCandidateChallenges())
  const [results, setResults] = useState<Record<string, ChallengeSubmission>>({})

  const onSubmitted = (c: Challenge, s: ChallengeSubmission) => {
    setResults((r) => ({ ...r, [c.id]: s }))
    setData((d) => d?.map((x) => (x.id === c.id ? { ...x, submitted: true } : x)) ?? d)
  }

  return (
    <>
      <PageHeader title="Челленджи" subtitle="Короткие задания от компаний. Хорошее решение — повод для приглашения." />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonList count={3} />}
      {data && data.length === 0 && <EmptyState glyph="</>" title="Челленджей пока нет" text="Компании публикуют задания регулярно — загляните позже." />}
      <div className="stack">
        {data?.map((c, i) => (
          <Reveal key={c.id} delay={i * 50}>
            <ChallengeCard challenge={c} submission={results[c.id]} onSubmitted={(s) => onSubmitted(c, s)} />
          </Reveal>
        ))}
      </div>
    </>
  )
}

function ChallengeCard({ challenge: c, submission, onSubmitted }: { challenge: Challenge; submission?: ChallengeSubmission; onSubmitted: (s: ChallengeSubmission) => void }) {
  const { specTitle } = useCatalog()
  const toast = useToast()
  const [open, setOpen] = useState(false)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const overdue = c.due_at ? new Date(c.due_at).getTime() < Date.now() : false

  const submit = async () => {
    if (!answer.trim()) return
    setBusy(true)
    try {
      const s = await api.submitChallenge(c.id, answer.trim())
      onSubmitted(s)
      setOpen(false)
      toast.success('Ответ отправлен')
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось отправить ответ'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <article className={`card card--glow challenge ${c.submitted ? 'is-done' : ''}`}>
      <div className="row between wrap gap-sm">
        <div className="row gap-sm small muted">
          <Building2 size={14} /> {c.company_name}
          <span className="tag">{specTitle(c.specialization)}</span>
        </div>
        {c.due_at && (
          <span className={`small ${overdue ? 'text-red' : 'muted'}`}>
            <CalendarClock size={14} style={{ display: 'inline' }} /> до {formatDate(c.due_at)}
          </span>
        )}
      </div>
      <h3 className="challenge__title">{c.title}</h3>
      <p className="prewrap muted">{c.description}</p>

      {c.submitted ? (
        <div className="alert alert--success mt">
          <CheckCircle2 size={16} />
          <div>
            <strong>Ответ отправлен.</strong>{' '}
            {submission?.score !== null && submission?.score !== undefined
              ? `Оценка: ${submission.score}.`
              : 'Компания проверит решение.'}
            {submission?.feedback && <div className="small">{submission.feedback}</div>}
          </div>
        </div>
      ) : open ? (
        <div className="stack mt">
          <textarea
            className="textarea code-input"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="// ваше решение или ответ"
            rows={8}
            aria-label="Ответ"
            autoFocus
          />
          <div className="row end gap-sm">
            <Button variant="ghost" onClick={() => setOpen(false)}>Отмена</Button>
            <Button icon={<Send size={16} />} loading={busy} disabled={!answer.trim()} onClick={submit}>Отправить</Button>
          </div>
        </div>
      ) : (
        <div className="row end mt">
          <Button onClick={() => setOpen(true)} disabled={overdue}>{overdue ? 'Срок истёк' : 'Решить'}</Button>
        </div>
      )}
    </article>
  )
}
