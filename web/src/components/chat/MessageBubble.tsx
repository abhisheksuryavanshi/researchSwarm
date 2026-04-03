import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { StageName, Turn } from '../../lib/api/types'
import { TurnMetadata } from './TurnMetadata'

const STAGE_CONFIG: Record<StageName, { label: string; icon: string }> = {
  classifying: { label: 'Understanding your question', icon: '🧠' },
  researcher: { label: 'Searching for information', icon: '🔍' },
  analyst: { label: 'Analyzing findings', icon: '📊' },
  critic: { label: 'Evaluating quality', icon: '✓' },
  synthesizer: { label: 'Writing final answer', icon: '✍️' },
}

const STAGE_ORDER: StageName[] = ['classifying', 'researcher', 'analyst', 'critic', 'synthesizer']

function StageIndicator({ currentStage }: { currentStage: StageName | null | undefined }) {
  const activeIdx = currentStage ? STAGE_ORDER.indexOf(currentStage) : -1

  return (
    <div className="flex flex-col gap-2.5 py-1">
      {STAGE_ORDER.map((stage, i) => {
        const config = STAGE_CONFIG[stage]
        const isDone = activeIdx > i
        const isActive = activeIdx === i
        const isPending = activeIdx < i

        return (
          <div key={stage} className="flex items-center gap-2.5">
            <div
              className={[
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs transition-all duration-300',
                isDone
                  ? 'bg-[var(--rs-success)]/20 text-[var(--rs-success)]'
                  : isActive
                    ? 'bg-[var(--rs-accent)]/20 text-[var(--rs-accent)] ring-2 ring-[var(--rs-accent)]/40'
                    : 'bg-[var(--rs-border)]/40 text-[var(--rs-text-muted)]/50',
              ].join(' ')}
            >
              {isDone ? '✓' : config.icon}
            </div>
            <span
              className={[
                'text-sm transition-all duration-300',
                isDone
                  ? 'text-[var(--rs-text-muted)] line-through decoration-[var(--rs-text-muted)]/30'
                  : isActive
                    ? 'text-[var(--rs-text)] font-medium'
                    : 'text-[var(--rs-text-muted)]/50',
              ].join(' ')}
            >
              {config.label}
            </span>
            {isActive && (
              <span className="inline-flex gap-0.5">
                <span className="h-1 w-1 animate-bounce rounded-full bg-[var(--rs-accent)]" style={{ animationDelay: '0ms' }} />
                <span className="h-1 w-1 animate-bounce rounded-full bg-[var(--rs-accent)]" style={{ animationDelay: '150ms' }} />
                <span className="h-1 w-1 animate-bounce rounded-full bg-[var(--rs-accent)]" style={{ animationDelay: '300ms' }} />
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

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
        <div className="max-w-[85%] rounded-[var(--rs-radius-lg)] border border-[var(--rs-border)] bg-[var(--rs-surface)] px-4 py-3">
          <StageIndicator currentStage={turn.currentStage} />
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
