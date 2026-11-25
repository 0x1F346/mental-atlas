import { useState } from 'react'
import type { FormEvent } from 'react'

import { ApiFailure } from '../api/client'
import { useAuth } from '../auth'

export default function LoginPage() {
  const { signIn } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function submit(event: FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await signIn(email, password)
    } catch (failure) {
      setError(failure instanceof ApiFailure ? failure.message : 'Could not sign in.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="narrow">
      <h1>Mental Atlas</h1>
      <form onSubmit={submit} className="stack">
        <label>
          Email
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          Sign in
        </button>
      </form>
    </main>
  )
}
