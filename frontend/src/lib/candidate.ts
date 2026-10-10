import type { CandidateProfile, Invitation, InvitationStatus } from '../api/types'
import type { Step } from '../components/ui/Stepper'

/** Шаги воронки кандидата вычисляются из профиля и приглашений. */
export function candidateSteps(p: CandidateProfile, invitations: Invitation[]): Step[] {
  return [
    { label: 'Профиль', done: p.completeness >= 50, hint: `${p.completeness}%` },
    { label: 'Опрос', done: !!p.specialization && !!p.declared_grade },
    { label: 'Тест', done: p.test_score !== null },
    { label: 'Категория', done: !!p.category },
    { label: 'Приглашения', done: invitations.length > 0, hint: invitations.length ? String(invitations.length) : undefined },
  ]
}


/**
 * Ждёт ли кандидат ответа на приглашение компании. Только в этом случае новое приглашение
 * отправить нельзя — бэкенд отвечает 409; после принятия или отказа можно пригласить снова.
 */
export function invitationPending(status: InvitationStatus | null | undefined): boolean {
  return status === 'sent' || status === 'viewed'
}
