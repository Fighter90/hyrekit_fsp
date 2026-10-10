import { useEffect, useState } from 'react'
import { Send } from 'lucide-react'
import { api } from '../../api/client'
import type { CandidateCard, Invitation, Vacancy } from '../../api/types'
import { useToast } from '../../contexts/ToastContext'
import Modal from '../ui/Modal'
import Field from '../ui/Field'
import { Button } from '../ui/Button'
import { CategoryBadge } from '../ui/Badges'
import { errorMessage, formatSalary } from '../../lib/format'

interface Props {
  candidate: CandidateCard
  vacancy?: Vacancy | null
  vacancies?: Vacancy[]
  onClose: () => void
  onSent: (inv: Invitation) => void
}

/** Приглашение кандидата: зарплатная вилка и способ связи обязательны. */
export default function InviteModal({ candidate, vacancy, vacancies = [], onClose, onSent }: Props) {
  const toast = useToast()
  const [vacancyId, setVacancyId] = useState<string>(vacancy?.id ?? '')
  const selected = vacancy ?? vacancies.find((v) => v.id === vacancyId) ?? null
  const [title, setTitle] = useState(selected?.title ?? candidate.headline ?? '')
  const [message, setMessage] = useState('')
  const [from, setFrom] = useState(selected ? String(selected.salary_from) : candidate.salary_from ? String(candidate.salary_from) : '')
  const [to, setTo] = useState(selected ? String(selected.salary_to) : candidate.salary_to ? String(candidate.salary_to) : '')
  const [contact, setContact] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [busy, setBusy] = useState(false)

  // способ связи по умолчанию — контакты компании
  useEffect(() => {
    api.getCompany()
      .then((c) => setContact((cur) => cur || c.contact_email || c.contact_phone || ''))
      .catch(() => undefined)
  }, [])

  // при выборе потребности подставляем её название и вилку
  const pickVacancy = (id: string) => {
    setVacancyId(id)
    const v = vacancies.find((x) => x.id === id)
    if (v) {
      setTitle(v.title)
      setFrom(String(v.salary_from))
      setTo(String(v.salary_to))
    }
  }

  const submit = async () => {
    const e: Record<string, string> = {}
    if (title.trim().length < 3) e.title = 'Укажите позицию'
    if (message.trim().length < 10) e.message = 'Напишите пару предложений — минимум 10 символов'
    const f = Number(from)
    const t = Number(to)
    if (!(f > 0)) e.from = 'Обязательно'
    if (!(t > 0)) e.to = 'Обязательно'
    else if (f > t) e.to = '«До» меньше «от»'
    if (!contact.trim()) e.contact = 'Как кандидату с вами связаться?'
    setErrors(e)
    if (Object.keys(e).length) return
    setBusy(true)
    try {
      const inv = await api.createInvitation({
        candidate_id: candidate.id,
        vacancy_id: vacancy?.id ?? (vacancyId || null),
        title: title.trim(),
        message: message.trim(),
        salary_from: f,
        salary_to: t,
        contact: contact.trim(),
      })
      toast.success(`Приглашение отправлено: ${candidate.display_name}`)
      onSent(inv)
      onClose()
    } catch (err) {
      toast.error(errorMessage(err, 'Не удалось отправить приглашение'))
    } finally {
      setBusy(false)
    }
  }

  const candSalary = candidate.salary_from || candidate.salary_to ? formatSalary(candidate.salary_from, candidate.salary_to) : null

  return (
    <Modal
      open
      wide
      title="Пригласить кандидата"
      onClose={onClose}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Отмена</Button>
          <Button icon={<Send size={16} />} loading={busy} onClick={submit}>Отправить приглашение</Button>
        </>
      }
    >
      <div className="stack">
        <div className="row between wrap gap-sm invite-target">
          <div>
            <strong>{candidate.display_name}</strong>
            <div className="muted small">{candidate.headline ?? 'Без заголовка'}</div>
          </div>
          <CategoryBadge title={candidate.category_title} grade={candidate.grade} />
        </div>
        {candSalary && <p className="muted small">Ожидания кандидата: <strong className="text-success">{candSalary}</strong></p>}

        {!vacancy && vacancies.length > 0 && (
          <Field label="Потребность" htmlFor="inv-vac" hint="Необязательно: подставит название и вилку">
            <select id="inv-vac" className="select" value={vacancyId} onChange={(e) => pickVacancy(e.target.value)}>
              <option value="">Без привязки к потребности</option>
              {vacancies.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
            </select>
          </Field>
        )}

        <Field label="Позиция" htmlFor="inv-title" required error={errors.title}>
          <input id="inv-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} />
        </Field>
        <div className="form-grid">
          <Field label="Зарплата от, ₽" htmlFor="inv-from" required error={errors.from}>
            <input id="inv-from" type="number" min={0} step={5000} className="input" value={from} onChange={(e) => setFrom(e.target.value)} />
          </Field>
          <Field label="Зарплата до, ₽" htmlFor="inv-to" required error={errors.to}>
            <input id="inv-to" type="number" min={0} step={5000} className="input" value={to} onChange={(e) => setTo(e.target.value)} />
          </Field>
        </div>
        <Field label="Сообщение" htmlFor="inv-msg" required error={errors.message} hint="Чем интересна задача, команда, следующий шаг">
          <textarea id="inv-msg" className="textarea" rows={5} value={message} onChange={(e) => setMessage(e.target.value)} />
        </Field>
        <Field label="Способ связи" htmlFor="inv-contact" required error={errors.contact} hint="Email, телефон или Telegram — кандидат увидит после принятия">
          <input id="inv-contact" className="input" value={contact} onChange={(e) => setContact(e.target.value)} />
        </Field>
      </div>
    </Modal>
  )
}
