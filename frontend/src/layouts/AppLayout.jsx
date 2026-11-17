/** App shell: sidebar navigation, top bar (page title, notifications, recruiter placeholder) and page content. */
import {
  BarChart3,
  Bell,
  BriefcaseBusiness,
  ChevronDown,
  History,
  LayoutDashboard,
  LogOut,
  Menu,
  PlusCircle,
  Settings,
  Sparkles,
  Trophy,
  UserCog,
  X,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, matchPath, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { analysisApi } from '../services/api'
import { formatDateTime, formatScore } from '../utils/format'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/analysis/new', label: 'New Analysis', icon: PlusCircle },
  { to: '/rankings', label: 'Candidate Rankings', icon: Trophy },
  { to: '/jobs', label: 'Job Descriptions', icon: BriefcaseBusiness },
  { to: '/history', label: 'Analysis History', icon: History },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const PAGE_TITLES = [
  ['/', 'Dashboard'],
  ['/analysis/new', 'New Analysis'],
  ['/rankings', 'Candidate Rankings'],
  ['/candidates/:candidateId/jobs/:jobId', 'Candidate Details'],
  ['/jobs', 'Job Descriptions'],
  ['/jobs/:jobId/edit', 'Edit Job Description'],
  ['/history', 'Analysis History'],
  ['/settings', 'Settings'],
]

function pageTitle(pathname) {
  return PAGE_TITLES.find(([pattern]) => matchPath({ path: pattern, end: true }, pathname))?.[1] || 'TalentMatch AI'
}

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2.5 px-2">
      <div className="flex size-9 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-accent-600">
        <Sparkles className="size-5 text-white" aria-hidden="true" />
      </div>
      <div className="leading-tight">
        <p className="font-bold text-white">TalentMatch AI</p>
        <p className="text-[11px] text-brand-100/70">Smarter hiring decisions</p>
      </div>
    </Link>
  )
}

