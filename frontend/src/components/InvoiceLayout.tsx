import { Outlet } from 'react-router-dom'
import WorkspaceSidebar from './WorkspaceSidebar'

export default function InvoiceLayout() {
  return (
    <div className="flex min-h-screen">
      <WorkspaceSidebar workspace="invoice" />
      <Outlet />
    </div>
  )
}
