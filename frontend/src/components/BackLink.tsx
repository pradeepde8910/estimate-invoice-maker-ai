import { useNavigate } from 'react-router-dom'

export default function BackLink() {
  const navigate = useNavigate()
  return (
    <button
      onClick={() => navigate(-1)}
      className="flex items-center gap-2 text-sm font-medium text-slate-500 hover:text-slate-700 px-8 pt-4 pb-1"
    >
      ← Back
    </button>
  )
}
