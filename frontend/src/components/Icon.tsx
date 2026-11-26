import type { ReactNode } from 'react'

type IconName = 'link' | 'copy' | 'check' | 'open' | 'reset' | 'refresh' | 'alert'

const paths: Record<IconName, ReactNode> = {
  link: <><path d="m10 13 4-4" /><path d="m8 15-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0M12 5l1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" /></>,
  copy: <><rect x="7" y="7" width="11" height="12" rx="1.5" /><path d="M4 14H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v1" /></>,
  check: <path d="m4 10 4 4 9-9" />,
  open: <><rect x="2" y="3" width="16" height="14" rx="1.5" /><path d="M2 7h16M5 5h.01M8 5h.01" /></>,
  reset: <><path d="M4 7a7 7 0 1 1-1 7" /><path d="M4 2v5h5" /></>,
  refresh: <><path d="M17 7a7 7 0 0 0-12-3L2 7m0-5v5h5M3 13a7 7 0 0 0 12 3l3-3m0 5v-5h-5" /></>,
  alert: <><circle cx="10" cy="10" r="8" /><path d="M10 6v5M10 14h.01" /></>,
}

export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  return <svg className={`icon ${className}`} width="20" height="20" viewBox="0 0 20 20" fill="none"
    stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false">{paths[name]}</svg>
}