function Sidebar({ onNavigate }) {
  return (
    <nav className="flex h-full flex-col gap-6 bg-navy-900 px-3 py-5" aria-label="Main navigation">
      <Logo />
      <ul className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              onClick={onNavigate}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                  isActive ? 'bg-white/10 text-white' : 'text-brand-100/70 hover:bg-white/5 hover:text-white'
                }`
              }
            >
              <Icon className="size-4.5" aria-hidden="true" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="mt-auto rounded-lg bg-white/5 p-3 text-xs text-brand-100/70">
        <p className="flex items-center gap-1.5 font-medium text-white">
          <BarChart3 className="size-3.5" aria-hidden="true" /> Decision support
        </p>
        <p className="mt-1">Scores help you prioritise. Every hiring decision should include human review.</p>
      </div>
    </nav>
  )
}

const LAST_SEEN_KEY = 'talentmatch:notifications-last-seen' // per browser; analyses are already per HR

function readLastSeen() {
  try {
    return localStorage.getItem(LAST_SEEN_KEY) || ''
  } catch {
    return ''
  }
}

/** Bell menu listing the most recent analyses (real data). A dot marks analyses since you last opened it. */
function NotificationsMenu() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState(null)
  const [lastSeen, setLastSeen] = useState(readLastSeen)
  const menuRef = useRef(null)
  const location = useLocation()

  useEffect(() => {
    let cancelled = false
    analysisApi.history({ limit: 5 }).then(
      (data) => !cancelled && setItems(data),
      () => !cancelled && setItems([]),
    )
    return () => {
      cancelled = true
    }
  }, [location.pathname])

  useEffect(() => {
    if (!open) return undefined
    const close = (event) => !menuRef.current?.contains(event.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  const hasNew = Boolean(items?.length && items[0].created_at > lastSeen)
  const toggle = () => {
    setOpen((value) => !value)
    if (items?.length) {
      setLastSeen(items[0].created_at)
      try {
        localStorage.setItem(LAST_SEEN_KEY, items[0].created_at)
      } catch {
        /* storage unavailable: the dot simply reappears next time */
      }
    }
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={toggle}
        className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-700"
        aria-label={hasNew ? 'Notifications (new analyses)' : 'Notifications'}
        aria-expanded={open}
      >
        <Bell className="size-5" />
        {hasNew && <span className="absolute right-1.5 top-1.5 size-2 rounded-full bg-accent-500 ring-2 ring-white" />}
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-80 rounded-xl border border-slate-200 bg-white shadow-xl">
          <p className="border-b border-slate-100 px-4 py-3 text-sm font-semibold text-slate-900">Recent analyses</p>
          {!items?.length ? (
            <p className="px-4 py-6 text-center text-sm text-slate-500">No analyses yet.</p>
          ) : (
            <ul className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
              {items.map((a) => (
                <li key={a.id}>
                  <Link
                    to={`/rankings?jobId=${a.job_id}&analysisId=${a.id}`}
                    onClick={() => setOpen(false)}
                    className="block px-4 py-3 hover:bg-slate-50"
                  >
                    <p className="text-sm font-medium text-slate-900">{a.job_title}</p>
                    <p className="text-xs text-slate-500">
                      {a.total_resumes} resumes · average {formatScore(a.average_score)} · {formatDateTime(a.created_at)}
                    </p>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          <Link to="/history" onClick={() => setOpen(false)} className="block border-t border-slate-100 px-4 py-2.5 text-center text-sm font-medium text-brand-700 hover:bg-slate-50">
            View all analyses
          </Link>
        </div>
      )}
    </div>
  )
}

function initials(name) {
  return name.split(' ').filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
}

/** The signed-in HR: name, role, link to account settings, sign out. */
function UserMenu() {
  const { user, logout } = useAuth()
  const [open, setOpen] = useState(false)
  const menuRef = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const close = (event) => !menuRef.current?.contains(event.target) && setOpen(false)
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  return (
    <div className="relative border-l border-slate-200 pl-3" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-lg p-1 hover:bg-slate-100"
        aria-expanded={open}
        aria-label={`Account menu for ${user.full_name}`}
      >
        <span className="flex size-8 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700" aria-hidden="true">
          {initials(user.full_name)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-medium text-slate-900">{user.full_name}</span>
          <span className="block text-xs text-slate-500">{user.role === 'admin' ? 'Admin' : 'HR recruiter'}</span>
        </span>
        <ChevronDown className="hidden size-4 text-slate-400 sm:block" aria-hidden="true" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-64 rounded-xl border border-slate-200 bg-white py-1 shadow-xl">
          <div className="border-b border-slate-100 px-4 py-3">
            <p className="text-sm font-medium text-slate-900">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
          </div>
          <Link to="/settings" onClick={() => setOpen(false)} className="flex items-center gap-2 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50">
            <UserCog className="size-4" aria-hidden="true" /> {user.role === 'admin' ? 'Account & team' : 'My account'}
          </Link>
          <button type="button" onClick={() => logout()} className="flex w-full items-center gap-2 px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50">
            <LogOut className="size-4" aria-hidden="true" /> Sign out
          </button>
        </div>
      )}
    </div>
  )
}

export default function AppLayout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const { pathname } = useLocation()
  const title = pageTitle(pathname)

  useEffect(() => {
    document.title = `${title} · TalentMatch AI`
  }, [title])

  return (
    <div className="min-h-screen lg:pl-64 print:pl-0">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-64 lg:block print:hidden">
        <Sidebar />
      </aside>

      {/* Mobile sidebar */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-navy-950/50" onClick={() => setMobileOpen(false)} />
          <aside className="relative h-full w-64">
            <Sidebar onNavigate={() => setMobileOpen(false)} />
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="absolute right-3 top-5 rounded-lg p-1 text-white/70 hover:text-white"
              aria-label="Close menu"
            >
              <X className="size-5" />
            </button>
          </aside>
        </div>
      )}

      <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-slate-200 bg-white/90 px-4 backdrop-blur sm:px-6 print:hidden">
        <button type="button" onClick={() => setMobileOpen(true)} className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden" aria-label="Open menu">
          <Menu className="size-5" />
        </button>
        <p className="text-sm font-medium text-slate-500">
          <span className="hidden sm:inline">TalentMatch AI / </span>
          <span className="text-slate-900">{title}</span>
        </p>
        <div className="ml-auto flex items-center gap-2">
          <NotificationsMenu />
          <UserMenu />
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:py-8">
        <Outlet />
      </main>
    </div>
  )
}
