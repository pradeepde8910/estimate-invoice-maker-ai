import { Navigate, Outlet } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { validateSession } from '../api/client'
import Spinner from './Spinner'

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
        <Spinner className="h-8 w-8 text-slate-400" />
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
