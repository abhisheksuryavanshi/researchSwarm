import { useCallback, useState } from 'react'
import { getToolStats } from '../lib/api/tools'
import { StatsOverview } from '../components/stats/StatsOverview'
import { ToolStatsTable } from '../components/stats/ToolStatsTable'
import { ErrorBanner } from '../components/ui/ErrorBanner'
import { Input } from '../components/ui/Input'
import { PageHeader } from '../components/ui/PageHeader'
import { useApi } from '../lib/hooks/useApi'

export default function StatsPage() {
  const [toolId, setToolId] = useState('')
  const [since, setSince] = useState('')

  const fetcher = useCallback(
    () =>
      getToolStats(
        toolId.trim() || undefined,
        since.trim() ? new Date(since).toISOString() : undefined,
      ),
    [toolId, since],
  )

  const { data, loading, error, refetch } = useApi(fetcher, [toolId, since])

  return (
    <div>
      <PageHeader title="Statistics" subtitle="Aggregated tool usage from the registry" />
      {error ? (
        <div className="mb-4">
          <ErrorBanner error={error} onRetry={() => void refetch()} />
        </div>
      ) : null}
      <StatsOverview data={data} loading={loading} />
      <div className="mb-4 flex flex-wrap gap-4">
        <div className="min-w-[200px] flex-1">
          <Input
            label="Filter by tool id"
            value={toolId}
            onChange={(e) => setToolId(e.target.value)}
            placeholder="optional"
          />
        </div>
        <div className="min-w-[200px] flex-1">
          <Input
            label="Since (local)"
            type="datetime-local"
            value={since}
            onChange={(e) => setSince(e.target.value)}
          />
        </div>
      </div>
      <ToolStatsTable rows={data?.stats ?? null} loading={loading} />
    </div>
  )
}
