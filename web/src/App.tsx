import { BrowserRouter, Link, Navigate, NavLink, Outlet, Route, Routes } from 'react-router-dom'

import { AuthProvider, useAuth } from './auth'
import MapPage from './map/MapPage'
import LoginPage from './sources/LoginPage'
import SourcePage from './sources/SourcePage'
import SourcesPage from './sources/SourcesPage'

function Shell() {
  const { me, loading, signOut } = useAuth()
  if (loading) return <main aria-busy="true" />
  if (!me) return <LoginPage />
  return (
    <>
      <header className="topbar">
        <Link to="/" className="brand">
          <svg viewBox="0 0 28 28" aria-hidden="true">
            <circle cx="14" cy="14" r="12" fill="none" stroke="var(--accent)" strokeWidth="1" strokeDasharray="2 4" />
            <circle cx="14" cy="14" r="7" fill="none" stroke="var(--accent)" strokeWidth="1.2" />
            <circle cx="14" cy="14" r="2.6" fill="var(--accent)" />
          </svg>
          Mental Atlas
        </Link>
        <nav aria-label="Main">
          <NavLink to="/" end>
            Atlas
          </NavLink>
          <NavLink to="/sources">Sources</NavLink>
        </nav>
        <div className="topbar-end">
          <span className="private">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.7"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <rect x="5" y="11" width="14" height="9" rx="2" />
              <path d="M8 11V8a4 4 0 0 1 8 0v3" />
            </svg>
            Private to you
          </span>
          <button type="button" className="quiet small" onClick={signOut}>
            Sign out
          </button>
        </div>
      </header>
      <Outlet />
    </>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Shell />}>
            <Route path="/" element={<MapPage />} />
            <Route path="/sources" element={<SourcesPage />} />
            <Route path="/sources/:sourceId" element={<SourcePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
