import { useRouteError, isRouteErrorResponse, Link } from 'react-router-dom'

export default function ErrorBoundary() {
  const error = useRouteError()
  
  let title = "Oops! Something went wrong."
  let message = "An unexpected error occurred."

  if (isRouteErrorResponse(error)) {
    if (error.status === 404) {
      title = "404 - Page Not Found"
      message = "The page you are looking for doesn't exist or has been moved."
    } else {
      title = `${error.status} - ${error.statusText}`
      message = error.data?.message || "An unexpected error occurred."
    }
  } else if (error instanceof Error) {
    message = error.message
  }

  return (
    <div className="flex-1 min-h-screen bg-slate-50 flex flex-col items-center justify-center p-8 text-center">
      <div className="w-20 h-20 rounded-full bg-coral-100 text-coral-500 flex items-center justify-center text-3xl mb-6">
        ⚠️
      </div>
      <h1 className="text-2xl font-bold text-slate-800 mb-3">{title}</h1>
      <p className="text-slate-500 mb-8 max-w-md">{message}</p>
      <Link 
        to="/" 
        className="px-6 py-2.5 bg-brand-600 hover:bg-brand-700 text-white rounded-xl font-medium transition-colors"
      >
        Return to Home
      </Link>
    </div>
  )
}
