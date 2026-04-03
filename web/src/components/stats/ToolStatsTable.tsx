import { useMemo, useState } from 'react'
import type { ToolStatsItem } from '../../lib/api/types'
import { Badge } from '../ui/Badge'
import { EmptyState } from '../ui/EmptyState'
import { Skeleton } from '../ui/Skeleton'

type SortKey = keyof Pick<
  ToolStatsItem,
  | 'name'
  | 'invocationCount'
  | 'errorRate'
  | 'avgLatencyMs'
  | 'lastInvokedAt'
>

function statusTone(s: string): 'green' | 'yellow' | 'grey' {
  if (s === 'active') return 'green'
  if (s === 'degraded') return 'yellow'
  return 'grey'
}

export function ToolStatsTable({
  rows,
  loading,
}: {
  rows: ToolStatsItem[] | null
  loading: boolean
}) {
  const [sortKey, setSortKey] = useState<SortKey>('invocationCount')
  const [dir, setDir] = useState<'asc' | 'desc'>('desc')

  const sorted = useMemo(() => {
    if (!rows) return []
    const mult = dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => {
      const va = a[sortKey]
      const vb = b[sortKey]
      if (va == null && vb == null) return 0
      if (va == null) return 1
      if (vb == null) return -1
      if (typeof va === 'number' && typeof vb === 'number') return (va - vb) * mult
      return String(va).localeCompare(String(vb)) * mult
    })
  }, [rows, sortKey, dir])

  const toggle = (k: SortKey) => {
    if (sortKey === k) setDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setSortKey(k)
      setDir('desc')
    }
  }

  if (loading) {
    return (
      <div className="overflow-x-auto rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)]">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--rs-border)]">
              <th className="p-3">Tool</th>
              <th className="p-3">Calls</th>
              <th className="p-3">Errors</th>
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-[var(--rs-border)]">
                <td className="p-3">
                  <Skeleton className="h-4 w-32" />
                </td>
                <td className="p-3">
                  <Skeleton className="h-4 w-12" />
                </td>
                <td className="p-3">
                  <Skeleton className="h-4 w-12" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (!rows?.length) {
    return (
      <EmptyState title="No statistics" description="No tool usage has been recorded for this filter." />
    )
  }

  return (
    <div className="overflow-x-auto rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)]">
      <table className="w-full min-w-[960px] text-left text-sm">
        <thead>
          <tr className="border-b border-[var(--rs-border)] bg-[var(--rs-surface-elevated)]">
            <th className="p-3">
              <button
                type="button"
                className="font-medium text-[var(--rs-accent)] hover:underline"
                onClick={() => toggle('name')}
              >
                Tool {sortKey === 'name' ? (dir === 'asc' ? '↑' : '↓') : ''}
              </button>
            </th>
            <th className="p-3">
              <button
                type="button"
                className="font-medium text-[var(--rs-accent)] hover:underline"
                onClick={() => toggle('invocationCount')}
              >
                Invocations {sortKey === 'invocationCount' ? (dir === 'asc' ? '↑' : '↓') : ''}
              </button>
            </th>
            <th className="p-3 text-[var(--rs-text-muted)]">Success</th>
            <th className="p-3 text-[var(--rs-text-muted)]">Errors</th>
            <th className="p-3">
              <button
                type="button"
                className="font-medium text-[var(--rs-accent)] hover:underline"
                onClick={() => toggle('errorRate')}
              >
                Error rate {sortKey === 'errorRate' ? (dir === 'asc' ? '↑' : '↓') : ''}
              </button>
            </th>
            <th className="p-3 text-[var(--rs-text-muted)]">Avg / p50 / p95 ms</th>
            <th className="p-3">
              <button
                type="button"
                className="font-medium text-[var(--rs-accent)] hover:underline"
                onClick={() => toggle('lastInvokedAt')}
              >
                Last invoked {sortKey === 'lastInvokedAt' ? (dir === 'asc' ? '↑' : '↓') : ''}
              </button>
            </th>
            <th className="p-3 text-[var(--rs-text-muted)]">Status</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => (
            <tr key={r.toolId} className="border-b border-[var(--rs-border)] hover:bg-[var(--rs-surface-elevated)]/50">
              <td className="p-3 font-medium text-[var(--rs-text)]">{r.name}</td>
              <td className="p-3 tabular-nums">{r.invocationCount}</td>
              <td className="p-3 tabular-nums text-emerald-300/90">{r.successCount}</td>
              <td className="p-3 tabular-nums text-red-300/90">{r.errorCount}</td>
              <td className="p-3">
                <span
                  className={
                    r.errorRate > 0.1
                      ? 'text-red-300'
                      : r.errorRate > 0.02
                        ? 'text-amber-200'
                        : 'text-[var(--rs-text-muted)]'
                  }
                >
                  {(r.errorRate * 100).toFixed(1)}%
                </span>
              </td>
              <td className="p-3 tabular-nums text-[var(--rs-text-muted)]">
                {Math.round(r.avgLatencyMs)} / {Math.round(r.p50LatencyMs)} / {Math.round(r.p95LatencyMs)}
              </td>
              <td className="p-3 text-[var(--rs-text-muted)]">
                {r.lastInvokedAt ? new Date(r.lastInvokedAt).toLocaleString() : '—'}
              </td>
              <td className="p-3">
                <Badge tone={statusTone(r.status)}>{r.status}</Badge>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
