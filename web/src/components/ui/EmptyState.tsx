import type { ReactNode } from 'react'
import { Button } from './Button'

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}: {
  icon?: ReactNode
  title: string
  description?: string
  actionLabel?: string
  onAction?: () => void
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12 px-4 text-center">
      {icon ? <div className="text-[var(--rs-text-muted)]">{icon}</div> : null}
      <h3 className="text-lg font-medium text-[var(--rs-text)]">{title}</h3>
      {description ? (
        <p className="max-w-md text-sm text-[var(--rs-text-muted)]">{description}</p>
      ) : null}
      {actionLabel && onAction ? (
        <Button type="button" variant="secondary" onClick={onAction}>
          {actionLabel}
        </Button>
      ) : null}
    </div>
  )
}
