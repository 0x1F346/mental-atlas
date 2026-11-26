import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
// Fonts are bundled, not fetched from a third party (D-023).
import '@fontsource-variable/figtree'
import '@fontsource-variable/newsreader/opsz.css'
import '@fontsource-variable/newsreader/opsz-italic.css'
import './index.css'
import App from './App.tsx'

const root = document.getElementById('root')
if (!root) throw new Error('missing #root element')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
