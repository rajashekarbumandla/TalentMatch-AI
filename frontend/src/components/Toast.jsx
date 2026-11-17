/* eslint-disable react-refresh/only-export-components */
import { CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { createContext, useCallback, useContext, useMemo, useState } from 'react'

/**
 * Success / error notifications ("toasts") shown in the bottom-right corner.
 *   const toast = useToast(); toast.success('Job saved'); toast.error(message)
 */
const ToastContext = createContext(null)

const STYLES = {
  success: { icon: CheckCircle2, className: 'border-emerald-200 bg-white', iconClass: 'text-emerald-600' },
  error: { icon: XCircle, className: 'border-red-200 bg-white', iconClass: 'text-red-600' },
  info: { icon: Info, className: 'border-brand-100 bg-white', iconClass: 'text-brand-600' },
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const dismiss = useCallback((id) => setToasts((list) => list.filter((t) => t.id !== id)), [])
  const show = useCallback(
    (type, message) => {
      const id = crypto.randomUUID()
      setToasts((list) => [...list.slice(-3), { id, type, message }])
      setTimeout(() => dismiss(id), type === 'error' ? 7000 : 4000)
    },
    [dismiss],
  )
  const api = useMemo(
    () => ({
      success: (message) => show('success', message),
      error: (message) => show('error', message),
      info: (message) => show('info', message),
    }),
    [show],
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-end gap-2" aria-live="polite">
        {toasts.map(({ id, type, message }) => {
          const { icon: Icon, className, iconClass } = STYLES[type]
          return (
            <div
              key={id}
              role={type === 'error' ? 'alert' : 'status'}
              className={`pointer-events-auto flex w-full max-w-sm items-start gap-3 rounded-xl border p-4 shadow-lg ${className}`}
            >
              <Icon className={`mt-0.5 size-5 shrink-0 ${iconClass}`} aria-hidden="true" />
              <p className="flex-1 text-sm text-slate-700">{message}</p>
              <button type="button" onClick={() => dismiss(id)} className="text-slate-400 hover:text-slate-600" aria-label="Dismiss notification">
                <X className="size-4" />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) throw new Error('useToast must be used inside <ToastProvider>')
  return context
}
