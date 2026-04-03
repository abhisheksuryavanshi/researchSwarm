import type { ApiError, ApiErrorType } from './types'

/** API origin. In dev, default '' uses Vite proxy (same origin as the UI → avoids CORS). */
function resolveApiBase(): string {
  const raw = import.meta.env.VITE_API_BASE_URL as string | undefined
  if (raw !== undefined && raw.trim() !== '') {
    return raw.replace(/\/$/, '')
  }
  if (import.meta.env.DEV) {
    return ''
  }
  return 'http://localhost:8000'
}

const API_BASE = resolveApiBase()

export class FetchApiError extends Error {
  readonly apiError: ApiError

  constructor(apiError: ApiError) {
    super(apiError.message)
    this.name = 'FetchApiError'
    this.apiError = apiError
  }
}

function snakeToCamelKey(key: string): string {
  return key.replace(/_([a-z])/g, (_, c: string) => c.toUpperCase())
}

export function keysToCamel<T>(value: unknown): T {
  if (value === null || value === undefined) return value as T
  if (Array.isArray(value)) {
    return value.map((v) => keysToCamel(v)) as T
  }
  if (typeof value === 'object' && value.constructor === Object) {
    const out: Record<string, unknown> = {}
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[snakeToCamelKey(k)] = keysToCamel(v)
    }
    return out as T
  }
  return value as T
}

function normalizeApiError(
  status: number,
  body: unknown,
  fallbackDetail: string | null,
): ApiError {
  const detailStr =
    typeof body === 'object' && body !== null && 'detail' in body
      ? String((body as { detail: unknown }).detail)
      : fallbackDetail

  let errCode: string | undefined
  if (typeof body === 'object' && body !== null && 'error' in body) {
    errCode = String((body as { error: unknown }).error)
  }

  let type: ApiErrorType = 'unknown'
  let message = 'An unexpected error occurred.'

  if (status === 404 && errCode === 'session_not_found') {
    type = 'session_not_found'
    message = 'Your session has expired or is no longer valid.'
  } else if (status === 503) {
    if (errCode === 'session_degraded') {
      type = 'session_degraded'
      message =
        'The system is temporarily operating in degraded mode. Your request may still complete.'
    } else {
      type = 'server_error'
      message = 'Backend not ready — conversation service is starting up'
    }
  } else if (status >= 500) {
    type = 'server_error'
    message = 'Something went wrong on the server. Please try again in a moment.'
  } else if (status === 422) {
    type = 'validation_error'
    message = 'Invalid request. Please check your input.'
  }

  return { type, message, status, detail: detailStr }
}

export interface ApiFetchOptions {
  method?: string
  body?: unknown
  principalId?: string | null
  sessionId?: string | null
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const { method = 'GET', body, principalId, sessionId } = options
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`

  const headers: Record<string, string> = {
    'X-Trace-ID': crypto.randomUUID(),
  }
  if (principalId) {
    headers.Authorization = `Bearer ${principalId}`
  }
  if (sessionId) {
    headers['X-Session-ID'] = sessionId
  }
  if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  let res: Response
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch (cause) {
    if (import.meta.env.DEV) {
      console.warn('[apiFetch] network error', {
        url,
        apiBase: API_BASE || '(Vite proxy → :8000)',
        cause,
        hint: API_BASE
          ? 'If the API is up, add this page’s origin to CORS_ORIGINS (localhost vs 127.0.0.1 differ).'
          : 'Ensure Uvicorn is running on port 8000 (e.g. ./setup.sh).',
      })
    }
    throw new FetchApiError({
      type: 'network',
      message:
        'Unable to reach the server. Check that the API is running on port 8000 and your browser console for details.',
      status: null,
      detail: cause instanceof Error ? cause.message : null,
    })
  }

  const text = await res.text()
  let parsed: unknown = null
  if (text) {
    try {
      parsed = JSON.parse(text) as unknown
    } catch {
      parsed = text
    }
  }

  if (!res.ok) {
    const apiErr = normalizeApiError(res.status, parsed, typeof parsed === 'string' ? parsed : null)
    throw new FetchApiError(apiErr)
  }

  return keysToCamel<T>(parsed)
}

export { API_BASE }
