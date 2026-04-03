import { useNavigate } from 'react-router-dom'
import type { ToolSearchResult } from '../../lib/api/types'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'

function statusTone(s: string): 'green' | 'yellow' | 'grey' {
  if (s === 'active') return 'green'
  if (s === 'degraded') return 'yellow'
  return 'grey'
}

export function ToolCard({ tool }: { tool: ToolSearchResult }) {
  const nav = useNavigate()
  const desc =
    tool.description.length > 160 ? `${tool.description.slice(0, 157)}…` : tool.description

  return (
    <Card
      role="button"
      tabIndex={0}
      className="cursor-pointer transition-colors hover:border-[var(--rs-accent)]/50"
      onClick={() => nav(`/tools/${encodeURIComponent(tool.toolId)}`)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          nav(`/tools/${encodeURIComponent(tool.toolId)}`)
        }
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-lg font-medium text-[var(--rs-text)]">{tool.name}</h3>
        <Badge tone={statusTone(tool.status)}>{tool.status}</Badge>
      </div>
      <p className="mt-2 text-sm text-[var(--rs-text-muted)]">{desc}</p>
      <div className="mt-3 flex flex-wrap gap-1">
        {tool.capabilities.slice(0, 6).map((c) => (
          <Badge key={c} tone="blue">
            {c}
          </Badge>
        ))}
        {tool.capabilities.length > 6 ? (
          <Badge tone="grey">+{tool.capabilities.length - 6}</Badge>
        ) : null}
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-xs text-[var(--rs-text-muted)]">
        <span>v{tool.version}</span>
        <span>{tool.avgLatencyMs != null ? `${Math.round(tool.avgLatencyMs)} ms avg` : '—'}</span>
      </div>
    </Card>
  )
}
