import { useMemo, useState } from 'react'
import { Building2, Check, ExternalLink, X, MessageSquare } from 'lucide-react'
import { api } from '../../api/client'
import type { Invitation } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useToast } from '../../contexts/ToastContext'
import { useCatalog } from '../../contexts/CatalogContext'
import PageHeader from '../../components/ui/PageHeader'
import Tabs from '../../components/ui/Tabs'
import Modal from '../../components/ui/Modal'
import Field from '../../components/ui/Field'
import { Button, LinkButton } from '../../components/ui/Button'
import { StatusChip } from '../../components/ui/Badges'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { errorMessage, formatDate, formatSalary } from '../../lib/format'

type Filter = 'all' | 'new' | 'accepted' | 'declined'

export default function CandidateInvitationsPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getCandidateInvitations())
  const [filter, setFilter] = useState<Filter>('all')
  const [openId, setOpenId] = useState<string | null>(null)
  const toast = useToast()

  const list = useMemo(() => data ?? [], [data])
  const shown = list.filter((i) =>
    filter === 'all' ? true : filter === 'new' ? i.status === 'sent' || i.status === 'viewed' : i.status === filter,
  )
  const current = list.find((i) => i.id === openId) ?? null

  const replace = (inv: Invitation) => setData((d) => (d ? d.map((x) => (x.id === inv.id ? { ...x, ...inv } : x)) : d))

  // при открытии отмечаем новое приглашение просмотренным
  const open = (inv: Invitation) => {
    setOpenId(inv.id)
    if (inv.status === 'sent') {
      api.viewInvitation(inv.id)
        .then((res) => replace(res && res.id ? res : { ...inv, status: 'viewed' }))
        .catch(() => undefined)
    }
  }

  return (
    <>
      <PageHeader title="Приглашения" subtitle="Работодатели пишут первыми и сразу называют зарплату. Контакты откроются им только после вашего согласия." />
      <div className="toolbar">
        <Tabs
          value={filter}
          onChange={setFilter}
          tabs={[
            { key: 'all', label: 'Все', count: list.length },
            { key: 'new', label: 'Новые', count: list.filter((i) => i.status === 'sent' || i.status === 'viewed').length },
            { key: 'accepted', label: 'Принятые' },
            { key: 'declined', label: 'Отклонённые' },
          ]}
        />
      </div>
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonList count={3} />}
      {data && shown.length === 0 && (
        <EmptyState
          glyph="@"
          title={list.length ? 'В этом разделе пусто' : 'Приглашений пока нет'}
          text={list.length ? 'Попробуйте другой фильтр.' : 'Подтвердите категорию тестом и дайте согласие на показ профиля — работодатели увидят вас в подборках.'}
          action={!list.length && <LinkButton to="/app/assessment">К тестированию</LinkButton>}
        />
      )}
      <div className="invite-list">
        {shown.map((inv, i) => (
          <Reveal key={inv.id} delay={i * 40}>
            <button className={`invite card card--hover ${inv.status === 'sent' ? 'is-new' : ''}`} onClick={() => open(inv)}>
              <div className="invite__company">
                <span className="invite__logo"><Building2 size={18} /></span>
                <div className="grow">
                  <strong>{inv.company.name}</strong>
                  <span className="muted small">{formatDate(inv.created_at)}</span>
                </div>
                <StatusChip status={inv.status} />
              </div>
              <h3 className="invite__title">{inv.title}</h3>
              <div className="invite__salary">{formatSalary(inv.salary_from, inv.salary_to)}</div>
              <p className="invite__msg muted small clamp-2">{inv.message}</p>
            </button>
          </Reveal>
        ))}
      </div>

      {current && (
        <InvitationModal
          inv={current}
          onClose={() => setOpenId(null)}
          onChanged={(inv) => {
            replace(inv)
            toast.success(inv.status === 'accepted' ? 'Приглашение принято — работодатель увидит ваши контакты' : 'Приглашение отклонено')
          }}
        />
      )}
    </>
  )
}

function InvitationModal({ inv, onClose, onChanged }: { inv: Invitation; onClose: () => void; onChanged: (i: Invitation) => void }) {
  const toast = useToast()
  const { industryTitle } = useCatalog()
  const [busy, setBusy] = useState<'accept' | 'decline' | null>(null)
  const [declining, setDeclining] = useState(false)
  const [reason, setReason] = useState('')
  const final = inv.status === 'accepted' || inv.status === 'declined'

  const act = async (kind: 'accept' | 'decline') => {
    setBusy(kind)
    try {
      const res = kind === 'accept' ? await api.acceptInvitation(inv.id) : await api.declineInvitation(inv.id, reason.trim() || undefined)
      onChanged(res && res.id ? res : { ...inv, status: kind === 'accept' ? 'accepted' : 'declined' })
      setDeclining(false)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy(null)
    }
  }

  return (
    <Modal
      open
      wide
      title={inv.title}
      onClose={onClose}
      footer={
        final ? (
          <Button variant="ghost" onClick={onClose}>Закрыть</Button>
        ) : declining ? (
          <>
            <Button variant="ghost" onClick={() => setDeclining(false)}>Назад</Button>
            <Button variant="danger" loading={busy === 'decline'} onClick={() => act('decline')}>Отклонить приглашение</Button>
          </>
        ) : (
          <>
            <Button variant="danger" icon={<X size={16} />} onClick={() => setDeclining(true)}>Отклонить</Button>
            <Button icon={<Check size={16} />} loading={busy === 'accept'} onClick={() => act('accept')}>Принять и открыть контакты</Button>
          </>
        )
      }
    >
      <div className="stack">
        <div className="row between wrap gap-sm">
          <div className="row gap-sm">
            <span className="invite__logo"><Building2 size={18} /></span>
            <div>
              <strong>{inv.company.name}</strong>
              <div className="muted small">
                {inv.company.industry ? industryTitle(inv.company.industry) : 'Отрасль не указана'}
                {inv.company.website && (
                  <>
                    {' · '}
                    <a href={inv.company.website} target="_blank" rel="noreferrer noopener">
                      сайт <ExternalLink size={11} style={{ display: 'inline' }} />
                    </a>
                  </>
                )}
              </div>
            </div>
          </div>
          <StatusChip status={inv.status} />
        </div>
        <div className="salary-hero">
          <span className="kicker">зарплата</span>
          <span className="salary-hero__value">{formatSalary(inv.salary_from, inv.salary_to)}</span>
        </div>
        <div>
          <div className="field__label"><MessageSquare size={14} style={{ display: 'inline', marginRight: 6 }} />Сообщение</div>
          <p className="prewrap">{inv.message}</p>
        </div>
        {inv.status === 'accepted' && (
          <div className="alert alert--success">
            <Check size={16} />
            <div>
              <strong>Вы приняли приглашение.</strong> Связь с работодателем: <span className="mono">{inv.contact}</span>
            </div>
          </div>
        )}
        {!final && <p className="muted small">Связь после принятия: работодатель увидит ваши контакты и напишет по указанному способу.</p>}
        {declining && (
          <Field label="Причина отказа (необязательно)" htmlFor="reason" hint="Работодатель увидит причину — это поможет точнее подбирать предложения">
            <textarea id="reason" className="textarea" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Например: рассматриваю только удалённый формат" />
          </Field>
        )}
      </div>
    </Modal>
  )
}
