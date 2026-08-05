import { Outlet } from 'react-router-dom'
import WorkspaceSidebar from './WorkspaceSidebar'

export default function EstimationLayout() {
  return (
    <div className="flex min-h-screen">
      <WorkspaceSidebar workspace="estimation" />
      <Outlet />
    </div>
  )
}
