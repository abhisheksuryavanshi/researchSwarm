import { useState } from 'react'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Skeleton } from '../ui/Skeleton'

function truncateId(id: string): string {
  if (id.length <= 14) return id
  return `${id.slice(0, 8)}…${id.slice(-4)}`
}

export function SessionHeader({
  sessionId,
  loading,
  onNewSession,
}: {
  sessionId: string | null
  loading: boolean
  onNewSession: () => void | Promise<void>
}) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    if (!sessionId) return
    try {
      await navigator.clipboard.writeText(sessionId)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* ignore */
    }
  }

  if (loading) {
    return (
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rs-border)] pb-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-9 w-28" />
      </div>
    )
  }

  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 border-b border-[var(--rs-border)] pb-4">
      <div className="flex min-w-0 flex-wrap items-center gap-3">
        <span className="text-sm text-[var(--rs-text-muted)]">Session</span>
        <code className="truncate rounded bg-[var(--rs-surface-elevated)] px-2 py-1 font-mono text-sm text-[var(--rs-text)]">
          {sessionId ? truncateId(sessionId) : '—'}
        </code>
        {sessionId ? (
          <Button type="button" variant="ghost" size="sm" onClick={() => void copy()}>
            {copied ? 'Copied' : 'Copy ID'}
          </Button>
        ) : null}
        <Badge tone="green">active</Badge>
      </div>
      <Button type="button" variant="secondary" size="sm" onClick={() => void onNewSession()}>
        New Session
      </Button>
    </div>
  )
}
