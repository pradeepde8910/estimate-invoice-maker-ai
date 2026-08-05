import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/client'

export default function Login() {
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const navigate = useNavigate()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!password.trim()) {
      setError('Password is required')
      return
    }
    setError('')
    setLoading(true)

    try {
      await login(password)
      navigate('/')
    } catch (err: any) {
      let msg = 'Invalid credentials or connection error.'
      if (err?.message) {
        try {
          const parsed = JSON.parse(err.message)
          msg = parsed.detail || err.message
        } catch {
          msg = err.message
        }
      }
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 font-sans relative overflow-hidden">
      {/* Background blobs for depth and premium look */}
      <div className="absolute top-[-20%] left-[-10%] w-[50vw] h-[50vw] rounded-full bg-gradient-to-br from-pixous-blue/10 to-transparent blur-[100px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[-10%] w-[45vw] h-[45vw] rounded-full bg-gradient-to-tr from-pixous-teal/10 to-transparent blur-[90px] pointer-events-none" />

      <div className="relative w-full max-w-md px-6 py-12 z-10">
        {/* Logo and Brand Title */}
        <div className="flex flex-col items-center mb-8">
          <img src="/branding/logo.png" alt="Pixous Technologies Logo" className="h-14 w-auto object-contain mb-4" />
          <p className="text-xs text-slate-500 mt-1 uppercase tracking-wider font-semibold text-center">Estimation & Invoicing Portal</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-slate-200/60 rounded-3xl p-8 shadow-xl shadow-slate-200/40 relative">
          <h2 className="text-lg font-semibold text-slate-800 mb-6">Administrator Access</h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            {error && (
              <div className="p-3.5 rounded-2xl bg-coral-50 border border-coral-200 text-coral-600 text-xs flex items-start gap-2.5 animate-fadeIn">
                <span className="text-sm mt-0.5">⚠️</span>
                <span className="leading-relaxed text-coral-700">{error}</span>
              </div>
            )}

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Username</label>
              <div className="relative">
                <input
                  type="text"
                  disabled
                  value="admin"
                  className="w-full bg-slate-50 border border-slate-200 text-slate-400 rounded-2xl px-4 py-3.5 text-sm select-none opacity-80"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Enter administrator password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full bg-white border border-slate-200 text-slate-800 placeholder-slate-400 rounded-2xl pl-4 pr-11 py-3.5 text-sm transition-all focus:outline-none focus:border-pixous-blue focus:ring-2 focus:ring-pixous-blue/10"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.8} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542 7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-gradient-to-r from-pixous-blue to-[#2066ca] hover:from-[#1b55aa] hover:to-pixous-blue text-white font-semibold text-sm rounded-2xl py-4 transition-all shadow-lg shadow-pixous-blue/15 flex items-center justify-center gap-2 hover:-translate-y-[1px] active:translate-y-0 disabled:opacity-50 disabled:pointer-events-none"
            >
              {loading ? (
                <>
                  <svg className="animate-spin h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>Authenticating...</span>
                </>
              ) : (
                <span>Access Dashboard →</span>
              )}
            </button>
          </form>
        </div>

        {/* Footer */}
        <p className="text-center text-xs text-slate-400 mt-8">
          🔒 ISO 27001 Certified & Secured Connection
        </p>
      </div>
    </div>
  )
}
