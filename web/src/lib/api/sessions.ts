import { API_BASE, FetchApiError, keysToCamel } from './client'
import type { CreateSessionResponse, StageName, TurnRequest, TurnResult } from './types'
import { apiFetch } from './client'

export function createSession(principalId: string): Promise<CreateSessionResponse> {
  return apiFetch<CreateSessionResponse>('/v1/sessions', {
    method: 'POST',
    principalId,
  })
}

export function postTurn(
  sessionId: string,
  principalId: string,
  message: string,
): Promise<TurnResult> {
  const body: TurnRequest = { message }
  return apiFetch<TurnResult>(`/v1/sessions/${encodeURIComponent(sessionId)}/turns`, {
    method: 'POST',
    body,
    principalId,
    sessionId,
  })
}

export async function postTurnStreaming(
  sessionId: string,
  principalId: string,
  message: string,
  onStage: (stage: StageName) => void,
): Promise<TurnResult> {
  const url = `${API_BASE}/v1/sessions/${encodeURIComponent(sessionId)}/turns`
  const body: TurnRequest = { message }

  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${principalId}`,
      'X-Trace-ID': crypto.randomUUID(),
      'X-Session-ID': sessionId,
    },
    body: JSON.stringify(body),
  })

  if (!res.ok || !res.body) {
    const text = await res.text()
    let parsed: unknown = null
    try { parsed = JSON.parse(text) } catch { parsed = text }
    throw new FetchApiError({
      type: res.status === 404 ? 'session_not_found' : 'server_error',
      message: typeof parsed === 'object' && parsed !== null && 'detail' in parsed
        ? String((parsed as Record<string, unknown>).detail)
        : 'Server error',
      status: res.status,
      detail: null,
    })
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let finalResult: TurnResult | null = null

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const parts = buffer.split('\n\n')
    buffer = parts.pop() ?? ''

    for (const part of parts) {
      const lines = part.trim().split('\n')
      let eventType = ''
      let data = ''
      for (const line of lines) {
        if (line.startsWith('event: ')) eventType = line.slice(7)
        else if (line.startsWith('data: ')) data = line.slice(6)
      }
      if (!eventType || !data) continue

      if (eventType === 'status') {
        try {
          const evt = JSON.parse(data) as { stage: string }
          onStage(evt.stage as StageName)
        } catch { /* ignore malformed */ }
      } else if (eventType === 'result') {
        try {
          finalResult = keysToCamel<TurnResult>(JSON.parse(data))
        } catch { /* ignore */ }
      } else if (eventType === 'error') {
        try {
          const err = JSON.parse(data) as Record<string, unknown>
          throw new FetchApiError({
            type: err.error === 'session_not_found' ? 'session_not_found' : 'server_error',
            message: String(err.message ?? err.detail ?? 'Server error'),
            status: null,
            detail: null,
          })
        } catch (e) {
          if (e instanceof FetchApiError) throw e
          throw new FetchApiError({
            type: 'server_error',
            message: 'Stream error',
            status: null,
            detail: null,
          })
        }
      }
    }
  }

  if (!finalResult) {
    throw new FetchApiError({
      type: 'server_error',
      message: 'Stream ended without a result',
      status: null,
      detail: null,
    })
  }

  return finalResult
}
