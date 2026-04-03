import { Link } from 'react-router-dom'
import { getToolBind } from '../../lib/api/tools'
import { useApi } from '../../lib/hooks/useApi'
import { ErrorBanner } from '../ui/ErrorBanner'
import { Skeleton } from '../ui/Skeleton'
import { HealthCheck } from '../stats/HealthCheck'

function JsonPre({ value }: { value: unknown }) {
  return (
    <pre className="max-h-96 overflow-x-auto overflow-y-auto rounded-[var(--rs-radius-md)] bg-black/35 p-3 font-mono text-xs leading-relaxed">
      <code className="text-emerald-200/90">{JSON.stringify(value ?? null, null, 2)}</code>
    </pre>
  )
}

export function ToolDetail({ toolId }: { toolId: string }) {
  const { data, loading, error, refetch } = useApi(() => getToolBind(toolId), [toolId])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-48 w-full" />
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-4">
        <ErrorBanner error={error} onRetry={() => void refetch()} />
        <Link to="/tools" className="text-sm text-[var(--rs-accent)] hover:underline">
          ← Back to catalog
        </Link>
      </div>
    )
  }

  if (!data) return null

  return (
    <div className="space-y-6">
      <Link to="/tools" className="inline-block text-sm text-[var(--rs-accent)] hover:underline">
        ← Back to catalog
      </Link>
      <div>
        <h2 className="text-2xl font-semibold text-[var(--rs-text)]">{data.name}</h2>
        <p className="mt-2 text-[var(--rs-text-muted)]">{data.description}</p>
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
        <dt className="text-[var(--rs-text-muted)]">Endpoint</dt>
        <dd className="break-all font-mono text-[var(--rs-text)]">{data.endpoint}</dd>
        <dt className="text-[var(--rs-text-muted)]">Method</dt>
        <dd className="font-mono">{data.method}</dd>
        <dt className="text-[var(--rs-text-muted)]">Version</dt>
        <dd>{data.version}</dd>
      </dl>
      <HealthCheck toolId={toolId} />
      <div>
        <h3 className="mb-2 text-sm font-medium text-[var(--rs-text)]">Arguments schema</h3>
        <JsonPre value={data.argsSchema} />
      </div>
      <div>
        <h3 className="mb-2 text-sm font-medium text-[var(--rs-text)]">Return schema</h3>
        <JsonPre value={data.returnSchema} />
      </div>
    </div>
  )
}
