import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from './ui/Button'

export class GlobalErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean }
> {
  state = { hasError: false }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('GlobalErrorBoundary', error, info.componentStack)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex min-h-full flex-col items-center justify-center gap-4 p-8 text-center">
          <h1 className="text-xl font-semibold text-[var(--rs-text)]">Something went wrong</h1>
          <p className="max-w-md text-sm text-[var(--rs-text-muted)]">
            The UI hit an unexpected error. You can reload the page to try again.
          </p>
          <Button type="button" onClick={() => window.location.reload()}>
            Reload
          </Button>
        </div>
      )
    }
    return this.props.children
  }
}
