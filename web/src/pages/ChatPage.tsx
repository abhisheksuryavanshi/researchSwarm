import { ChatView } from '../components/chat/ChatView'
import { ErrorBanner } from '../components/ui/ErrorBanner'
import { PageHeader } from '../components/ui/PageHeader'
import { Skeleton } from '../components/ui/Skeleton'
import { useSession } from '../lib/hooks/useSession'

export default function ChatPage() {
  const { isReady, error, sessionId, retryBootstrap, clearSessionError } = useSession()

  if (!isReady) {
    return (
      <div>
        <PageHeader title="Chat" subtitle="Conversational session with the research coordinator" />
        <div className="space-y-4">
          <Skeleton className="h-10 w-full max-w-xl" />
          <Skeleton className="h-64 w-full" />
          <Skeleton className="h-24 w-full" />
        </div>
      </div>
    )
  }

  if (error && !sessionId) {
    return (
      <div>
        <PageHeader title="Chat" subtitle="Conversational session with the research coordinator" />
        <ErrorBanner error={error} onRetry={() => void retryBootstrap()} />
      </div>
    )
  }

  return (
    <div>
      <PageHeader title="Chat" subtitle="Conversational session with the research coordinator" />
      {error && error.type !== 'session_not_found' ? (
        <div className="mb-4">
          <ErrorBanner error={error} onDismiss={clearSessionError} />
        </div>
      ) : null}
      <ChatView />
    </div>
  )
}
