import { useState } from 'react'
import { Code2, Trophy, Target, ShieldCheck } from 'lucide-react'
import { api } from '../../api/client'
import { useAsync } from '../../hooks/useAsync'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Stat from '../../components/ui/Stat'
import Toggle from '../../components/ui/Toggle'
import { ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import { RatingChart, RoundCard } from '../../components/arena/parts'
import { errorMessage } from '../../lib/format'

/** Arena кандидата: рейтинг, раунды, приватность. */
export default function CandidateArenaPage() {
  const rounds = useAsync(() => api.getArenaRounds())
  const me = useAsync(() => api.getArenaMe())
  const toast = useToast()
  const [saving, setSaving] = useState(false)

  const toggle = async (v: boolean) => {
    setSaving(true)
    try {
      const r = await api.setArenaSettings(v)
      me.setData((d) => (d ? { ...d, show_arena: r.show_arena, display_name: r.display_name } : d))
      toast.success(v ? 'Работодатели увидят ваше имя и решения' : 'Вы участвуете анонимно')
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setSaving(false)
    }
  }

  const rt = me.data?.rating
  return (
    <>
      <PageHeader
        title="Code Arena"
        subtitle="Решайте задачи в браузере: код проверяется на скрытых тестах, после проверки — разбор решения. Рейтинг Arena видят работодатели, на грейд он не влияет."
      />
      <div className="grid-4">
        <Stat label="Рейтинг Arena" value={rt ? rt.rating : null} icon={<Trophy size={16} />} hint={rt ? (rt.provisional ? `предварительный, ±${rt.rd}` : `±${rt.rd}`) : 'после первого раунда'} />
        <Stat label="Раундов" value={rt?.rounds ?? 0} icon={<Code2 size={16} />} />
        <Stat label="Решено задач" value={rt?.solved ?? 0} icon={<Target size={16} />} />
        <Stat label="Место среди специализации" value={me.data?.top_percent ?? null} suffix="%" icon={<ShieldCheck size={16} />} hint={me.data?.top_percent ? `топ-${me.data.top_percent}%` : '—'} />
      </div>

      {rt && rt.history.length > 0 && (
        <section className="card mt">
          <div className="card__title">История рейтинга</div>
          <RatingChart history={rt.history} />
        </section>
      )}

      <section className="card mt">
        <Toggle
          checked={!!me.data?.show_arena}
          disabled={saving || !me.data}
          onChange={toggle}
          label="Показывать имя и решения в Arena"
          hint={me.data ? `Сейчас в таблицах вы — «${me.data.display_name}». Контакты раскрываются только после принятия приглашения.` : undefined}
        />
      </section>

      <h2 className="section-title mt">Раунды</h2>
      {rounds.error && <ErrorState message={rounds.error} onRetry={rounds.reload} />}
      {rounds.loading && !rounds.data && <SkeletonList count={3} />}
      <div className="arena-rounds">
        {rounds.data?.map((r) => <RoundCard key={r.id} round={r} />)}
      </div>
    </>
  )
}
