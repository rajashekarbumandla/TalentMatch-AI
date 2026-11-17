/** Wraps the app pages: shows a loader while a stored session is checked, and sends signed-out users to /login. */
import { Loader2 } from 'lucide-react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function RequireAuth({ children }) {
  const { status } = useAuth()
  const location = useLocation()
  if (status === 'checking') {
    return (
      <div className="flex min-h-screen items-center justify-center gap-2 text-sm text-slate-500" role="status">
        <Loader2 className="size-5 animate-spin text-brand-600" aria-hidden="true" /> Checking your session…
      </div>
    )
  }
  if (status !== 'signed-in') return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}
