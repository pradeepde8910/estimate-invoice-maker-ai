import { ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface ConfirmModalProps {
  isOpen: boolean
  title: string
  message: ReactNode
  confirmText?: string
  cancelText?: string
  onConfirm: () => void
  onCancel: () => void
  onClose?: () => void
  /** 'danger' (default) for destructive/irreversible actions (delete, log out).
   *  'brand' for routine confirmations that aren't destructive (e.g. recording a payment). */
  tone?: 'danger' | 'brand'
  /** Disables both buttons — set while the confirmed action is in flight, so a slow
   *  request can't be fired twice and the dialog can't be dismissed mid-request. */
  busy?: boolean
}

export default function ConfirmModal({
  isOpen,
  title,
  message,
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  onConfirm,
  onCancel,
  onClose,
  tone = 'danger',
  busy = false,
}: ConfirmModalProps) {
  if (!isOpen) return null

  const handleClose = onClose || onCancel

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm" onClick={busy ? undefined : handleClose} />
      <div className="relative bg-white rounded-3xl shadow-card w-full max-w-sm p-6 animate-in fade-in zoom-in-95 duration-200">
        {onClose && (
          <button
            onClick={onClose}
            disabled={busy}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors disabled:opacity-40 disabled:pointer-events-none"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        )}
        <h3 className="text-xl font-semibold tracking-tight text-slate-800 mb-2 pr-6">{title}</h3>
        <p className="text-sm text-slate-600 mb-6 leading-relaxed">{message}</p>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            disabled={busy}
            className="px-5 py-2.5 rounded-full text-sm font-medium text-slate-600 bg-slate-100 hover:bg-slate-200 transition-colors disabled:opacity-50 disabled:pointer-events-none"
          >
            {cancelText}
          </button>
          <button
            onClick={onConfirm}
            disabled={busy}
            className={`px-5 py-2.5 rounded-full text-sm font-medium text-white shadow-sm transition-colors disabled:opacity-50 disabled:pointer-events-none ${
              tone === 'brand' ? 'bg-brand-600 hover:bg-brand-700' : 'bg-coral-500 hover:bg-coral-600'
            }`}
          >
            {confirmText}
          </button>
        </div>
      </div>
    </div>,
    document.body
  )
}
