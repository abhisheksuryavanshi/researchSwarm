import type { HTMLAttributes, ReactNode } from 'react'

export function Card({
  children,
  className = '',
  ...rest
}: HTMLAttributes<HTMLDivElement> & { children: ReactNode }) {
  return (
    <div
      className={[
        'rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)] bg-[var(--rs-surface)] p-4',
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </div>
  )
}
