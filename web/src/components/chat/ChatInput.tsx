import { useCallback, useRef } from 'react'
import { Button } from '../ui/Button'

export function ChatInput({
  onSend,
  disabled,
  sending,
}: {
  onSend: (text: string) => void | Promise<void>
  disabled?: boolean
  sending?: boolean
}) {
  const taRef = useRef<HTMLTextAreaElement>(null)

  const submit = useCallback(() => {
    const el = taRef.current
    if (!el || sending || disabled) return
    const text = el.value
    if (!text.trim()) return
    void onSend(text)
    el.value = ''
  }, [disabled, onSend, sending])

  return (
    <form
      className="border-t border-[var(--rs-border)] pt-4"
      onSubmit={(e) => {
        e.preventDefault()
        void submit()
      }}
    >
      <label htmlFor="chat-message" className="sr-only">
        Message
      </label>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
        <textarea
          id="chat-message"
          ref={taRef}
          rows={3}
          disabled={disabled || sending}
          placeholder="Type a message… (Enter to send, Shift+Enter for newline)"
          className={[
            'min-h-[5rem] w-full flex-1 resize-y rounded-[var(--rs-radius-md)] border border-[var(--rs-border)]',
            'bg-[var(--rs-surface)] px-3 py-2 text-sm text-[var(--rs-text)] placeholder:text-[var(--rs-text-muted)]/70',
            'focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--rs-accent)]',
            'disabled:cursor-not-allowed disabled:opacity-50',
          ].join(' ')}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void submit()
            }
          }}
        />
        <Button
          type="submit"
          className="shrink-0 sm:mb-0.5"
          disabled={disabled || sending}
        >
          {sending ? 'Sending…' : 'Send'}
        </Button>
      </div>
    </form>
  )
}
