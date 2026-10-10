import { useState, type FormEvent } from 'react'
import { Save, Building2 } from 'lucide-react'
import { api, ApiError } from '../../api/client'
import type { Company, CompanyUpdate } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Field from '../../components/ui/Field'
import { Button } from '../../components/ui/Button'
import { ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import { errorMessage } from '../../lib/format'

type FormState = Record<keyof CompanyUpdate, string>

const FIELDS: (keyof CompanyUpdate)[] = ['name', 'industry', 'description', 'website', 'contact_email', 'contact_phone', 'city']

function toForm(c: Company | null): FormState {
  const out = {} as FormState
  for (const k of FIELDS) out[k] = (c?.[k] as string | null | undefined) ?? ''
  return out
}

export default function CompanyPage() {
  // 404 — компания ещё не заполнена: показываем пустую форму
  const { data, error, loading, reload, setData } = useAsync<Company | null>(() =>
    api.getCompany().catch((e: unknown) => {
      if (e instanceof ApiError && e.status === 404) return null
      throw e
    }),
  )
  return (
    <>
      <PageHeader title="Компания" subtitle="Эти данные кандидат видит в приглашении — расскажите, почему к вам стоит прийти." />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonCard lines={6} />}
      {!loading && !error && <CompanyForm company={data} onSaved={setData} />}
    </>
  )
}

function CompanyForm({ company, onSaved }: { company: Company | null; onSaved: (c: Company) => void }) {
  const { catalog } = useCatalog()
  const toast = useToast()
  const [form, setForm] = useState<FormState>(() => toForm(company))
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const set = (k: keyof CompanyUpdate, v: string) => setForm((f) => ({ ...f, [k]: v }))

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!form.name.trim()) {
      setErr('Укажите название компании')
      return
    }
    setErr(null)
    setBusy(true)
    try {
      const payload: CompanyUpdate = {}
      for (const k of FIELDS) {
        const v = form[k].trim()
        ;(payload as Record<string, string | null>)[k] = v === '' ? null : v
      }
      payload.name = form.name.trim()
      const c = await api.updateCompany(payload)
      onSaved(c)
      toast.success('Профиль компании сохранён')
    } catch (e2) {
      toast.error(errorMessage(e2, 'Не удалось сохранить'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="profile-layout" onSubmit={submit}>
      <div className="card">
        <div className="form-grid">
          <Field label="Название" htmlFor="c-name" required error={err}>
            <input id="c-name" className="input" value={form.name} onChange={(e) => set('name', e.target.value)} />
          </Field>
          <Field label="Отрасль" htmlFor="c-ind">
            <select id="c-ind" className="select" value={form.industry} onChange={(e) => set('industry', e.target.value)}>
              <option value="">Не выбрана</option>
              {catalog?.industries.map((i) => <option key={i.code} value={i.code}>{i.title}</option>)}
            </select>
          </Field>
          <Field label="О компании" htmlFor="c-desc" className="span-2" hint="Продукт, команда, технологии, чем гордитесь">
            <textarea id="c-desc" className="textarea" rows={6} value={form.description} onChange={(e) => set('description', e.target.value)} />
          </Field>
          <Field label="Сайт" htmlFor="c-web">
            <input id="c-web" type="url" className="input" placeholder="https://" value={form.website} onChange={(e) => set('website', e.target.value)} />
          </Field>
          <Field label="Город" htmlFor="c-city">
            <input id="c-city" className="input" value={form.city} onChange={(e) => set('city', e.target.value)} />
          </Field>
          <Field label="Email для связи" htmlFor="c-mail">
            <input id="c-mail" type="email" className="input" value={form.contact_email} onChange={(e) => set('contact_email', e.target.value)} />
          </Field>
          <Field label="Телефон" htmlFor="c-phone">
            <input id="c-phone" type="tel" className="input" value={form.contact_phone} onChange={(e) => set('contact_phone', e.target.value)} />
          </Field>
        </div>
        <div className="row end mt-lg">
          <Button type="submit" icon={<Save size={16} />} loading={busy}>Сохранить</Button>
        </div>
      </div>
      <aside className="profile-side">
        <div className="card card--glow company-preview">
          <div className="kicker">так видит кандидат</div>
          <div className="row gap-sm mt">
            <span className="invite__logo"><Building2 size={18} /></span>
            <div>
              <strong>{form.name || 'Название компании'}</strong>
              <div className="muted small">{catalog?.industries.find((i) => i.code === form.industry)?.title ?? 'Отрасль'}{form.city && ` · ${form.city}`}</div>
            </div>
          </div>
          <p className="muted small mt clamp-3">{form.description || 'Описание компании появится здесь.'}</p>
        </div>
      </aside>
    </form>
  )
}
