import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'

import { api, setCsrfToken, unwrap, type Me } from './api/client'

interface AuthState {
  me: Me | null
  loading: boolean
  signIn: (email: string, password: string) => Promise<void>
  signOut: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    api.GET('/api/v1/auth/me').then((result) => {
      if (cancelled) return
      if (result.response.ok && result.data) {
        setCsrfToken(result.data.csrf_token)
        setMe(result.data)
      }
      setLoading(false)
    })
    return () => {
      cancelled = true
    }
  }, [])

  const signIn = useCallback(async (email: string, password: string) => {
    const user = unwrap(await api.POST('/api/v1/auth/login', { body: { email, password } }))
    setCsrfToken(user.csrf_token)
    setMe(user)
  }, [])

  const signOut = useCallback(async () => {
    await api.POST('/api/v1/auth/logout')
    setCsrfToken(null)
    setMe(null)
  }, [])

  const value = useMemo(() => ({ me, loading, signIn, signOut }), [me, loading, signIn, signOut])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthState {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
