import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Turn } from '../../lib/api/types'
import { Skeleton } from '../ui/Skeleton'
import { TurnMetadata } from './TurnMetadata'

export function MessageBubble({ turn, role }: { turn: Turn; role: 'operator' | 'assistant' }) {
  const time = new Date(turn.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  })

  if (role === 'operator') {
    return (
      <div className="flex justify-end">
        <div
          className="max-w-[85%] rounded-[var(--rs-radius-lg)] bg-[var(--rs-surface-elevated)] px-4 py-3 text-left text-[var(--rs-text)]"
        >
          <p className="whitespace-pre-wrap text-sm">{turn.userMessage}</p>
          <p className="mt-2 text-right text-xs text-[var(--rs-text-muted)]">{time}</p>
        </div>
      </div>
    )
  }

  if (turn.awaitingAssistant) {
    return (
      <div className="flex justify-start">
        <div className="max-w-[85%] space-y-2 rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)] bg-[var(--rs-surface)] px-4 py-3">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-3 w-4/5" />
          <Skeleton className="h-3 w-2/3" />
        </div>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)] bg-[var(--rs-surface)] px-4 py-3 text-left">
        <div className="prose prose-invert prose-sm max-w-none prose-chat prose-p:my-2 prose-headings:my-3">
          <Markdown remarkPlugins={[remarkGfm]}>{turn.assistantMessage}</Markdown>
        </div>
        <TurnMetadata turn={turn} />
        <p className="mt-2 text-xs text-[var(--rs-text-muted)]">{time}</p>
      </div>
    </div>
  )
}
