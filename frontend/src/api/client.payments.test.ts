import { describe, it, expect, beforeEach } from 'vitest'
import { recordPayment, recordManualPayment, listInvoicePayments } from './client'

// Regression coverage for the exact bug class just fixed on the backend:
// payment.router lived at app/api/payment.py but was never mounted in
// main.py, so every one of these frontend calls 404'd. These tests pin the
// URLs the client actually calls so a future path/prefix mismatch between
// frontend and backend shows up here instead of silently in production.
//
// NOTE: fetch is mocked globally in vitest.setup.ts, before client.ts is
// ever imported — see the comment there for why that ordering matters.
const fetchMock = fetch as unknown as { mock: { calls: any[][] }; mockReset: () => void; mockResolvedValue: (v: any) => void; mockResolvedValueOnce: (v: any) => void }

describe('payment API client', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve({ id: 'pay-1', status: 'SUCCESS' }),
    } as Response)
  })

  it('recordPayment posts to /api/payments/{projectId}/invoices/{invoiceId}/payments', async () => {
    await recordPayment('proj-1', 'inv-1', { amount: 100 })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/payments/proj-1/invoices/inv-1/payments')
    expect(options.method).toBe('POST')
  })

  it('recordManualPayment posts to the /manual sub-path', async () => {
    await recordManualPayment('proj-1', 'inv-1', {
      amount: 100,
      payment_method: 'CASH',
    })
    const [url, options] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/payments/proj-1/invoices/inv-1/payments/manual')
    expect(options.method).toBe('POST')
    expect(JSON.parse(options.body)).toMatchObject({ amount: 100, payment_method: 'CASH' })
  })

  it('listInvoicePayments GETs the same collection path recordPayment posts to', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      status: 200,
      json: () => Promise.resolve([]),
    } as Response)
    await listInvoicePayments('proj-1', 'inv-1')
    const [url] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/payments/proj-1/invoices/inv-1/payments')
  })
})
