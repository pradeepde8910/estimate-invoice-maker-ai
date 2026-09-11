import { Suspense, useEffect, useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import WorkspaceSidebar from './WorkspaceSidebar'
import PageFallback from './PageFallback'
import { SidebarMenuProvider } from '../SidebarMenuContext'

export default function EstimationLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const location = useLocation()

  // Any navigation (sidebar link, a button inside the page, back/forward)
  // should leave the mobile drawer closed rather than stuck open over the
  // next page's content.
  useEffect(() => {
    setSidebarOpen(false)
  }, [location.pathname])

  return (
    <div className="flex min-h-screen">
      <WorkspaceSidebar workspace="estimation" open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <div className="flex-1 min-w-0 flex flex-col">
        <SidebarMenuProvider value={() => setSidebarOpen(true)}>
          <Suspense fallback={<PageFallback />}>
            <Outlet />
          </Suspense>
        </SidebarMenuProvider>
      </div>
    </div>
  )
}
