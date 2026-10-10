import { lazy, Suspense, type ReactNode } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import PublicLayout from './components/layout/PublicLayout'
import CenteredLayout from './components/layout/CenteredLayout'
import { Spinner } from './components/ui/States'
import LandingPage from './pages/public/LandingPage'
import AuthPage from './pages/auth/AuthPage'
import type { Role } from './api/types'

// Кабинеты грузятся лениво — лендинг остаётся лёгким
const AppLayout = lazy(() => import('./components/layout/AppLayout'))
const EmailVerifyPage = lazy(() => import('./pages/auth/EmailVerifyPage'))
const PrivacyPage = lazy(() => import('./pages/public/PrivacyPage'))
const TermsPage = lazy(() => import('./pages/public/TermsPage'))
const NotFoundPage = lazy(() => import('./pages/public/NotFoundPage'))

const CandDashboard = lazy(() => import('./pages/candidate/DashboardPage'))
const CandProfile = lazy(() => import('./pages/candidate/ProfilePage'))
const CandAssessment = lazy(() => import('./pages/candidate/AssessmentPage'))
const CandInvitations = lazy(() => import('./pages/candidate/InvitationsPage'))
const CandVacancies = lazy(() => import('./pages/candidate/VacanciesPage'))
const CandChallenges = lazy(() => import('./pages/candidate/ChallengesPage'))
const CandSettings = lazy(() => import('./pages/candidate/SettingsPage'))

const EmpDashboard = lazy(() => import('./pages/employer/DashboardPage'))
const EmpCompany = lazy(() => import('./pages/employer/CompanyPage'))
const EmpVacancies = lazy(() => import('./pages/employer/VacanciesPage'))
const EmpVacancyForm = lazy(() => import('./pages/employer/VacancyFormPage'))
const EmpMatches = lazy(() => import('./pages/employer/MatchesPage'))
const EmpCandidates = lazy(() => import('./pages/employer/CandidatesPage'))
const EmpCandidate = lazy(() => import('./pages/employer/CandidateDetailPage'))
const EmpInvitations = lazy(() => import('./pages/employer/InvitationsPage'))
const EmpChallenges = lazy(() => import('./pages/employer/ChallengesPage'))
const EmpSettings = lazy(() => import('./pages/employer/SettingsPage'))

function FullSpinner() {
  return (
    <div className="full-center">
      <Spinner />
    </div>
  )
}

/** Только для вошедших; иначе — на страницу входа с возвратом. */
function RequireAuth({ children }: { children: ReactNode }) {
  const { loading, isAuthenticated } = useAuth()
  const loc = useLocation()
  if (loading) return <FullSpinner />
  if (!isAuthenticated) return <Navigate to={`/auth?next=${encodeURIComponent(loc.pathname)}`} replace />
  return <>{children}</>
}

/** Ограничение маршрута ролью: чужая роль уводится на свой дашборд. */
function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { role: current } = useAuth()
  if (current !== role) return <Navigate to="/app/dashboard" replace />
  return <>{children}</>
}

/** Один путь — разные страницы для кандидата и работодателя. */
function ByRole({ candidate, employer }: { candidate: ReactNode; employer: ReactNode }) {
  const { role } = useAuth()
  return <>{role === 'employer' ? employer : candidate}</>
}

const cand = (el: ReactNode) => <RequireRole role="candidate">{el}</RequireRole>
const emp = (el: ReactNode) => <RequireRole role="employer">{el}</RequireRole>

export default function App() {
  return (
    <ErrorBoundary>
      <Suspense fallback={<FullSpinner />}>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<LandingPage />} />
            <Route path="/privacy" element={<PrivacyPage />} />
            <Route path="/terms" element={<TermsPage />} />
          </Route>

          <Route element={<CenteredLayout />}>
            <Route path="/auth" element={<AuthPage />} />
            <Route path="/verify/:token" element={<EmailVerifyPage />} />
            <Route path="/email-verify" element={<EmailVerifyPage />} />
          </Route>

          <Route
            path="/app"
            element={
              <RequireAuth>
                <AppLayout />
              </RequireAuth>
            }
          >
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<ByRole candidate={<CandDashboard />} employer={<EmpDashboard />} />} />
            <Route path="vacancies" element={<ByRole candidate={<CandVacancies />} employer={<EmpVacancies />} />} />
            <Route path="invitations" element={<ByRole candidate={<CandInvitations />} employer={<EmpInvitations />} />} />
            <Route path="challenges" element={<ByRole candidate={<CandChallenges />} employer={<EmpChallenges />} />} />
            <Route path="settings" element={<ByRole candidate={<CandSettings />} employer={<EmpSettings />} />} />

            <Route path="profile" element={cand(<CandProfile />)} />
            <Route path="assessment" element={cand(<CandAssessment />)} />

            <Route path="company" element={emp(<EmpCompany />)} />
            <Route path="vacancies/new" element={emp(<EmpVacancyForm />)} />
            <Route path="vacancies/:id/edit" element={emp(<EmpVacancyForm />)} />
            <Route path="vacancies/:id/matches" element={emp(<EmpMatches />)} />
            <Route path="candidates" element={emp(<EmpCandidates />)} />
            <Route path="candidates/:id" element={emp(<EmpCandidate />)} />
            <Route path="*" element={<NotFoundPage inApp />} />
          </Route>

          <Route element={<PublicLayout />}>
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
