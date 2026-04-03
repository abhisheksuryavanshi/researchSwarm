import { useState } from 'react'
import type { Turn } from '../../lib/api/types'
import { Badge } from '../ui/Badge'

export function TurnMetadata({ turn }: { turn: Turn }) {
  const [open, setOpen] = useState(false)
  if (turn.awaitingAssistant || !turn.traceId) {
    return null
  }
  const confPct = Math.round(turn.intentConfidence * 100)
  const traceShort =
    turn.traceId.length > 12 ? `${turn.traceId.slice(0, 8)}…${turn.traceId.slice(-4)}` : turn.traceId

  return (
    <div className="mt-2 text-xs text-[var(--rs-text-muted)]">
      <button
        type="button"
        className="flex w-full items-center justify-between rounded-[var(--rs-radius-sm)] py-1 text-left hover:bg-[var(--rs-surface-elevated)]/80"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span>Metadata</span>
        <span className="text-[var(--rs-text-muted)]">{open ? '▼' : '▶'}</span>
      </button>
      {open ? (
        <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 border-t border-[var(--rs-border)] pt-2">
          <dt className="text-[var(--rs-text-muted)]">Intent</dt>
          <dd className="font-mono text-[var(--rs-text)]">{turn.intent}</dd>
          <dt className="text-[var(--rs-text-muted)]">Confidence</dt>
          <dd>{confPct}%</dd>
          <dt className="text-[var(--rs-text-muted)]">Trace</dt>
          <dd className="font-mono">{traceShort}</dd>
          {turn.routeMode ? (
            <>
              <dt className="text-[var(--rs-text-muted)]">Route</dt>
              <dd className="font-mono">{turn.routeMode}</dd>
            </>
          ) : null}
          {turn.engineEntry ? (
            <>
              <dt className="text-[var(--rs-text-muted)]">Engine</dt>
              <dd className="font-mono">{turn.engineEntry}</dd>
            </>
          ) : null}
          <dt className="text-[var(--rs-text-muted)]">Degraded</dt>
          <dd>
            {turn.degradedMode ? (
              <div className="flex flex-col gap-1">
                <Badge tone="yellow">degraded</Badge>
                <span className="text-[var(--rs-warning)]/90">
                  Response generated in degraded mode — results may be limited.
                </span>
              </div>
            ) : (
              <span>no</span>
            )}
          </dd>
        </dl>
      ) : (
        <div className="mt-1 flex flex-wrap gap-2">
          <Badge tone="blue">{turn.intent}</Badge>
          <span>{confPct}%</span>
          <code className="rounded bg-[var(--rs-surface-elevated)] px-1 font-mono">{traceShort}</code>
          {turn.degradedMode ? <Badge tone="yellow">degraded</Badge> : null}
        </div>
      )}
    </div>
  )
}
