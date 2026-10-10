import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Lock, Mail, Phone, Send, MessageCircle, Gauge, Star, Briefcase } from 'lucide-react'
import { api } from '../../api/client'
import type { Vacancy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { Button } from '../../components/ui/Button'
import { CategoryBadge, StatusChip, Tags } from '../../components/ui/Badges'
import { ErrorState } from '../../components/ui/States'
import { SkeletonCard } from '../../components/ui/Skeleton'
import ScoreRing from '../../components/ui/ScoreRing'
import Reveal from '../../components/ui/Reveal'
import FspPanel from '../../components/settings/FspPanel'
import InviteModal from '../../components/employer/InviteModal'
import { experienceLabel, formatSalary, workFormatLabel } from '../../lib/format'

export default function CandidateDetailPage() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const { specTitle } = useCatalog()
  const { data: c, error, loading, reload, setData } = useAsync(() => api.getCandidate(id), [id])
  const [inviting, setInviting] = useState(false)
  const [vacancies, setVacancies] = useState<Vacancy[]>([])

  useEffect(() => {
    api.getEmployerVacancies().then(setVacancies).catch(() => undefined)
  }, [])

  const invited = !!c?.invitation_status && c.invitation_status !== 'declined'

  return (
    <>
      <button className="back-link" onClick={() => navigate(-1)}><ArrowLeft size={14} /> Назад</button>
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !c && <SkeletonCard lines={8} />}
      {c && (
        <div className="cand-detail">
          <Reveal className="card card--spin cand-detail__hero">
            <span className="avatar avatar--lg">{c.display_name.replace(/[^\p{L}\d]/gu, '').slice(0, 2).toUpperCase()}</span>
            <div className="grow stack-sm">
              <h1 className="page-head__title">{c.display_name}</h1>
              <p className="muted">{c.headline ?? specTitle(c.specialization)}</p>
              <div className="row wrap gap-sm">
                <CategoryBadge title={c.category_title} grade={c.grade} size="lg" />
                {c.invitation_status && <StatusChip status={c.invitation_status} />}
              </div>
            </div>
            <div className="cand-detail__cta">
              <Button size="lg" icon={<Send size={16} />} onClick={() => setInviting(true)} disabled={invited}>
                {invited ? 'Приглашение отправлено' : 'Пригласить'}
              </Button>
            </div>
          </Reveal>

          <div className="grid-2-1">
            <div className="stack-lg">
              <Reveal className="card">
                <div className="card__title">Навыки</div>
                <div className="stack">
                  <div><div className="field__label">Стек</div><Tags items={c.stack} /></div>
                  {c.roles.length > 0 && <div><div className="field__label">Роли</div><Tags items={c.roles} /></div>}
                  {c.soft_skills.length > 0 && <div><div className="field__label">Soft skills</div><Tags items={c.soft_skills} /></div>}
                </div>
                <dl className="kv mt-lg">
                  <dt>Специализация</dt><dd>{specTitle(c.specialization)}</dd>
                  <dt>Опыт</dt><dd>{experienceLabel(c.experience_years)}</dd>
                  <dt>Формат</dt><dd>{workFormatLabel(c.work_format)}</dd>
                  <dt>Город</dt><dd>{c.city ?? <span className="muted">скрыт или не указан</span>}</dd>
                  <dt>Ожидания</dt><dd>{c.salary_from || c.salary_to ? <span className="text-success">{formatSalary(c.salary_from, c.salary_to)}</span> : <span className="muted">скрыты или не указаны</span>}</dd>
                </dl>
              </Reveal>
              <Reveal className="card card--glow">
                <div className="card__title">Достижения ФСП</div>
                {c.fsp ? <FspPanel fsp={c.fsp} /> : <p className="muted small">Кандидат не привязал ФСП ID или скрыл достижения.</p>}
              </Reveal>
            </div>

            <div className="stack-lg">
              <Reveal className="card score-card" delay={80}>
                <div className="card__title"><Gauge size={16} /> Результат теста</div>
                {c.test_score !== null ? <ScoreRing value={c.test_score} size={150} /> : <p className="muted">нет данных</p>}
                {c.rating !== null && <p className="row gap-sm mt"><Star size={16} className="text-blue" /> Рейтинг в категории: <strong>{Math.round(c.rating)}</strong>/100</p>}
              </Reveal>
              <Reveal className="card" delay={140}>
                <div className="card__title"><Briefcase size={16} /> Контакты</div>
                {c.contacts_unlocked && c.contacts ? (
                  <ul className="contacts">
                    {c.contacts.email && <li><Mail size={14} /> <a href={`mailto:${c.contacts.email}`}>{c.contacts.email}</a></li>}
                    {c.contacts.phone && <li><Phone size={14} /> <a href={`tel:${c.contacts.phone}`}>{c.contacts.phone}</a></li>}
                    {c.contacts.telegram && <li><MessageCircle size={14} /> {c.contacts.telegram}</li>}
                  </ul>
                ) : (
                  <div className="masked">
                    <ul className="contacts contacts--masked" aria-hidden>
                      <li><Mail size={14} /> ••••••@••••.ru</li>
                      <li><Phone size={14} /> +7 ••• •••-••-••</li>
                      <li><MessageCircle size={14} /> @••••••</li>
                    </ul>
                    <div className="masked__overlay">
                      <Lock size={18} />
                      <span>Откроются, когда кандидат примет приглашение</span>
                    </div>
                  </div>
                )}
              </Reveal>
            </div>
          </div>
        </div>
      )}
      {inviting && c && (
        <InviteModal
          candidate={c}
          vacancies={vacancies}
          onClose={() => setInviting(false)}
          onSent={(inv) => setData((d) => (d ? { ...d, invitation_status: inv.status } : d))}
        />
      )}
    </>
  )
}
