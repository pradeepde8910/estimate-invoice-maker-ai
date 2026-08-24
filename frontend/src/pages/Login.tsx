import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { login } from '../api/client'
import { useLogo } from '../hooks/useLogo'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const navigate = useNavigate()
  const logoUrl = useLogo()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!username.trim()) {
      setError('Username is required')
      return
    }
    if (!password.trim()) {
      setError('Password is required')
      return
    }
    setError('')
    setLoading(true)

    try {
      await login(password, username)
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
        <div className="flex flex-col items-center justify-center mb-8">
          {logoUrl
            ? <img src={logoUrl} alt="Logo" className="h-20 w-auto object-contain mb-4" />
            : <span className="text-xl font-bold tracking-tight text-slate-700 mb-4">Pixous Technologies</span>
          }
          <p className="text-sm text-slate-700 mt-1 uppercase tracking-wider font-bold text-center">Estimation &amp; Invoicing Portal</p>
        </div>

        {/* Card */}
        <div className="bg-white border border-slate-200/60 rounded-3xl p-8 shadow-xl shadow-slate-200/40 relative">
          <h2 className="text-xl font-bold tracking-tight text-slate-800 mb-6 text-center">Login</h2>

          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-slate-500 uppercase tracking-wider">Username</label>
              <div className="relative">
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter username"
                  className="w-full bg-white border border-slate-200 text-slate-800 placeholder-slate-400 rounded-2xl px-4 py-3.5 text-sm transition-all focus:outline-none focus:border-pixous-blue focus:ring-2 focus:ring-pixous-blue/10"
                  disabled={loading}
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
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61" />
                      <line x1="2" y1="2" x2="22" y2="22" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z" />
                      <circle cx="12" cy="12" r="3" strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} />
                    </svg>
                  )}
                </button>
              </div>
            </div>

            {error && (
              <div className="p-3.5 rounded-2xl bg-coral-50 border border-coral-200 text-coral-600 text-xs flex items-start gap-2.5 animate-fadeIn">
                <span className="text-sm mt-0.5">⚠️</span>
                <span className="leading-relaxed text-coral-700">{error}</span>
              </div>
            )}

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
                <span>Login</span>
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
