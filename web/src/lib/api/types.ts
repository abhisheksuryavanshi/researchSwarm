export interface CreateSessionResponse {
  sessionId: string
  status: string
  expiresAt: string
}

export interface TurnRequest {
  message: string
}

export interface TurnResult {
  turnIndex: number
  assistantMessage: string
  intent: string
  intentConfidence: number
  degradedMode: boolean
  traceId: string
  routeMode: string | null
  engineEntry: string | null
}

export interface ToolSearchResult {
  toolId: string
  name: string
  description: string
  capabilities: string[]
  version: string
  status: string
  avgLatencyMs: number
}

export interface ToolSearchResponse {
  results: ToolSearchResult[]
  total: number
  capabilityFilter: string | null
}

export interface ToolBindResponse {
  name: string
  description: string
  argsSchema: Record<string, unknown>
  endpoint: string
  method: string
  version: string
  returnSchema: Record<string, unknown>
}

export interface ToolHealthResponse {
  toolId: string
  status: string
  latencyMs: number | null
  checkedAt: string
  endpointChecked: string | null
  message: string | null
  error: string | null
}

export interface ToolStatsItem {
  toolId: string
  name: string
  invocationCount: number
  successCount: number
  errorCount: number
  errorRate: number
  avgLatencyMs: number
  p50LatencyMs: number
  p95LatencyMs: number
  lastInvokedAt: string | null
  status: string
}

export interface ToolStatsResponse {
  stats: ToolStatsItem[]
  totalTools: number
  totalInvocations: number
  since: string | null
}

export type ApiErrorType =
  | 'network'
  | 'session_not_found'
  | 'session_degraded'
  | 'server_error'
  | 'validation_error'
  | 'unknown'

export interface ApiError {
  type: ApiErrorType
  message: string
  status: number | null
  detail: string | null
}

export interface StoredSession {
  sessionId: string
  principalId: string
  createdAt: string
  expiresAt: string
}

export type StageName = 'classifying' | 'researcher' | 'analyst' | 'critic' | 'synthesizer'

export interface Turn {
  turnIndex: number
  userMessage: string
  assistantMessage: string
  intent: string
  intentConfidence: number
  degradedMode: boolean
  traceId: string
  routeMode: string | null
  engineEntry: string | null
  timestamp: string
  /** True while waiting for POST /turns response */
  awaitingAssistant?: boolean
  /** Current processing stage (while awaitingAssistant) */
  currentStage?: StageName | null
}
