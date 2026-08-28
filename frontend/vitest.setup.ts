import '@testing-library/jest-dom'
import { vi } from 'vitest'

// client.ts captures `window.fetch` into a module-level const at import time
// (`const originalFetch = window.fetch`) before wrapping it as `authFetch`.
// A stub installed later (e.g. per-test) would miss that capture entirely,
// so the mock function itself must exist as `globalThis.fetch` before any
// test file's `import ... from './client'` runs — i.e. here, in setup.
globalThis.fetch = vi.fn() as unknown as typeof fetch
