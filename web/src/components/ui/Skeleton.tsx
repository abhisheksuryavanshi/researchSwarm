import type { HTMLAttributes } from 'react'

export function Skeleton({ className = '', ...rest }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={[
        'animate-pulse rounded-[var(--rs-radius-md)] bg-[var(--rs-border)]/60',
        className,
      ].join(' ')}
      {...rest}
    />
  )
}
