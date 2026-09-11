import { lazy, Suspense } from 'react'
import { createBrowserRouter, createRoutesFromElements, Route, RouterProvider } from 'react-router-dom'
import ProtectedRoute from './components/ProtectedRoute'
import { JobProvider } from './JobContext'
import ErrorBoundary from './components/ErrorBoundary'
import PageFallback from './components/PageFallback'

// Route-level code splitting: each page (and whatever heavy library it
// alone needs — the rich-text editor, Mermaid, recharts, ...) is only
// fetched when its route is actually visited, instead of every one of
// them loading eagerly on first paint regardless of which page (even
// just /login) the browser lands on first.
const Home = lazy(() => import('./pages/Home'))
const EstimationLayout = lazy(() => import('./components/EstimationLayout'))
const InvoiceLayout = lazy(() => import('./components/InvoiceLayout'))
const EstimationDashboard = lazy(() => import('./pages/EstimationDashboard'))
const NewEstimation = lazy(() => import('./pages/NewEstimation'))
const EstimationList = lazy(() => import('./pages/EstimationList'))
const EstimationDetail = lazy(() => import('./pages/EstimationDetail'))
const RateCardPage = lazy(() => import('./pages/RateCard'))
const OrganizationSettings = lazy(() => import('./pages/OrganizationSettings'))
const DocumentView = lazy(() => import('./pages/DocumentView'))
const Login = lazy(() => import('./pages/Login'))
const Projects = lazy(() => import('./pages/Projects'))
const ProjectDetail = lazy(() => import('./pages/ProjectDetail'))
const NewInvoiceV2 = lazy(() => import('./pages/NewInvoiceV2'))
const InvoiceViewV2 = lazy(() => import('./pages/InvoiceViewV2'))
const NewStandaloneInvoice = lazy(() => import('./pages/NewStandaloneInvoice'))
const ExportCenter = lazy(() => import('./pages/ExportCenter'))
const ResourceCatalog = lazy(() => import('./pages/admin/ResourceCatalog'))
const BillingClassifications = lazy(() =>
  import('./pages/admin/BillingClassifications').then((m) => ({ default: m.BillingClassifications }))
)

const router = createBrowserRouter(
  createRoutesFromElements(
    <Route errorElement={<ErrorBoundary />}>
      <Route path="/login" element={<Login />} />

      <Route element={<ProtectedRoute />}>
        <Route path="/" element={<Home />} />
        <Route path="/organization" element={<OrganizationSettings />} />

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
          <Route path="export" element={<ExportCenter />} />
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
      <Suspense fallback={<PageFallback />}>
        <RouterProvider router={router} />
      </Suspense>
    </JobProvider>
  )
}
