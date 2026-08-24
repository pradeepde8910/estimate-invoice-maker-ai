import { createBrowserRouter, createRoutesFromElements, Route, RouterProvider } from 'react-router-dom'
import Home from './pages/Home'
import EstimationLayout from './components/EstimationLayout'
import InvoiceLayout from './components/InvoiceLayout'
import EstimationDashboard from './pages/EstimationDashboard'
import NewEstimation from './pages/NewEstimation'
import EstimationList from './pages/EstimationList'
import EstimationDetail from './pages/EstimationDetail'
import InvoiceDashboard from './pages/InvoiceDashboard'
import NewInvoice from './pages/NewInvoice'
import InvoiceHistory from './pages/InvoiceHistory'
import InvoiceDetail from './pages/InvoiceDetail'
import RateCardPage from './pages/RateCard'
import OrganizationSettings from './pages/OrganizationSettings'
import DocumentView from './pages/DocumentView'
import Login from './pages/Login'
import ProtectedRoute from './components/ProtectedRoute'
import { JobProvider } from './JobContext'
import ErrorBoundary from './components/ErrorBoundary'
import Projects from './pages/Projects'
import ProjectDetail from './pages/ProjectDetail'
import NewInvoiceV2 from './pages/NewInvoiceV2'
import InvoiceViewV2 from './pages/InvoiceViewV2'
import NewStandaloneInvoice from './pages/NewStandaloneInvoice'

import { BillingClassifications } from './pages/admin/BillingClassifications'
import ResourceCatalog from './pages/admin/ResourceCatalog'

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route errorElement={<ErrorBoundary />}>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Home />} />

        <Route path="/estimation" element={<EstimationLayout />}>
          <Route index element={<EstimationDashboard />} />
          <Route path="new" element={<NewEstimation />} />
          <Route path="list" element={<EstimationList />} />
          <Route path="rate-card" element={<RateCardPage />} />
          <Route path="organization" element={<OrganizationSettings />} />
          <Route path="resource-catalog" element={<ResourceCatalog />} />
          <Route path="document/base/:baseName/:type" element={<DocumentView source="base" />} />
          <Route path="document/:jobId/:type" element={<DocumentView source="job" />} />
          <Route path=":baseName" element={<EstimationDetail />} />
        </Route>

        <Route path="/invoice" element={<InvoiceLayout />}>
          <Route index element={<Projects />} />
          <Route path="projects/:projectId" element={<ProjectDetail />} />
          <Route path="projects/:projectId/new-invoice" element={<NewInvoiceV2 />} />
          <Route path="projects/:projectId/invoice/:invoiceId" element={<InvoiceViewV2 />} />
          <Route path="standalone/new" element={<NewStandaloneInvoice />} />
          <Route path="standalone/:invoiceId" element={<InvoiceViewV2 />} />
          <Route path="organization" element={<OrganizationSettings />} />
          <Route path="classifications" element={<BillingClassifications />} />
          <Route path="resource-catalog" element={<ResourceCatalog />} />
        </Route>
      </Route>

      <Route path="*" element={<ErrorBoundary />} />
    </Route>
  )
)

export default function App() {
  return (
    <JobProvider>
      <RouterProvider router={router} />
    </JobProvider>
  )
}
