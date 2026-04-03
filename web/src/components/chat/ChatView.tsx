import { useEffect, useRef, useState } from 'react'
import { FetchApiError } from '../../lib/api/client'
import { postTurnStreaming } from '../../lib/api/sessions'
import type { StageName, Turn, TurnResult } from '../../lib/api/types'
import { useSession } from '../../lib/hooks/useSession'
import { Button } from '../ui/Button'
import { ErrorBanner } from '../ui/ErrorBanner'
import { ChatInput } from './ChatInput'
import { MessageBubble } from './MessageBubble'
import { SessionHeader } from './SessionHeader'

function turnFromResponse(
  userMessage: string,
  r: TurnResult,
  timestamp: string,
): Turn {
  return {
    turnIndex: r.turnIndex,
    userMessage,
    assistantMessage: r.assistantMessage,
    intent: r.intent,
    intentConfidence: r.intentConfidence,
    degradedMode: r.degradedMode,
    traceId: r.traceId,
    routeMode: r.routeMode,
    engineEntry: r.engineEntry,
    timestamp,
  }
}

export function ChatView() {
  const {
    sessionId,
    principalId,
    createNewSession,
    recoverSession,
    error: sessionError,
    notifySessionNotFound,
    isStoragePersistent,
  } = useSession()
  const [turns, setTurns] = useState<Turn[]>([])
  const [sending, setSending] = useState(false)
  const [sendError, setSendError] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setTurns([])
  }, [sessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [turns])

  const onSend = async (text: string) => {
    const trimmed = text.trim()
    if (!trimmed || !sessionId || !principalId || sending) return
    setSendError(null)
    const ts = new Date().toISOString()
    const pending: Turn = {
      turnIndex: turns.length,
      userMessage: trimmed,
      assistantMessage: '',
      intent: '',
      intentConfidence: 0,
      degradedMode: false,
      traceId: '',
      routeMode: null,
      engineEntry: null,
      timestamp: ts,
      awaitingAssistant: true,
      currentStage: null,
    }
    setTurns((t) => [...t, pending])
    setSending(true)
    try {
      const result = await postTurnStreaming(
        sessionId,
        principalId,
        trimmed,
        (stage: StageName) => {
          setTurns((t) => {
            const next = [...t]
            const i = next.findIndex((x) => x.timestamp === ts && x.awaitingAssistant)
            if (i >= 0) {
              next[i] = { ...next[i], currentStage: stage }
            }
            return next
          })
        },
      )
      setTurns((t) => {
        const next = [...t]
        const i = next.findIndex((x) => x.timestamp === ts && x.awaitingAssistant)
        if (i >= 0) {
          next[i] = turnFromResponse(trimmed, result, ts)
        }
        return next
      })
    } catch (e) {
      setTurns((t) => t.filter((x) => !(x.timestamp === ts && x.awaitingAssistant)))
      if (e instanceof FetchApiError && e.apiError.type === 'session_not_found') {
        notifySessionNotFound()
      } else if (e instanceof FetchApiError) {
        setSendError(e.apiError.message)
      } else {
        setSendError('An unexpected error occurred.')
      }
    } finally {
      setSending(false)
    }
  }

  const sessionExpired = sessionError?.type === 'session_not_found'

  return (
    <div className="relative flex h-[calc(100vh-8rem)] min-h-[420px] flex-col">
      {!isStoragePersistent ? (
        <p className="mb-2 rounded-[var(--rs-radius-md)] border border-[var(--rs-border)] bg-[var(--rs-surface-elevated)] px-3 py-2 text-sm text-[var(--rs-text-muted)]">
          Session won&apos;t persist across visits — storage is unavailable in this browser context.
        </p>
      ) : null}

      <SessionHeader
        sessionId={sessionId}
        loading={false}
        onNewSession={async () => {
          setTurns([])
          await createNewSession()
        }}
      />

      {sendError ? (
        <div className="mb-2">
          <ErrorBanner
            error={{ type: 'unknown', message: sendError, status: null, detail: null }}
            onDismiss={() => setSendError(null)}
          />
        </div>
      ) : null}

      <div className="relative flex min-h-0 flex-1 flex-col">
        {sessionExpired ? (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-4 bg-[var(--rs-bg)]/90 p-6">
            <ErrorBanner
              error={{
                type: 'session_not_found',
                message: 'Your session has expired.',
                status: 404,
                detail: null,
              }}
            />
            <Button type="button" onClick={() => void recoverSession()}>
              Start New Session
            </Button>
          </div>
        ) : null}

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto pr-1">
          {turns.length === 0 ? (
            <p className="py-8 text-center text-sm text-[var(--rs-text-muted)]">
              Send a message to start the conversation.
            </p>
          ) : null}
          {turns.map((turn) => (
            <div key={`${turn.timestamp}-${turn.turnIndex}`} className="space-y-3">
              <MessageBubble turn={turn} role="operator" />
              <MessageBubble turn={turn} role="assistant" />
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <ChatInput onSend={onSend} disabled={!sessionId || sessionExpired} sending={sending} />
      </div>
    </div>
  )
}
