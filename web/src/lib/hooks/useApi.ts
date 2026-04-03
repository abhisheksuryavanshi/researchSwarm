import { useCallback, useEffect, useState } from 'react'
import { FetchApiError } from '../api/client'
import type { ApiError } from '../api/types'

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: React.DependencyList,
): {
  data: T | null
  loading: boolean
  error: ApiError | null
  refetch: () => Promise<void>
} {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<ApiError | null>(null)

  const refetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await fetcher()
      setData(result)
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
      setLoading(false)
    }
    // fetcher is intentionally excluded; caller supplies deps that cover closed-over values.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    void refetch()
  }, [refetch])

  return { data, loading, error, refetch }
}
