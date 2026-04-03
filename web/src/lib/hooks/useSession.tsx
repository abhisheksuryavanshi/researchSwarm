import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { FetchApiError } from '../api/client'
import { createSession } from '../api/sessions'
import type { ApiError } from '../api/types'
import { isStoragePersistent, sessionStore } from '../session-store'

interface SessionContextValue {
  sessionId: string | null
  principalId: string | null
  isReady: boolean
  error: ApiError | null
  isStoragePersistent: boolean
  createNewSession: () => Promise<void>
  recoverSession: () => Promise<void>
  retryBootstrap: () => Promise<void>
  notifySessionNotFound: () => void
  clearSessionError: () => void
}

const SessionContext = createContext<SessionContextValue | null>(null)

async function persistNewSession(principalId: string) {
  const res = await createSession(principalId)
  sessionStore.set({
    sessionId: res.sessionId,
    principalId,
    createdAt: new Date().toISOString(),
    expiresAt: res.expiresAt,
  })
  return res.sessionId
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [principalId, setPrincipalId] = useState<string | null>(null)
  const [isReady, setIsReady] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const [storageOk] = useState(() => isStoragePersistent())

  const bootstrap = useCallback(async () => {
    setIsReady(false)
    const pid = sessionStore.ensurePrincipalId()
    setPrincipalId(pid)
    const stored = sessionStore.get()
    if (stored?.sessionId) {
      setSessionId(stored.sessionId)
      setError(null)
      setIsReady(true)
      return
    }
    try {
      const sid = await persistNewSession(pid)
      setSessionId(sid)
      setError(null)
    } catch (e) {
      if (e instanceof FetchApiError) {
        setError(e.apiError)
      } else {
        setError({
          type: 'unknown',
          message: 'An unexpected error occurred.',
          status: null,
          detail: e instanceof Error ? e.message : String(e),
        })
      }
    } finally {
      setIsReady(true)
    }
  }, [])

  useEffect(() => {
    void bootstrap()
  }, [bootstrap])

  const createNewSession = useCallback(async () => {
    const pid = principalId ?? sessionStore.ensurePrincipalId()
    setPrincipalId(pid)
    setError(null)
    try {
      const sid = await persistNewSession(pid)
      setSessionId(sid)
    } catch (e) {
      if (e instanceof FetchApiError) {
        setError(e.apiError)
      } else {
        setError({
          type: 'unknown',
          message: 'An unexpected error occurred.',
          status: null,
          detail: e instanceof Error ? e.message : String(e),
        })
      }
    }
  }, [principalId])

  const recoverSession = useCallback(async () => {
    setError(null)
    sessionStore.clearServerSession()
    setSessionId(null)
    const pid = sessionStore.ensurePrincipalId()
    setPrincipalId(pid)
    try {
      const sid = await persistNewSession(pid)
      setSessionId(sid)
    } catch (e) {
      if (e instanceof FetchApiError) {
        setError(e.apiError)
      } else {
        setError({
          type: 'unknown',
          message: 'An unexpected error occurred.',
          status: null,
          detail: e instanceof Error ? e.message : String(e),
        })
      }
    }
  }, [])

  const notifySessionNotFound = useCallback(() => {
    sessionStore.clearServerSession()
    setSessionId(null)
    setError({
      type: 'session_not_found',
      message: 'Your session has expired or is no longer valid.',
      status: 404,
      detail: null,
    })
  }, [])

  const clearSessionError = useCallback(() => {
    setError(null)
  }, [])

  const retryBootstrap = useCallback(async () => {
    setError(null)
    await bootstrap()
  }, [bootstrap])

  const value = useMemo(
    () => ({
      sessionId,
      principalId,
      isReady,
      error,
      isStoragePersistent: storageOk,
      createNewSession,
      recoverSession,
      retryBootstrap,
      notifySessionNotFound,
      clearSessionError,
    }),
    [
      sessionId,
      principalId,
      isReady,
      error,
      storageOk,
      createNewSession,
      recoverSession,
      retryBootstrap,
      notifySessionNotFound,
      clearSessionError,
    ],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const ctx = useContext(SessionContext)
  if (!ctx) {
    throw new Error('useSession must be used within SessionProvider')
  }
  return ctx
}
