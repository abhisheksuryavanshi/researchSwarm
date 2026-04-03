import type { HTMLAttributes, ReactNode } from 'react'

const tones = {
  green: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  yellow: 'bg-amber-500/20 text-amber-200 border-amber-500/40',
  red: 'bg-red-500/20 text-red-300 border-red-500/40',
  grey: 'bg-zinc-500/20 text-zinc-300 border-zinc-500/40',
  blue: 'bg-blue-500/20 text-blue-200 border-blue-500/40',
} as const

export function Badge({
  tone = 'grey',
  children,
  className = '',
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof tones; children: ReactNode }) {
  return (
    <span
      className={[
        'inline-flex items-center rounded-[var(--rs-radius-sm)] border px-2 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </span>
  )
}
