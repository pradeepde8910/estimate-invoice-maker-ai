import { Navigate, Outlet } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { validateSession } from '../api/client'

export default function ProtectedRoute() {
  const [isValidating, setIsValidating] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)

  useEffect(() => {
    const checkAuth = async () => {
      const token = sessionStorage.getItem('pixous_auth_token')
      if (!token) {
        setIsAuthenticated(false)
        setIsValidating(false)
        return
      }

      const valid = await validateSession()
      if (!valid) {
        sessionStorage.removeItem('pixous_auth_token')
      }
      setIsAuthenticated(valid)
      setIsValidating(false)
    }
    
    checkAuth()
  }, [])

  if (isValidating) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <svg className="animate-spin h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
        </svg>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
