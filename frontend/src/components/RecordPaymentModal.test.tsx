import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import RecordPaymentModal from './RecordPaymentModal'
import * as api from '../api/client'

// Client-side guard tests for the payment amount field. The backend
// (payment_service.record_manual_payment) rejects an amount exceeding the
// outstanding balance with a 400 — these tests confirm the UI disables
// submission before that round trip even happens, for a clear inline
// message instead of a generic API error.

const invoice = {
  id: 'inv-1',
  invoice_number: 'INV-0001',
  total_payable: '1000.00',
  amount_paid: '400.00',
  balance_due: '600.00',
}

describe('RecordPaymentModal', () => {
  beforeEach(() => {
    vi.spyOn(api, 'recordManualPayment').mockResolvedValue({ payment_reference: 'PAY/2026-27/00001' })
  })

  it('pre-fills the amount field with the full balance due', () => {
    render(<RecordPaymentModal projectId="proj-1" invoice={invoice} onClose={vi.fn()} onRecorded={vi.fn()} />)
    expect(screen.getByDisplayValue('600.00')).toBeInTheDocument()
  })

  it('disables submit while no payment method is selected', () => {
    render(<RecordPaymentModal projectId="proj-1" invoice={invoice} onClose={vi.fn()} onRecorded={vi.fn()} />)
    expect(screen.getByRole('button', { name: /Record Payment/i })).toBeDisabled()
  })

  it('rejects (disables submit for) an amount greater than the balance due', async () => {
    const user = userEvent.setup()
    render(<RecordPaymentModal projectId="proj-1" invoice={invoice} onClose={vi.fn()} onRecorded={vi.fn()} />)

    const amountInput = screen.getByDisplayValue('600.00')
    await user.clear(amountInput)
    await user.type(amountInput, '999999')
    await user.selectOptions(screen.getByRole('combobox'), 'CASH')

    expect(screen.getByRole('button', { name: /Record Payment/i })).toBeDisabled()
    expect(screen.getByText(/Enter an amount between/i)).toBeInTheDocument()
  })

  it('submits recordManualPayment with the entered amount when the form is valid', async () => {
    const user = userEvent.setup()
    const onRecorded = vi.fn()
    render(<RecordPaymentModal projectId="proj-1" invoice={invoice} onClose={vi.fn()} onRecorded={onRecorded} />)

    await user.selectOptions(screen.getByRole('combobox'), 'BANK_TRANSFER')
    await user.click(screen.getByRole('button', { name: /Record Payment/i }))

    expect(api.recordManualPayment).toHaveBeenCalledWith(
      'proj-1',
      'inv-1',
      expect.objectContaining({ amount: 600, payment_method: 'BANK_TRANSFER' })
    )
    expect(onRecorded).toHaveBeenCalled()
  })
})
