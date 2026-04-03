import type { InputHTMLAttributes } from 'react'

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string | null
}

export function Input({ label, error, id, className = '', disabled, ...rest }: InputProps) {
  const inputId = id ?? rest.name ?? 'input-field'
  return (
    <div className="flex flex-col gap-1 w-full">
      {label ? (
        <label htmlFor={inputId} className="text-sm text-[var(--rs-text-muted)]">
          {label}
        </label>
      ) : null}
      <input
        id={inputId}
        disabled={disabled}
        className={[
          'w-full rounded-[var(--rs-radius-md)] border bg-[var(--rs-surface)] px-3 py-2 text-[var(--rs-text)]',
          'placeholder:text-[var(--rs-text-muted)]/70',
          'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-0 focus-visible:outline-[var(--rs-accent)]',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          error ? 'border-[var(--rs-danger)]' : 'border-[var(--rs-border)]',
          className,
        ].join(' ')}
        {...rest}
      />
      {error ? <p className="text-sm text-[var(--rs-danger)]">{error}</p> : null}
    </div>
  )
}
