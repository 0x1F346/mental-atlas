import { render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import App from './App'

afterEach(() => vi.unstubAllGlobals())

function stubFetch(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })),
  )
}

test('shows the sign-in form when nobody is signed in', async () => {
  stubFetch(401, { error: { code: 'not_signed_in', message: 'Sign in to continue.' } })
  render(<App />)
  expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
})

test('shows the app when signed in', async () => {
  stubFetch(200, { id: 'u1', email: 'owner@example.com', csrf_token: 't' })
  render(<App />)
  expect(await screen.findByRole('link', { name: 'Sources' })).toBeInTheDocument()
})
