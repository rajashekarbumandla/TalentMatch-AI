import { Compass } from 'lucide-react'
import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router-dom'
import RequireAuth from './auth/RequireAuth'
import { ButtonLink, Card, EmptyState, Spinner } from './components/ui'
import AppLayout from './layouts/AppLayout'
import LoginPage from './pages/LoginPage'

// Each page is downloaded only when first opened (code splitting), so the initial load stays small;
// for example, the charts library is only fetched for the dashboard.
const DashboardPage = lazy(() => import('./pages/DashboardPage'))
const NewAnalysisPage = lazy(() => import('./pages/NewAnalysisPage'))
const RankingsPage = lazy(() => import('./pages/RankingsPage'))
const CandidateDetailPage = lazy(() => import('./pages/CandidateDetailPage'))
const JobsPage = lazy(() => import('./pages/JobsPage'))
const JobEditPage = lazy(() => import('./pages/JobEditPage'))
const HistoryPage = lazy(() => import('./pages/HistoryPage'))
const SettingsPage = lazy(() => import('./pages/SettingsPage'))

function NotFoundPage() {
  return (
    <Card>
      <EmptyState icon={Compass} title="Page not found" description="The page you are looking for does not exist." action={<ButtonLink to="/">Go to dashboard</ButtonLink>} />
    </Card>
  )
}

const page = (Component) => (
  <Suspense fallback={<Spinner />}>
    <Component />
  </Suspense>
)

export default function App() {
  return (
    <Routes>
      <Route path="login" element={<LoginPage />} />
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route index element={page(DashboardPage)} />
        <Route path="analysis/new" element={page(NewAnalysisPage)} />
        <Route path="rankings" element={page(RankingsPage)} />
        <Route path="candidates/:candidateId/jobs/:jobId" element={page(CandidateDetailPage)} />
        <Route path="jobs" element={page(JobsPage)} />
        <Route path="jobs/:jobId/edit" element={page(JobEditPage)} />
        <Route path="history" element={page(HistoryPage)} />
        <Route path="settings" element={page(SettingsPage)} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  )
}
