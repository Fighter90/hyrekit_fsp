import { useState } from 'react'
import { Plus, CalendarClock, Inbox } from 'lucide-react'
import { api } from '../../api/client'
import type { Challenge, ChallengeSubmission } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Modal from '../../components/ui/Modal'
import Field from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { EmptyState, ErrorState, Spinner } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { errorMessage, formatDate, formatDateTime } from '../../lib/format'

export default function EmployerChallengesPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getEmployerChallenges())
  const { specTitle } = useCatalog()
  const [creating, setCreating] = useState(false)
  const [viewing, setViewing] = useState<Challenge | null>(null)

  return (
    <>
      <PageHeader
        
        title="Короткие задания"
        subtitle="Небольшие задачи для кандидатов вашей специализации — способ заметить сильных до приглашения."
        actions={<Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>Новое задание</Button>}
      />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonList count={3} lines={2} />}
      {data && data.length === 0 && (
        <EmptyState glyph="</>" title="Заданий пока нет" text="Создайте задание на 15–30 минут — кандидаты увидят его в своём кабинете." action={<Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>Создать</Button>} />
      )}
      <div className="vacancy-grid">
        {data?.map((c, i) => (
          <Reveal key={c.id} delay={i * 40}>
            <article className="card card--glow card--hover challenge">
              <div className="row between gap-sm small muted">
                <span className="tag">{specTitle(c.specialization)}</span>
                {c.due_at && <span><CalendarClock size={13} style={{ display: 'inline' }} /> до {formatDate(c.due_at)}</span>}
              </div>
              <h3 className="challenge__title">{c.title}</h3>
              <p className="muted small clamp-3 prewrap">{c.description}</p>
              <div className="row end mt">
                <Button variant="secondary" size="sm" icon={<Inbox size={14} />} onClick={() => setViewing(c)}>Ответы</Button>
              </div>
            </article>
          </Reveal>
        ))}
      </div>
      {creating && <CreateModal onClose={() => setCreating(false)} onCreated={(c) => setData((d) => [c, ...(d ?? [])])} />}
      {viewing && <SubmissionsModal challenge={viewing} onClose={() => setViewing(null)} />}
    </>
  )
}

function CreateModal({ onClose, onCreated }: { onClose: () => void; onCreated: (c: Challenge) => void }) {
  const { catalog } = useCatalog()
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [spec, setSpec] = useState('')
  const [due, setDue] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = async () => {
    if (title.trim().length < 3 || description.trim().length < 10 || !spec) {
      setErr('Заполните название, специализацию и условие (от 10 символов)')
      return
    }
    setErr(null)
    setBusy(true)
    try {
      const c = await api.createChallenge({
        title: title.trim(),
        description: description.trim(),
        specialization: spec,
        // дата из поля — конец выбранного дня по местному времени
        due_at: due ? new Date(`${due}T23:59:59`).toISOString() : null,
      })
      onCreated(c)
      toast.success('Задание опубликовано')
      onClose()
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось создать задание'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      wide
      title="Новое задание"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button loading={busy} onClick={submit}>Опубликовать</Button>
        </>
      }
    >
      <div className="stack">
        <Field label="Название" htmlFor="ch-title" required>
          <input id="ch-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Найдите утечку памяти в сервисе" />
        </Field>
        <div className="form-grid">
          <Field label="Специализация" htmlFor="ch-spec" required>
            <select id="ch-spec" className="select" value={spec} onChange={(e) => setSpec(e.target.value)}>
              <option value="">Выберите</option>
              {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
            </select>
          </Field>
          <Field label="Срок" htmlFor="ch-due" hint="Необязательно">
            <input id="ch-due" type="date" className="input" value={due} onChange={(e) => setDue(e.target.value)} />
          </Field>
        </div>
        <Field label="Условие" htmlFor="ch-desc" required hint="Можно вставить код — моноширинный шрифт сохранит форматирование">
          <textarea id="ch-desc" className="textarea code-input" rows={8} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        {err && <div className="alert alert--error">{err}</div>}
      </div>
    </Modal>
  )
}

function SubmissionsModal({ challenge, onClose }: { challenge: Challenge; onClose: () => void }) {
  const { data, error, loading, reload } = useAsync<ChallengeSubmission[]>(() => api.getChallengeSubmissions(challenge.id), [challenge.id])
  return (
    <Modal open wide title={`Ответы: ${challenge.title}`} onClose={onClose}>
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && <Spinner />}
      {data && data.length === 0 && <EmptyState glyph="…" title="Ответов пока нет" text="Кандидаты увидят задание в разделе «Челленджи»." />}
      <div className="stack">
        {data?.map((s, i) => (
          <div key={s.id} className="submission">
            <div className="row between small muted">
              <span>Ответ #{i + 1}</span>
              <span>{formatDateTime(s.created_at)}{s.score !== null && ` · оценка ${s.score}`}</span>
            </div>
            <pre className="code-block"><code>{s.answer}</code></pre>
            {s.feedback && <p className="small muted">{s.feedback}</p>}
          </div>
        ))}
      </div>
    </Modal>
  )
}
