import { useEffect, useState } from 'react'
import { Button } from '../ui/Button'
import { Input } from '../ui/Input'

export function ToolSearch({
  onDebouncedChange,
  resultCount,
}: {
  onDebouncedChange: (capability: string) => void
  resultCount: number | null
}) {
  const [local, setLocal] = useState('')

  useEffect(() => {
    const t = window.setTimeout(() => onDebouncedChange(local), 300)
    return () => window.clearTimeout(t)
  }, [local, onDebouncedChange])

  return (
    <div className="mb-6 flex flex-wrap items-end gap-3">
      <div className="min-w-[200px] flex-1">
        <Input
          label="Search by capability"
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          placeholder="e.g. web_search"
        />
      </div>
      {local ? (
        <Button type="button" variant="ghost" size="sm" onClick={() => setLocal('')}>
          Clear
        </Button>
      ) : null}
      {resultCount !== null ? (
        <span className="text-sm text-[var(--rs-text-muted)]">{resultCount} result(s)</span>
      ) : null}
    </div>
  )
}
