import type { ReactNode } from 'react'

export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string
  subtitle?: string
  action?: ReactNode
}) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4 border-b border-[var(--rs-border)] pb-4">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight text-[var(--rs-text)]">{title}</h1>
        {subtitle ? (
          <p className="mt-1 text-sm text-[var(--rs-text-muted)]">{subtitle}</p>
        ) : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </header>
  )
}
