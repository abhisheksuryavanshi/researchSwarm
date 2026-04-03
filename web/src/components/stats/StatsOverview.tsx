import type { ToolStatsResponse } from '../../lib/api/types'
import { Card } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'

export function StatsOverview({
  data,
  loading,
}: {
  data: ToolStatsResponse | null
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    )
  }
  if (!data) return null
  return (
    <div className="mb-6 grid gap-4 sm:grid-cols-2">
      <Card>
        <p className="text-sm text-[var(--rs-text-muted)]">Total tools</p>
        <p className="mt-1 text-3xl font-semibold text-[var(--rs-text)]">{data.totalTools}</p>
      </Card>
      <Card>
        <p className="text-sm text-[var(--rs-text-muted)]">Total invocations</p>
        <p className="mt-1 text-3xl font-semibold text-[var(--rs-text)]">{data.totalInvocations}</p>
      </Card>
    </div>
  )
}
