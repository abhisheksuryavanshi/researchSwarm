import { useCallback, useState } from 'react'
import { searchTools } from '../../lib/api/tools'
import { useApi } from '../../lib/hooks/useApi'
import { EmptyState } from '../ui/EmptyState'
import { ErrorBanner } from '../ui/ErrorBanner'
import { Skeleton } from '../ui/Skeleton'
import { ToolCard } from './ToolCard'
import { ToolSearch } from './ToolSearch'

export function ToolCatalog() {
  const [capability, setCapability] = useState('')
  const fetcher = useCallback(() => searchTools(capability || undefined, 50), [capability])
  const { data, loading, error, refetch } = useApi(fetcher, [capability])

  return (
    <div>
      <ToolSearch onDebouncedChange={setCapability} resultCount={data?.total ?? null} />
      {error ? (
        <div className="mb-4">
          <ErrorBanner error={error} onRetry={() => void refetch()} />
        </div>
      ) : null}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-40 w-full" />
          ))}
        </div>
      ) : data?.results.length === 0 ? (
        <EmptyState
          title="No tools found"
          description="Try a different capability keyword or clear the search to see all tools."
          actionLabel="Retry"
          onAction={() => void refetch()}
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data?.results.map((t) => (
            <ToolCard key={t.toolId} tool={t} />
          ))}
        </div>
      )}
    </div>
  )
}
