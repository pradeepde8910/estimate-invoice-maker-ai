import { Routes, Route } from 'react-router-dom'
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

export default function App() {
  return (
    <JobProvider>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<ProtectedRoute />}>
          <Route path="/" element={<Home />} />

          <Route path="/estimation" element={<EstimationLayout />}>
            <Route index element={<EstimationDashboard />} />
            <Route path="new" element={<NewEstimation />} />
            <Route path="list" element={<EstimationList />} />
            <Route path="document/base/:baseName/:type" element={<DocumentView source="base" />} />
            <Route path="document/:jobId/:type" element={<DocumentView source="job" />} />
            <Route path=":baseName" element={<EstimationDetail />} />
          </Route>

          <Route path="/invoice" element={<InvoiceLayout />}>
            <Route index element={<InvoiceDashboard />} />
            <Route path="new" element={<NewInvoice />} />
            <Route path="list" element={<InvoiceHistory />} />
            <Route path=":baseName" element={<InvoiceDetail />} />
          </Route>

          <Route path="/organization" element={<OrganizationSettings />} />
          <Route path="/rate-card" element={<RateCardPage />} />
        </Route>
      </Routes>
    </JobProvider>
  )
}
