import { useEffect, useRef, useState, type DragEvent, type FormEvent } from 'react'
import { Download, FileUp, Save, Sparkles, FileText } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateProfile, CandidateProfileUpdate, WorkFormat } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Field from '../../components/ui/Field'
import TagInput from '../../components/ui/TagInput'
import { Button } from '../../components/ui/Button'
import { ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { CategoryBadge } from '../../components/ui/Badges'
import { errorMessage, saveBlob } from '../../lib/format'

// Состояние формы: числа храним строками, чтобы поле можно было очистить
interface FormState {
  full_name: string
  headline: string
  city: string
  phone: string
  telegram: string
  contact_email: string
  about: string
  industry: string
  work_format: WorkFormat | ''
  experience_years: string
  salary_from: string
  salary_to: string
  stack: string[]
  roles: string[]
  soft_skills: string[]
}

const s = (v: string | null | undefined) => v ?? ''
const n = (v: number | null | undefined) => (v === null || v === undefined ? '' : String(v))

function toForm(p: CandidateProfileUpdate): FormState {
  return {
    full_name: s(p.full_name),
    headline: s(p.headline),
    city: s(p.city),
    phone: s(p.phone),
    telegram: s(p.telegram),
    contact_email: s(p.contact_email),
    about: s(p.about),
    industry: s(p.industry),
    work_format: (p.work_format ?? '') as WorkFormat | '',
    experience_years: n(p.experience_years),
    salary_from: n(p.salary_from),
    salary_to: n(p.salary_to),
    stack: p.stack ?? [],
    roles: p.roles ?? [],
    soft_skills: p.soft_skills ?? [],
  }
}

const numOrNull = (v: string) => (v.trim() === '' ? null : Number(v))
const strOrNull = (v: string) => (v.trim() === '' ? null : v.trim())

function toUpdate(f: FormState): CandidateProfileUpdate {
  return {
    full_name: strOrNull(f.full_name),
    headline: strOrNull(f.headline),
    city: strOrNull(f.city),
    phone: strOrNull(f.phone),
    telegram: strOrNull(f.telegram),
    contact_email: strOrNull(f.contact_email),
    about: strOrNull(f.about),
    industry: strOrNull(f.industry),
    work_format: f.work_format || null,
    experience_years: numOrNull(f.experience_years),
    salary_from: numOrNull(f.salary_from),
    salary_to: numOrNull(f.salary_to),
    stack: f.stack,
    roles: f.roles,
    soft_skills: f.soft_skills,
  }
}

/** Слияние распознанных из резюме полей: пустые значения не затирают введённое. */
function mergeParsed(form: FormState, fields: CandidateProfileUpdate): { next: FormState; changed: string[] } {
  const parsed = toForm(fields)
  const next = { ...form }
  const rec = next as unknown as Record<string, string | string[]>
  const changed: string[] = []
  for (const key of Object.keys(fields) as (keyof CandidateProfileUpdate)[]) {
    const k = key as keyof FormState
    const v = parsed[k]
    if (Array.isArray(v)) {
      const cur = next[k] as string[]
      const merged = [...cur, ...v.filter((x) => !cur.some((c) => c.toLowerCase() === x.toLowerCase()))]
      if (merged.length !== cur.length) {
        rec[k] = merged
        changed.push(k)
      }
    } else if (v !== '' && v !== next[k]) {
      rec[k] = v
      changed.push(k)
    }
  }
  return { next, changed }
}

const LABELS: Record<string, string> = {
  full_name: 'ФИО', headline: 'желаемая роль', city: 'город', phone: 'телефон', telegram: 'Telegram',
  contact_email: 'email', about: 'о себе', industry: 'отрасль', work_format: 'формат', experience_years: 'опыт',
  salary_from: 'зарплата от', salary_to: 'зарплата до', stack: 'стек', roles: 'роли', soft_skills: 'soft skills',
}

export default function ProfilePage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getCandidateProfile())
  return (
    <>
      <PageHeader title="Профиль" subtitle="Чем полнее профиль, тем точнее подбор. Работодатель увидит его в карточке кандидата." />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonCard lines={8} />}
      {data && <ProfileForm profile={data} onSaved={setData} />}
    </>
  )
}

