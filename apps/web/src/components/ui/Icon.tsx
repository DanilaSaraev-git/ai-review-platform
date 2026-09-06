import type { ReactNode } from 'react';

const paths = {
  plus: <path d="M12 5v14M5 12h14" />,
  history: <><path d="M3 11a9 9 0 1 1 2.4 7M3 4v7h7" /><path d="M12 7v5l3 2" /></>,
  'file-text': <><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" /><path d="M14 2v6h6M8 12h8M8 16h8" /></>,
  upload: <path d="m7 7 5-5 5 5M12 2v14M4 16v4a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4" />,
  'chevron-right': <path d="m9 5 7 7-7 7" />,
  'chevron-left': <path d="m15 5-7 7 7 7" />,
  'arrow-left': <path d="m12 5-7 7 7 7M5 12h14" />,
  'arrow-right': <path d="m12 5 7 7-7 7M5 12h14" />,
  paperclip: <path d="m21 11-9 9a6 6 0 0 1-8.5-8.5l9-9a4 4 0 0 1 5.7 5.7l-9 9a2 2 0 0 1-2.8-2.8L15 6" />,
  settings: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1" /><circle cx="12" cy="12" r="6" /><circle cx="12" cy="12" r="2" /></>,
  sliders: <><path d="M4 7h5m4 0h7M4 17h9m4 0h3" /><circle cx="11" cy="7" r="2" /><circle cx="15" cy="17" r="2" /></>,
  check: <path d="m5 12 4 4L19 6" />,
  x: <path d="m6 6 12 12M6 18 18 6" />,
  layers: <path d="m12 3 10 6-10 6L2 9ZM2 14l10 6 10-6" />,
  messages: <><path d="M21 11a2 2 0 0 1-2 2H9l-5 4V5a2 2 0 0 1 2-2h13a2 2 0 0 1 2 2Z" /><path d="M9 17h8l4 4v-4" /></>,
} satisfies Record<string, ReactNode>;

export type IconName = keyof typeof paths;

/** Декоративные знаки; имя действия задаётся подписью родителя. */
export function Icon({ name, size = 16, className = '' }: { name: IconName; size?: number; className?: string }) {
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className={`shrink-0 ${className}`}>{paths[name]}</svg>;
}
