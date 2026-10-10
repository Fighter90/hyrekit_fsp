import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Shield, Trophy, Link2, Unlink, FileCheck2 } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateProfile, CandidateSettingsUpdate, FspSummary, Privacy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Toggle from '../../components/ui/Toggle'
import { Button } from '../../components/ui/Button'
import { ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import SecuritySection from '../../components/settings/SecuritySection'
import FspPanel from '../../components/settings/FspPanel'
import { errorMessage, formatDateTime } from '../../lib/format'

const PRIVACY_LABELS: { key: keyof Privacy; label: string; hint: string }[] = [
  { key: 'show_full_name', label: 'Показывать имя', hint: 'Иначе работодатель видит «Кандидат #A1B2»' },
  { key: 'show_city', label: 'Показывать город', hint: 'Полезно для офисных и гибридных вакансий' },
  { key: 'show_salary', label: 'Показывать зарплатные ожидания', hint: 'Помогает работодателю сразу предложить подходящую вилку' },
  { key: 'show_fsp', label: 'Показывать достижения ФСП', hint: 'Достижения повышают рейтинг и видны в карточке' },
]

export default function CandidateSettingsPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getCandidateProfile())
  return (
    <>
      <PageHeader title="Настройки" subtitle="Приватность, согласие на обработку данных, ФСП ID и безопасность." />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonCard lines={6} />}
      {data && (
        <div className="stack-lg settings">
          <ConsentSection profile={data} onChange={setData} />
          <PrivacySection profile={data} onChange={setData} />
          <FspSection profile={data} onChange={setData} />
          <SecuritySection />
        </div>
      )}
    </>
  )
}

interface SectionProps {
  profile: CandidateProfile
  onChange: (p: CandidateProfile) => void
}

function useSettingsSaver(onChange: (p: CandidateProfile) => void) {
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const save = async (patch: CandidateSettingsUpdate, okText: string) => {
    setBusy(true)
    try {
      const p = await api.updateCandidateSettings(patch)
      onChange(p)
      toast.success(okText)
      return p
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось сохранить настройки'))
      return null
    } finally {
      setBusy(false)
    }
  }
  return { save, busy }
}

function ConsentSection({ profile, onChange }: SectionProps) {
  const { save, busy } = useSettingsSaver(onChange)
  const given = !!profile.consent_given_at
  return (
    <section className={`card ${given ? '' : 'card--spin'}`}>
      <div className="card__title"><FileCheck2 size={18} /> Согласие на обработку персональных данных</div>
      <label className="checkbox">
        <input type="checkbox" checked={given} disabled={busy} onChange={(e) => void save({ consent: e.target.checked }, e.target.checked ? 'Согласие дано — профиль может быть показан работодателям' : 'Согласие отозвано — профиль скрыт')} />
        <span>
          Даю согласие на обработку моих персональных данных в соответствии с Федеральным законом № 152-ФЗ «О персональных данных»
          для подбора вакансий и показа обезличенной карточки работодателям платформы HyreKit на условиях{' '}
          <Link to="/privacy#consent" target="_blank">политики конфиденциальности</Link>.
        </span>
      </label>
      <p className="muted small mt">
        {given ? `Согласие дано ${formatDateTime(profile.consent_given_at)}. Его можно отозвать в любой момент — профиль сразу скроется.` : 'Без согласия профиль не показывается работодателям, даже при наличии категории.'}
      </p>
      <div className={`visibility mt ${profile.is_visible ? 'is-on' : ''}`}>
        {profile.is_visible ? 'Профиль виден работодателям' : 'Профиль скрыт от работодателей'}
      </div>
    </section>
  )
}

function PrivacySection({ profile, onChange }: SectionProps) {
  const { save, busy } = useSettingsSaver(onChange)
  return (
    <section className="card">
      <div className="card__title"><Shield size={18} /> Приватность</div>
      <p className="muted small">Контакты (email, телефон, Telegram) всегда скрыты до принятия приглашения.</p>
      <div className="toggles">
        {PRIVACY_LABELS.map((p) => (
          <Toggle
            key={p.key}
            label={p.label}
            hint={p.hint}
            checked={profile.privacy[p.key]}
            disabled={busy}
            onChange={(v) => void save({ privacy: { [p.key]: v } }, 'Настройки приватности сохранены')}
          />
        ))}
      </div>
    </section>
  )
}

function FspSection({ profile, onChange }: SectionProps) {
  const { save, busy } = useSettingsSaver(onChange)
  const toast = useToast()
  const [fspId, setFspId] = useState('')
  const [summary, setSummary] = useState<FspSummary | null>(profile.fsp)
  const [loadingFsp, setLoadingFsp] = useState(false)

  const refresh = async () => {
    setLoadingFsp(true)
    try {
      setSummary(await api.getFsp())
    } catch (e) {
      toast.error(errorMessage(e, 'Не удалось получить достижения'))
    } finally {
      setLoadingFsp(false)
    }
  }

  const link = async () => {
    const id = fspId.trim()
    if (!id) return
    const p = await save({ fsp_id: id }, 'ФСП ID привязан')
    if (p) {
      setFspId('')
      if (p.fsp) setSummary(p.fsp)
      else void refresh()
    }
  }

  const unlink = async () => {
    const p = await save({ fsp_id: null }, 'ФСП ID отвязан')
    if (p) setSummary(null)
  }

  return (
    <section className="card card--glow">
      <div className="card__title"><Trophy size={18} /> Достижения ФСП</div>
      {profile.fsp_id ? (
        <div className="stack">
          {summary ? <FspPanel fsp={summary} /> : (
            <Button variant="secondary" loading={loadingFsp} onClick={refresh}>Загрузить достижения</Button>
          )}
          <div className="row end gap-sm wrap">
            <Button variant="ghost" size="sm" loading={loadingFsp} onClick={refresh}>Обновить</Button>
            <Button variant="danger" size="sm" icon={<Unlink size={14} />} loading={busy} onClick={unlink}>Отвязать ФСП ID</Button>
          </div>
        </div>
      ) : (
        <div className="stack">
          <p className="muted small">
            Укажите идентификатор спортсмена Федерации спортивного программирования — участие и призовые места подтянутся
            автоматически и повысят рейтинг. Нет истории? Ничего страшного — рейтинг считается по тесту.
          </p>
          <div className="row gap-sm wrap">
            <input className="input grow" style={{ maxWidth: 320 }} placeholder="ФСП ID, например FSP-123456" value={fspId} onChange={(e) => setFspId(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && link()} aria-label="ФСП ID" />
            <Button icon={<Link2 size={16} />} loading={busy} disabled={!fspId.trim()} onClick={link}>Привязать</Button>
          </div>
        </div>
      )}
    </section>
  )
}
