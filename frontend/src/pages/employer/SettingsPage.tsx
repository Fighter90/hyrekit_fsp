import { Link } from 'react-router-dom'
import { Building2 } from 'lucide-react'
import PageHeader from '../../components/ui/PageHeader'
import SecuritySection from '../../components/settings/SecuritySection'

export default function EmployerSettingsPage() {
  return (
    <>
      <PageHeader title="Настройки" subtitle="Аккаунт и безопасность. Данные компании — в разделе «Компания»." />
      <div className="stack-lg settings">
        <SecuritySection />
        <section className="card row gap wrap">
          <Building2 size={20} className="text-blue" />
          <p className="grow">Название, описание и контакты компании видят кандидаты в приглашениях.</p>
          <Link to="/app/company">Профиль компании →</Link>
        </section>
      </div>
    </>
  )
}
