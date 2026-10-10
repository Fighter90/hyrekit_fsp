import { Suspense, type ReactNode } from 'react'
import { lazyPage } from './lib/lazyPage'
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
const AppLayout = lazyPage(() => import('./components/layout/AppLayout'))
const ExpressPage = lazyPage(() => import('./pages/auth/ExpressPage'))
const EmailVerifyPage = lazyPage(() => import('./pages/auth/EmailVerifyPage'))
const PrivacyPage = lazyPage(() => import('./pages/public/PrivacyPage'))
const TermsPage = lazyPage(() => import('./pages/public/TermsPage'))
const NotFoundPage = lazyPage(() => import('./pages/public/NotFoundPage'))

const CandDashboard = lazyPage(() => import('./pages/candidate/DashboardPage'))
const CandProfile = lazyPage(() => import('./pages/candidate/ProfilePage'))
const CandAssessment = lazyPage(() => import('./pages/candidate/AssessmentPage'))
const CandInvitations = lazyPage(() => import('./pages/candidate/InvitationsPage'))
const CandVacancies = lazyPage(() => import('./pages/candidate/VacanciesPage'))
const CandChallenges = lazyPage(() => import('./pages/candidate/ChallengesPage'))
const CandSettings = lazyPage(() => import('./pages/candidate/SettingsPage'))

const EmpDashboard = lazyPage(() => import('./pages/employer/DashboardPage'))
const EmpCompany = lazyPage(() => import('./pages/employer/CompanyPage'))
const EmpVacancies = lazyPage(() => import('./pages/employer/VacanciesPage'))
const EmpVacancyForm = lazyPage(() => import('./pages/employer/VacancyFormPage'))
const EmpMatches = lazyPage(() => import('./pages/employer/MatchesPage'))
const EmpCandidates = lazyPage(() => import('./pages/employer/CandidatesPage'))
const EmpCandidate = lazyPage(() => import('./pages/employer/CandidateDetailPage'))
const EmpFavorites = lazyPage(() => import('./pages/employer/FavoritesPage'))
const EmpInvitations = lazyPage(() => import('./pages/employer/InvitationsPage'))
const EmpChallenges = lazyPage(() => import('./pages/employer/ChallengesPage'))
const EmpSettings = lazyPage(() => import('./pages/employer/SettingsPage'))

const CandArena = lazyPage(() => import('./pages/arena/CandidateArenaPage'))
const EmpArena = lazyPage(() => import('./pages/arena/EmployerArenaPage'))
const ArenaRound = lazyPage(() => import('./pages/arena/ArenaRoundPage'))

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
            <Route path="/express" element={<ExpressPage />} />
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
            <Route path="arena" element={<ByRole candidate={<CandArena />} employer={<EmpArena />} />} />
            <Route path="arena/:roundId" element={<ArenaRound />} />

            <Route path="profile" element={cand(<CandProfile />)} />
            <Route path="assessment" element={cand(<CandAssessment />)} />

            <Route path="company" element={emp(<EmpCompany />)} />
            <Route path="vacancies/new" element={emp(<EmpVacancyForm />)} />
            <Route path="vacancies/:id/edit" element={emp(<EmpVacancyForm />)} />
            <Route path="vacancies/:id/matches" element={emp(<EmpMatches />)} />
            <Route path="candidates" element={emp(<EmpCandidates />)} />
            <Route path="candidates/:id" element={emp(<EmpCandidate />)} />
            <Route path="favorites" element={emp(<EmpFavorites />)} />
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
