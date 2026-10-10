import { useState } from 'react'
import { Link } from 'react-router-dom'
import { Plus, Pencil, Trash2, Sparkles, Eye, EyeOff, Users } from 'lucide-react'
import { api } from '../../api/client'
import type { Vacancy } from '../../api/types'
import { useAsync } from '../../hooks/useAsync'
import { useCatalog } from '../../contexts/CatalogContext'
import { useToast } from '../../contexts/ToastContext'
import PageHeader from '../../components/ui/PageHeader'
import Modal from '../../components/ui/Modal'
import { Button, LinkButton } from '../../components/ui/Button'
import { GradePill, Tags } from '../../components/ui/Badges'
import { EmptyState, ErrorState } from '../../components/ui/States'
import { SkeletonList } from '../../components/ui/Skeleton'
import Reveal from '../../components/ui/Reveal'
import { errorMessage, formatDate, formatSalary, workFormatLabel } from '../../lib/format'

export default function EmployerVacanciesPage() {
  const { data, error, loading, reload, setData } = useAsync(() => api.getEmployerVacancies())
  const { specTitle } = useCatalog()
  const toast = useToast()
  const [toDelete, setToDelete] = useState<Vacancy | null>(null)
  const [busy, setBusy] = useState(false)

  const remove = async () => {
    if (!toDelete) return
    setBusy(true)
    try {
      await api.deleteVacancy(toDelete.id)
      setData((d) => d?.filter((v) => v.id !== toDelete.id) ?? d)
      toast.success('Потребность удалена')
      setToDelete(null)
    } catch (e) {
      toast.error(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        
        title="Вакансии"
        subtitle="Каждая потребность — это фильтр подборки: специализация, диапазон грейдов, стек и зарплатная вилка."
        actions={<LinkButton to="/app/vacancies/new" icon={<Plus size={16} />}>Новая потребность</LinkButton>}
      />
      {error && <ErrorState message={error} onRetry={reload} />}
      {loading && !data && <SkeletonList count={3} />}
      {data && data.length === 0 && (
        <EmptyState
          glyph="+"
          title="Потребностей пока нет"
          text="Создайте первую — и получите ранжированную подборку кандидатов с объяснением."
          action={<LinkButton to="/app/vacancies/new" icon={<Plus size={16} />}>Создать потребность</LinkButton>}
        />
      )}
      <div className="stack">
        {data?.map((v, i) => (
          <Reveal key={v.id} delay={i * 40}>
            <article className="card card--hover emp-vacancy">
              <div className="emp-vacancy__main">
                <div className="row gap-sm wrap">
                  <span className={`pub ${v.is_published ? 'is-on' : ''}`}>
                    {v.is_published ? <Eye size={12} /> : <EyeOff size={12} />} {v.is_published ? 'опубликована' : 'черновик'}
                  </span>
                  <span className="muted small">{specTitle(v.specialization)} · {workFormatLabel(v.work_format)}{v.city && ` · ${v.city}`}</span>
                </div>
                <h3 className="vacancy__title"><Link to={`/app/vacancies/${v.id}/matches`}>{v.title}</Link></h3>
                <div className="row gap-sm wrap">
                  <span className="vacancy__salary">{formatSalary(v.salary_from, v.salary_to)}</span>
                  <span className="grade-range"><GradePill grade={v.grade_min} />–<GradePill grade={v.grade_max} /></span>
                </div>
                <Tags items={v.stack} limit={10} />
                <span className="tiny muted"><Users size={12} style={{ display: 'inline' }} /> откликов: {v.applications_count} · обновлено {formatDate(v.updated_at)}</span>
              </div>
              <div className="emp-vacancy__actions">
                <LinkButton to={`/app/vacancies/${v.id}/matches`} icon={<Sparkles size={16} />}>Подборка</LinkButton>
                <LinkButton to={`/app/vacancies/${v.id}/edit`} variant="ghost" icon={<Pencil size={16} />}>Изменить</LinkButton>
                <Button variant="danger" icon={<Trash2 size={16} />} onClick={() => setToDelete(v)} aria-label="Удалить" />
              </div>
            </article>
          </Reveal>
        ))}
      </div>
      <Modal
        open={!!toDelete}
        title="Удалить потребность?"
        onClose={() => setToDelete(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setToDelete(null)}>Отмена</Button>
            <Button variant="danger" loading={busy} onClick={remove}>Удалить</Button>
          </>
        }
      >
        <p>«{toDelete?.title}» будет удалена вместе с подборкой. Отправленные приглашения сохранятся.</p>
      </Modal>
    </>
  )
}
