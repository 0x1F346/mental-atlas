import { BrowserRouter, Link, Navigate, Outlet, Route, Routes } from 'react-router-dom'

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
        <strong>Mental Atlas</strong>
        <nav>
          <Link to="/">Map</Link>
          <Link to="/sources">Sources</Link>
        </nav>
        <button type="button" className="quiet" onClick={signOut}>
          Sign out
        </button>
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
