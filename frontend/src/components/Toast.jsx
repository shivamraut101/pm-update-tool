import { useState, useEffect, useCallback } from 'react'

const icons = {
  success: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M5 13l4 4L19 7" />
    </svg>
  ),
  error: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
    </svg>
  ),
  warning: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01M10.29 3.86l-8.4 14.31A1 1 0 002.77 20h18.46a1 1 0 00.88-1.83l-8.4-14.31a1 1 0 00-1.76 0z" />
    </svg>
  ),
  info: (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M12 2a10 10 0 100 20 10 10 0 000-20z" />
    </svg>
  ),
}

const styles = {
  success: 'bg-green-50 border-green-400 text-green-800',
  error: 'bg-red-50 border-red-400 text-red-800',
  warning: 'bg-amber-50 border-amber-400 text-amber-800',
  info: 'bg-blue-50 border-blue-400 text-blue-800',
}

const iconStyles = {
  success: 'text-green-500',
  error: 'text-red-500',
  warning: 'text-amber-500',
  info: 'text-blue-500',
}

const progressStyles = {
  success: 'bg-green-400',
  error: 'bg-red-400',
  warning: 'bg-amber-400',
  info: 'bg-blue-400',
}

function Toast({ toast, onDismiss }) {
  const [exiting, setExiting] = useState(false)
  const duration = toast.duration || 4000

  const handleDismiss = useCallback(() => {
    setExiting(true)
    setTimeout(() => onDismiss(toast.id), 250)
  }, [toast.id, onDismiss])

  useEffect(() => {
    const timer = setTimeout(handleDismiss, duration)
    return () => clearTimeout(timer)
  }, [duration, handleDismiss])

  return (
    <div
      className={`${styles[toast.type]} ${exiting ? 'toast-exit' : 'toast-enter'} border-l-4 rounded-lg shadow-lg p-4 flex items-start gap-3 max-w-sm w-full pointer-events-auto`}
    >
      <span className={`${iconStyles[toast.type]} flex-shrink-0 mt-0.5`}>
        {icons[toast.type]}
      </span>
      <div className="flex-1 min-w-0">
        {toast.title && (
          <p className="font-semibold text-sm">{toast.title}</p>
        )}
        <p className="text-sm">{toast.message}</p>
      </div>
      <button
        onClick={handleDismiss}
        className="flex-shrink-0 opacity-50 hover:opacity-100 transition-opacity"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
      <div className="absolute bottom-0 left-0 right-0 h-1 overflow-hidden rounded-b-lg">
        <div
          className={`h-full ${progressStyles[toast.type]}`}
          style={{ animation: `shrinkWidth ${duration}ms linear forwards` }}
        />
      </div>
    </div>
  )
}

let toastId = 0

export function useToast() {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', options = {}) => {
    const id = ++toastId
    setToasts((prev) => [...prev, { id, message, type, ...options }])
    return id
  }, [])

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = {
    success: (message, options) => addToast(message, 'success', options),
    error: (message, options) => addToast(message, 'error', options),
    warning: (message, options) => addToast(message, 'warning', options),
    info: (message, options) => addToast(message, 'info', options),
  }

  return { toasts, toast, dismissToast }
}

export function ToastContainer({ toasts, onDismiss }) {
  if (toasts.length === 0) return null

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-3 pointer-events-none">
      {toasts.map((t) => (
        <Toast key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}
