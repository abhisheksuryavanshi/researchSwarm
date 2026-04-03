import type { ButtonHTMLAttributes, ReactNode } from 'react'

const variants = {
  primary:
    'bg-[var(--rs-accent)] text-[var(--rs-bg)] hover:opacity-90 border border-transparent',
  secondary:
    'bg-[var(--rs-surface-elevated)] text-[var(--rs-text)] border border-[var(--rs-border)] hover:bg-[var(--rs-surface)]',
  ghost: 'bg-transparent text-[var(--rs-text-muted)] hover:text-[var(--rs-text)] border border-transparent',
  danger:
    'bg-[var(--rs-danger)]/20 text-[var(--rs-danger)] border border-[var(--rs-danger)]/40 hover:bg-[var(--rs-danger)]/30',
} as const

const sizes = {
  sm: 'px-2 py-1 text-sm rounded-[var(--rs-radius-sm)]',
  md: 'px-3 py-2 text-sm rounded-[var(--rs-radius-md)]',
  lg: 'px-4 py-2.5 text-base rounded-[var(--rs-radius-md)]',
} as const

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: keyof typeof variants
  size?: keyof typeof sizes
  children: ReactNode
}

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  disabled,
  children,
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled}
      className={[
        'inline-flex items-center justify-center font-medium transition-opacity',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--rs-accent)]',
        'disabled:opacity-50 disabled:pointer-events-none',
        variants[variant],
        sizes[size],
        className,
      ].join(' ')}
      {...rest}
    >
      {children}
    </button>
  )
}
