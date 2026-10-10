import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Send, Trophy } from 'lucide-react'
import { api } from '../../api/client'
import type { ArenaRound, ArenaTopItem, CandidateCard } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Modal from '../../components/ui/Modal'
import Field from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import InviteModal from '../../components/employer/InviteModal'
import { RoundCard } from '../../components/arena/parts'
import { GRADE_LABEL, GRADE_ORDER, errorMessage } from '../../lib/format'

/** Arena работодателя: витрина по рейтингу, свои раунды, создание раунда. */
export default function EmployerArenaPage() {
  const { catalog } = useCatalog()
  const [spec, setSpec] = useState('')
  const [grade, setGrade] = useState('')
  const [fspOnly, setFspOnly] = useState(false)
  const top = useAsync(
    () => api.getArenaTop({ specialization: spec || undefined, grade: grade || undefined, has_fsp: fspOnly ? true : undefined }),
    [spec, grade, fspOnly],
  )
  const rounds = useAsync(() => api.getArenaRounds())
  const [creating, setCreating] = useState(false)
  const [invite, setInvite] = useState<CandidateCard | null>(null)
  const toast = useToast()

  return (
    <>
      <PageHeader
        title="Code Arena"
        subtitle="Кандидаты решают алгоритмические задачи на скрытых тестах. Рейтинг считается по Glicko-2 и входит в балл подборки как подтверждённое достижение."
        actions={<Button icon={<Plus size={16} />} onClick={() => setCreating(true)}>Раунд компании</Button>}
      />

      <section className="card">
        <div className="card__title"><Trophy size={16} /> Витрина Arena</div>
        <div className="form-grid mt-sm">
          <Field label="Специализация" htmlFor="at-spec">
            <select id="at-spec" className="select" value={spec} onChange={(e) => setSpec(e.target.value)}>
              <option value="">Все</option>
              {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
            </select>
          </Field>
          <Field label="Грейд" htmlFor="at-grade">
            <select id="at-grade" className="select" value={grade} onChange={(e) => setGrade(e.target.value)}>
              <option value="">Любой</option>
              {GRADE_ORDER.map((g) => <option key={g} value={g}>{GRADE_LABEL[g]}</option>)}
            </select>
          </Field>
        </div>
        <label className="row gap-sm small mt-sm">
          <input type="checkbox" checked={fspOnly} onChange={(e) => setFspOnly(e.target.checked)} /> Только участники ФСП
        </label>
        {top.error && <ErrorState message={top.error} onRetry={top.reload} />}
        {top.loading && !top.data && <SkeletonList count={3} lines={1} />}
        {top.data && top.data.items.length === 0 && (
          <EmptyState glyph="</>" title="Пока никого" text="Рейтинг появляется после первого завершённого раунда." />
        )}
        {top.data && top.data.items.length > 0 && <TopTable items={top.data.items} onInvite={setInvite} />}
      </section>

      <h2 className="section-title mt">Раунды</h2>
      {rounds.error && <ErrorState message={rounds.error} onRetry={rounds.reload} />}
      {rounds.loading && !rounds.data && <SkeletonList count={2} />}
      <div className="arena-rounds">
        {rounds.data?.map((r) => <RoundCard key={r.id} round={r} />)}
      </div>

      {creating && (
        <CreateRoundModal
          onClose={() => setCreating(false)}
          onCreated={(r) => rounds.setData((d) => [r, ...(d ?? [])])}
        />
      )}
      {invite && (
        <InviteModal
          candidate={invite}
          onClose={() => setInvite(null)}
          onSent={() => {
            setInvite(null)
            toast.success('Приглашение отправлено')
            top.reload()
          }}
        />
      )}
    </>
  )
}

function TopTable({ items, onInvite }: { items: ArenaTopItem[]; onInvite: (c: CandidateCard) => void }) {
  return (
    <div className="table-wrap mt-sm">
      <table className="table arena-board">
        <thead>
          <tr>
            <th>#</th>
            <th>Кандидат</th>
            <th>Рейтинг</th>
            <th>Раундов</th>
            <th>Решено</th>
            <th>Топ</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {items.map((it, i) => (
            <tr key={it.candidate.id}>
              <td>{i + 1}</td>
              <td>
                <Link to={`/app/candidates/${it.candidate.id}`}>{it.candidate.display_name}</Link>
                <div className="small muted">
                  {it.candidate.headline ?? it.candidate.category_title} · {GRADE_LABEL[it.candidate.grade]}
                </div>
              </td>
              <td>
                <strong>{Math.round(it.arena.rating)}</strong>
                <span className="small muted"> ±{Math.round(it.arena.rd)}</span>
                {it.arena.provisional && <div className="small text-warn">предварительный</div>}
              </td>
              <td>{it.arena.rounds}</td>
              <td>{it.arena.solved}</td>
              <td>{it.top_percent !== null ? `${it.top_percent}%` : '—'}</td>
              <td>
                {it.candidate.invitation_status ? (
                  <span className="small muted">Приглашён</span>
                ) : (
                  <Button size="sm" variant="secondary" icon={<Send size={14} />} onClick={() => onInvite(it.candidate)}>
                    Пригласить
                  </Button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function localInput(d: Date): string {
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}T${p(d.getHours())}:${p(d.getMinutes())}`
}

function CreateRoundModal({ onClose, onCreated }: { onClose: () => void; onCreated: (r: ArenaRound) => void }) {
  const { catalog } = useCatalog()
  const problems = useAsync(() => api.getArenaProblems())
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [spec, setSpec] = useState('')
  const [startsAt, setStartsAt] = useState(() => localInput(new Date(Date.now() + 60 * 60 * 1000)))
  const [duration, setDuration] = useState('60')
  const [prize, setPrize] = useState('')
  const [picked, setPicked] = useState<string[]>([])
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const togglePick = (code: string) =>
    setPicked((cur) => (cur.includes(code) ? cur.filter((c) => c !== code) : [...cur, code]))

  const submit = async () => {
    const minutes = Number(duration)
    if (title.trim().length < 3) return setErr('Название — от 3 символов')
    if (picked.length === 0) return setErr('Выберите хотя бы одну задачу')
    if (!startsAt || new Date(startsAt).getTime() < Date.now()) return setErr('Начало раунда должно быть в будущем')
    if (!Number.isInteger(minutes) || minutes < 15 || minutes > 240) return setErr('Длительность — от 15 до 240 минут')
    setErr(null)
    setBusy(true)
    try {
      const r = await api.createArenaRound({
        title: title.trim(),
        description: description.trim() || undefined,
        specialization: spec || null,
        problems: picked,
        starts_at: new Date(startsAt).toISOString(),
        duration_minutes: minutes,
        prize: prize.trim() || undefined,
      })
      onCreated(r)
      toast.success('Раунд создан')
      onClose()
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось создать раунд'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open
      wide
      title="Раунд компании"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button loading={busy} onClick={submit}>Создать</Button>
        </>
      }
    >
      <div className="stack">
        <Field label="Название" htmlFor="ar-title" required>
          <input id="ar-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Осенний раунд backend" />
        </Field>
        <Field label="Описание" htmlFor="ar-desc" hint="Необязательно">
          <textarea id="ar-desc" className="textarea" rows={3} value={description} onChange={(e) => setDescription(e.target.value)} />
        </Field>
        <div className="form-grid">
          <Field label="Специализация" htmlFor="ar-spec" hint="Пусто — открыт всем">
            <select id="ar-spec" className="select" value={spec} onChange={(e) => setSpec(e.target.value)}>
              <option value="">Все</option>
              {catalog?.specializations.map((s) => <option key={s.code} value={s.code}>{s.title}</option>)}
            </select>
          </Field>
          <Field label="Начало" htmlFor="ar-start" required>
            <input id="ar-start" type="datetime-local" className="input" value={startsAt} onChange={(e) => setStartsAt(e.target.value)} />
          </Field>
          <Field label="Длительность, мин" htmlFor="ar-dur" required>
            <input id="ar-dur" type="number" min={15} max={240} className="input" value={duration} onChange={(e) => setDuration(e.target.value)} />
          </Field>
          <Field label="Приз" htmlFor="ar-prize" hint="Например, оффер на собеседование">
            <input id="ar-prize" className="input" value={prize} onChange={(e) => setPrize(e.target.value)} />
          </Field>
        </div>
        <Field label="Задачи" required hint="Порядок выбора — порядок в раунде">
          <div className="stack-sm">
            {problems.data?.map((p) => (
              <label key={p.code} className="row gap-sm">
                <input type="checkbox" checked={picked.includes(p.code)} onChange={() => togglePick(p.code)} />
                <span>{p.title}</span>
                <span className={`tag level-${p.level}`}>{p.level_title}</span>
                <span className="small muted">{p.topic}</span>
              </label>
            ))}
          </div>
        </Field>
        {err && <div className="alert alert--error">{err}</div>}
      </div>
    </Modal>
  )
}
