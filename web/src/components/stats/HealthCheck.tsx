import { useState } from 'react'
import { FetchApiError } from '../../lib/api/client'
import { getToolHealth } from '../../lib/api/tools'
import type { ToolHealthResponse } from '../../lib/api/types'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'

function healthTone(
  s: string,
): 'green' | 'yellow' | 'red' | 'grey' {
  if (s === 'healthy') return 'green'
  if (s === 'degraded') return 'yellow'
  if (s === 'unhealthy') return 'red'
  return 'grey'
}

export function HealthCheck({ toolId }: { toolId: string }) {
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<ToolHealthResponse | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const run = async () => {
    setLoading(true)
    setErr(null)
    try {
      const r = await getToolHealth(toolId)
      setResult(r)
    } catch (e) {
      if (e instanceof FetchApiError) {
        setErr(e.apiError.message)
      } else {
        setErr('Health check failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-[var(--rs-radius-md)] border border-[var(--rs-border)] bg-[var(--rs-surface-elevated)] p-4">
      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="secondary" size="sm" disabled={loading} onClick={() => void run()}>
          {loading ? 'Checking…' : 'Check Health'}
        </Button>
        {result ? (
          <>
            <Badge tone={healthTone(result.status)}>{result.status}</Badge>
            {result.latencyMs != null ? (
              <span className="text-sm text-[var(--rs-text-muted)]">{result.latencyMs} ms</span>
            ) : null}
            <span className="text-xs text-[var(--rs-text-muted)]">
              {new Date(result.checkedAt).toLocaleString()}
            </span>
          </>
        ) : null}
      </div>
      {err ? <p className="mt-2 text-sm text-[var(--rs-danger)]">{err}</p> : null}
      {result?.message ? (
        <p className="mt-2 text-sm text-[var(--rs-text-muted)]">{result.message}</p>
      ) : null}
      {result?.error ? (
        <p className="mt-2 text-sm text-[var(--rs-danger)]">{result.error}</p>
      ) : null}
    </div>
  )
}
