// Line icons from the design mockups (docs/design). 24×24, drawn with currentColor.
import type { ReactNode } from 'react'

import type { NodeType } from './api/generated/vocabulary'

const PATHS = {
  person: (
    <>
      <circle cx="12" cy="8" r="3.5" />
      <path d="M5 20c0-3.9 3.1-6.5 7-6.5s7 2.6 7 6.5" />
    </>
  ),
  situation: (
    <>
      <path d="M12 21s-6.5-5.6-6.5-10.5a6.5 6.5 0 0 1 13 0C18.5 15.4 12 21 12 21z" />
      <circle cx="12" cy="10.5" r="2" />
    </>
  ),
  event: <path d="M12 3v5M12 16v5M3 12h5M16 12h5M6 6l3 3M15 15l3 3M18 6l-3 3M9 15l-3 3" />,
  feeling: <path d="M12 20s-7-4.4-7-9.6A4 4 0 0 1 12 8a4 4 0 0 1 7 2.4C19 15.6 12 20 12 20z" />,
  belief: (
    <>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="2.5" />
    </>
  ),
  behaviour: (
    <path d="M4 12a8 8 0 0 1 13.7-5.6L20 8.5M20 4v4.5h-4.5M20 12a8 8 0 0 1-13.7 5.6L4 15.5M4 20v-4.5h4.5" />
  ),
  group: (
    <>
      <circle cx="9" cy="8.5" r="3" />
      <circle cx="16.5" cy="9.5" r="2.5" />
      <path d="M3.5 19.5c0-3.3 2.5-5.5 5.5-5.5s5.5 2.2 5.5 5.5M15 14.2c3 .2 5.5 2.1 5.5 5.3" />
    </>
  ),
  sensation: <path d="M3 12h4l2-5 3 10 2-6 1.5 1H21" />,
  need: <path d="M12 3.5s6 6.4 6 10.5a6 6 0 0 1-12 0C6 9.9 12 3.5 12 3.5z" />,
  value: <path d="M7 4.5h10l4 4.5-9 11-9-11zM3 9h18M10 4.5 12 20M14 4.5 12 20" />,
  goal: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="4.5" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </>
  ),
  trait: <path d="M12 3l7.8 4.5v9L12 21l-7.8-4.5v-9z" />,
  role: <path d="M5 5h14v6a7 7 0 0 1-14 0zM9 10h.01M15 10h.01M9.5 14.5c1.4 1 3.6 1 5 0" />,
  pattern: <path d="M3 8c3-3 6 3 9 0s6-3 9 0M3 16c3-3 6 3 9 0s6-3 9 0" />,
  tension: <path d="M3 12h7M7 9l3 3-3 3M21 12h-7M17 9l-3 3 3 3" />,
  blind_spot: <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12zM4.5 19.5l15-15" />,
  unsorted: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.3-1 .9-1 1.6v.4M12 17h.01" />
    </>
  ),
  close: <path d="M6 6l12 12M18 6L6 18" />,
  play: <path d="M8 5.5v13l11-6.5z" fill="currentColor" />,
  pause: <path d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z" fill="currentColor" />,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  supports: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  contradicts: <path d="M5 9h14M5 15h14M15 5L9 19" />,
  waveform: <path d="M4 10v4M8 6v12M12 9v6M16 4v16M20 10v4" />,
  mic: (
    <>
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21" />
    </>
  ),
  page: <path d="M7 3h8l4 4v14H7zM15 3v4h4M10 12h6M10 16h6" />,
  upload: <path d="M12 16V5M7 10l5-5 5 5M5 20h14" />,
  lock: (
    <>
      <rect x="5" y="11" width="14" height="9" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  minus: <path d="M5 12h14" />,
  fit: <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />,
} satisfies Record<string, ReactNode>

export type IconName = keyof typeof PATHS

export function Icon({ name, size = 16, className }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
      style={{ flex: 'none' }}
    >
      {PATHS[name]}
    </svg>
  )
}

/** Every concept type has its own icon (D-024). */
export function typeIcon(type: NodeType): IconName {
  return type
}
