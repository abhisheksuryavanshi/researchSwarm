import type { ApiError } from '../../lib/api/types'
import { Button } from './Button'

export function ErrorBanner({
  error,
  onDismiss,
  onRetry,
}: {
  error: ApiError
  onDismiss?: () => void
  onRetry?: () => void
}) {
  return (
    <div
      role="alert"
      className="flex flex-wrap items-start gap-3 rounded-[var(--rs-radius-md)] border border-[var(--rs-danger)]/50 bg-[var(--rs-danger)]/10 p-4 text-[var(--rs-text)]"
    >
      <div className="min-w-0 flex-1">
        <p className="font-medium text-[var(--rs-danger)]">Error</p>
        <p className="mt-1 text-sm">{error.message}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        {onRetry ? (
          <Button type="button" size="sm" variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        ) : null}
        {onDismiss ? (
          <Button type="button" size="sm" variant="ghost" onClick={onDismiss}>
            Dismiss
          </Button>
        ) : null}
      </div>
    </div>
  )
}
