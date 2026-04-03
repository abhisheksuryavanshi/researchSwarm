import { apiFetch } from './client'
import type {
  ToolBindResponse,
  ToolHealthResponse,
  ToolSearchResponse,
  ToolStatsResponse,
} from './types'

export function searchTools(capability?: string, limit = 10): Promise<ToolSearchResponse> {
  const q = new URLSearchParams()
  if (capability?.trim()) q.set('capability', capability.trim())
  q.set('limit', String(Math.min(50, Math.max(1, limit))))
  const qs = q.toString()
  return apiFetch<ToolSearchResponse>(`/tools/search?${qs}`)
}

export function getToolBind(toolId: string): Promise<ToolBindResponse> {
  return apiFetch<ToolBindResponse>(`/tools/${encodeURIComponent(toolId)}/bind`)
}

export function getToolHealth(toolId: string): Promise<ToolHealthResponse> {
  return apiFetch<ToolHealthResponse>(`/tools/${encodeURIComponent(toolId)}/health`)
}

export function getToolStats(
  toolId?: string,
  since?: string | null,
): Promise<ToolStatsResponse> {
  const q = new URLSearchParams()
  if (toolId?.trim()) q.set('tool_id', toolId.trim())
  if (since?.trim()) q.set('since', since.trim())
  const qs = q.toString()
  const path = qs ? `/tools/stats?${qs}` : '/tools/stats'
  return apiFetch<ToolStatsResponse>(path)
}
