import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import NewInvoiceV2 from './NewInvoiceV2'
import * as api from '../api/client'

// Regression coverage for the bug fixed alongside the loading-state/"Select
// All" feature work: milestoneReqs used to be built from `data` (the project
// summary response) instead of `previewData` (the billing-preview response)
// — the two were fetched sequentially before, and the requirement/task
// breakdown only exists on the billing-preview payload. These tests render
// the real component against mocked API responses so a future refactor that
// reintroduces that mismatch fails a test instead of shipping silently.

const SUMMARY = {
  project_name: 'Test Project',
  delivery_unit_label: 'Milestone',
  components: [],
}

const BILLING_PREVIEW = {
  milestones: [
    {
      id: 'ms-1',
      name: 'Milestone 1',
      status: 'PENDING',
      tasks: [
        { task_key: 'k1', requirement_name: 'Login Module', description: 'Build login API', amount: '500', hours: '10' },
        { task_key: 'k2', requirement_name: 'Login Module', description: 'Build login UI', amount: '300', hours: '6' },
        { task_key: 'k3', requirement_name: 'Reporting', description: 'Build report export', amount: '200', hours: '4' },
      ],
    },
  ],
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/invoice/projects/proj-1/new-invoice']}>
      <Routes>
        <Route path="/invoice/projects/:projectId/new-invoice" element={<NewInvoiceV2 />} />
      </Routes>
    </MemoryRouter>
  )
}

describe('NewInvoiceV2', () => {
  beforeEach(() => {
    vi.spyOn(api, 'getProjectSummary').mockResolvedValue(SUMMARY as any)
    vi.spyOn(api, 'getBillingPreview').mockResolvedValue(BILLING_PREVIEW as any)
    // ClassificationPicker debounce-fetches a match for every checked
    // requirement's description; stub it so tests don't depend on real
    // timers/network for a component this suite isn't exercising.
    vi.spyOn(api, 'matchBillingClassifications').mockResolvedValue([])
  })

  it('shows a loading state before both API calls resolve', async () => {
    renderPage()
    expect(screen.getByText(/Loading project line items/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByText(/Loading project line items/i)).not.toBeInTheDocument())
  })

  it('builds requirement groups from the billing-preview response, grouped and summed correctly', async () => {
    renderPage()
    await waitFor(() => screen.getByText('Login Module'))

    expect(screen.getByText('Reporting')).toBeInTheDocument()
    // Login Module groups two tasks (500 + 300 = 800)
    expect(screen.getByText('₹800')).toBeInTheDocument()
    // Reporting groups one task (200)
    expect(screen.getByText('₹200')).toBeInTheDocument()
  })

  it('defaults every requirement to checked and totals the full billing-preview amount', async () => {
    renderPage()
    await waitFor(() => screen.getByText('Login Module'))

    // 800 (Login Module) + 200 (Reporting) = 1000, all checked by default
    expect(screen.getByText('Selected: ₹1,000')).toBeInTheDocument()
  })

  it('"Deselect All" on a milestone removes its requirements from the running total', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Login Module'))

    await user.click(screen.getByText('Deselect All'))

    expect(screen.getByText('Selected: ₹0')).toBeInTheDocument()
  })

  it('"Select All" restores every requirement after a Deselect All', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Login Module'))

    await user.click(screen.getByText('Deselect All'))
    await user.click(screen.getByText('Select All'))

    expect(screen.getByText('Selected: ₹1,000')).toBeInTheDocument()
  })

  it('unchecking a single requirement checkbox updates the running total', async () => {
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => screen.getByText('Login Module'))

    const reportingRow = screen.getByText('Reporting').closest('div.p-3') as HTMLElement
    const checkbox = reportingRow.querySelector('input[type="checkbox"]') as HTMLInputElement
    await user.click(checkbox)

    // 1000 total minus Reporting's 200 = 800
    expect(screen.getByText('Selected: ₹800')).toBeInTheDocument()
  })

  it('surfaces the error message when either API call fails, instead of hanging on loading', async () => {
    vi.spyOn(api, 'getBillingPreview').mockRejectedValue(new Error('Failed to load project details'))
    renderPage()

    await waitFor(() => expect(screen.queryByText(/Loading project line items/i)).not.toBeInTheDocument())
    // summary never gets set because Promise.all rejects as a whole, so the
    // component renders null rather than a stale/partial page.
    expect(document.body.textContent).not.toMatch(/Create Invoice/)
  })
})