function ProfileForm({ profile, onSaved }: { profile: CandidateProfile; onSaved: (p: CandidateProfile) => void }) {
  const { catalog } = useCatalog()
  const toast = useToast()
  const [form, setForm] = useState<FormState>(() => toForm(profile))
  const [dirty, setDirty] = useState(false)
  const [saving, setSaving] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [drag, setDrag] = useState(false)
  const [highlight, setHighlight] = useState<string[]>([])
  const [pdfBusy, setPdfBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // предупреждение о несохранённых изменениях при закрытии вкладки
  useEffect(() => {
    if (!dirty) return
    const h = (e: BeforeUnloadEvent) => e.preventDefault()
    window.addEventListener('beforeunload', h)
    return () => window.removeEventListener('beforeunload', h)
  }, [dirty])

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => {
    setForm((f) => ({ ...f, [k]: v }))
    setDirty(true)
  }

  const salaryError =
    form.salary_from && form.salary_to && Number(form.salary_from) > Number(form.salary_to) ? '«От» не может быть больше «до»' : null

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    if (salaryError) return
    setSaving(true)
    try {
      const p = await api.updateCandidateProfile(toUpdate(form))
      onSaved(p)
      setDirty(false)
      setHighlight([])
      toast.success('Профиль сохранён')
    } catch (err) {
      toast.error(errorMessage(err, 'Не удалось сохранить'))
    } finally {
      setSaving(false)
    }
  }

  const upload = async (file: File) => {
    if (!/\.(pdf|docx)$/i.test(file.name)) {
      toast.error('Поддерживаются только PDF и DOCX')
      return
    }
    if (file.size > 10 * 1024 * 1024) {
      toast.error('Файл больше 10 МБ')
      return
    }
    setUploading(true)
    try {
      const res = await api.uploadResume(file)
      const { next, changed } = mergeParsed(form, res.fields)
      setForm(next)
      setHighlight(changed)
      if (changed.length) {
        setDirty(true)
        toast.success(`Распознано: ${changed.map((c) => LABELS[c] ?? c).join(', ')}. Проверьте и сохраните.`)
      } else {
        toast.info('Новых данных в резюме не найдено')
      }
    } catch (err) {
      toast.error(errorMessage(err, 'Не удалось разобрать резюме'))
    } finally {
      setUploading(false)
      if (fileRef.current) fileRef.current.value = ''
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setDrag(false)
    const f = e.dataTransfer.files?.[0]
    if (f) void upload(f)
  }

  const downloadPdf = async () => {
    setPdfBusy(true)
    try {
      const blob = await api.downloadProfilePdf()
      saveBlob(blob, 'hyrekit-profile.pdf')
    } catch (err) {
      toast.error(errorMessage(err, 'PDF пока недоступен'))
    } finally {
      setPdfBusy(false)
    }
  }

  const hl = (k: keyof FormState) => (highlight.includes(k) ? 'is-autofilled' : '')
  const specHints = catalog?.specializations.find((x) => x.code === profile.specialization)?.stack_hints ?? []

  return (
    <div className="profile-layout">
      <form className="stack-lg" onSubmit={onSubmit}>
        <div
          className={`dropzone ${drag ? 'is-drag' : ''} ${uploading ? 'is-busy' : ''}`}
          onDragOver={(e) => {
            e.preventDefault()
            setDrag(true)
          }}
          onDragLeave={() => setDrag(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileRef.current?.click()}
        >
          <input ref={fileRef} type="file" accept=".pdf,.docx" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
          <div className="dropzone__icon">{uploading ? <Sparkles size={24} className="spin-slow" /> : <FileUp size={24} />}</div>
          <div>
            <strong>{uploading ? 'Распознаём резюме…' : 'Загрузите резюме — заполним анкету за вас'}</strong>
            <p className="muted small">PDF или DOCX до 10 МБ. Перетащите файл сюда или нажмите.</p>
          </div>
        </div>

        <div className="card">
          <section className="form-section">
            <h2 className="form-section__title">Основное</h2>
            <div className="form-grid">
              <Field label="ФИО" htmlFor="full_name" className={hl('full_name')}>
                <input id="full_name" className="input" value={form.full_name} onChange={(e) => set('full_name', e.target.value)} />
              </Field>
              <Field label="Желаемая роль" htmlFor="headline" hint="Например: Python backend-разработчик" className={hl('headline')}>
                <input id="headline" className="input" value={form.headline} onChange={(e) => set('headline', e.target.value)} />
              </Field>
              <Field label="Город" htmlFor="city" className={hl('city')}>
                <input id="city" className="input" value={form.city} onChange={(e) => set('city', e.target.value)} />
              </Field>
              <Field label="Отрасль" htmlFor="industry" className={hl('industry')}>
                <select id="industry" className="select" value={form.industry} onChange={(e) => set('industry', e.target.value)}>
                  <option value="">Не выбрана</option>
                  {catalog?.industries.map((i) => <option key={i.code} value={i.code}>{i.title}</option>)}
                </select>
              </Field>
              <Field label="О себе" htmlFor="about" className={`span-2 ${hl('about')}`}>
                <textarea id="about" className="textarea" value={form.about} onChange={(e) => set('about', e.target.value)} rows={4} />
              </Field>
            </div>
          </section>

          <section className="form-section">
            <h2 className="form-section__title">Навыки</h2>
            <div className="stack">
              <Field label="Стек технологий" htmlFor="stack" hint="Enter или запятая — добавить" className={hl('stack')}>
                <TagInput id="stack" value={form.stack} onChange={(v) => set('stack', v)} suggestions={specHints} placeholder="Python, FastAPI, PostgreSQL…" />
              </Field>
              <div className="form-grid">
                <Field label="Роли" htmlFor="roles" className={hl('roles')}>
                  <TagInput id="roles" value={form.roles} onChange={(v) => set('roles', v)} placeholder="Тимлид, ментор…" />
                </Field>
                <Field label="Soft skills" htmlFor="soft" className={hl('soft_skills')}>
                  <TagInput id="soft" value={form.soft_skills} onChange={(v) => set('soft_skills', v)} placeholder="Коммуникация…" />
                </Field>
              </div>
            </div>
          </section>

          <section className="form-section">
            <h2 className="form-section__title">Условия</h2>
            <div className="form-grid">
              <Field label="Опыт, лет" htmlFor="exp" className={hl('experience_years')}>
                <input id="exp" type="number" min={0} max={50} step={0.5} className="input" value={form.experience_years} onChange={(e) => set('experience_years', e.target.value)} />
              </Field>
              <Field label="Формат работы" htmlFor="wf" className={hl('work_format')}>
                <select id="wf" className="select" value={form.work_format} onChange={(e) => set('work_format', e.target.value as WorkFormat | '')}>
                  <option value="">Любой</option>
                  {(catalog?.work_formats ?? [
                    { code: 'office', title: 'Офис' },
                    { code: 'hybrid', title: 'Гибрид' },
                    { code: 'remote', title: 'Удалённо' },
                  ]).map((w) => <option key={w.code} value={w.code}>{w.title}</option>)}
                </select>
              </Field>
              <Field label="Зарплата от, ₽" htmlFor="sf" className={hl('salary_from')} error={salaryError}>
                <input id="sf" type="number" min={0} step={5000} className="input" value={form.salary_from} onChange={(e) => set('salary_from', e.target.value)} />
              </Field>
              <Field label="Зарплата до, ₽" htmlFor="st" className={hl('salary_to')}>
                <input id="st" type="number" min={0} step={5000} className="input" value={form.salary_to} onChange={(e) => set('salary_to', e.target.value)} />
              </Field>
            </div>
          </section>

          <section className="form-section">
            <h2 className="form-section__title">Контакты</h2>
            <p className="muted small" style={{ marginBottom: 12 }}>Работодатель увидит контакты только после того, как вы примете его приглашение.</p>
            <div className="form-grid">
              <Field label="Email для связи" htmlFor="ce" className={hl('contact_email')}>
                <input id="ce" type="email" className="input" value={form.contact_email} onChange={(e) => set('contact_email', e.target.value)} />
              </Field>
              <Field label="Телефон" htmlFor="ph" className={hl('phone')}>
                <input id="ph" type="tel" className="input" value={form.phone} onChange={(e) => set('phone', e.target.value)} placeholder="+7…" />
              </Field>
              <Field label="Telegram" htmlFor="tg" className={hl('telegram')}>
                <input id="tg" className="input" value={form.telegram} onChange={(e) => set('telegram', e.target.value)} placeholder="@username" />
              </Field>
            </div>
          </section>
        </div>

        <div className="sticky-actions">
          <span className="muted small">{dirty ? 'Есть несохранённые изменения' : 'Все изменения сохранены'}</span>
          <Button type="submit" icon={<Save size={16} />} loading={saving} disabled={!dirty || !!salaryError}>
            Сохранить
          </Button>
        </div>
      </form>

      <aside className="profile-side">
        <div className="card card--glow">
          <div className="card__title">Заполненность</div>
          <div className="meter">
            <div className="row between">
              <span className="display" style={{ fontSize: 34 }}>{profile.completeness}%</span>
              <span className="muted small">{profile.completeness >= 80 ? 'отлично' : profile.completeness >= 50 ? 'неплохо' : 'нужно дополнить'}</span>
            </div>
            <div className="meter__track"><div className="meter__fill" style={{ width: `${profile.completeness}%` }} /></div>
          </div>
        </div>
        <div className="card">
          <div className="card__title">Категория</div>
          <CategoryBadge title={profile.category_title} grade={profile.grade} />
          <p className="muted small mt">Категория присваивается по итогам теста и меняется только через пересдачу.</p>
        </div>
        <div className="card">
          <div className="card__title"><FileText size={18} /> PDF-профиль</div>
          <p className="muted small">Стандартизированная карточка с категорией, стеком и результатами — удобно прикладывать к письмам.</p>
          <Button variant="secondary" block className="mt" icon={<Download size={16} />} loading={pdfBusy} onClick={downloadPdf}>
            Скачать PDF-профиль
          </Button>
        </div>
      </aside>
    </div>
  )
}
