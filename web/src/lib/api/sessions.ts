import { apiFetch } from './client'
import type { CreateSessionResponse, TurnRequest, TurnResult } from './types'

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
