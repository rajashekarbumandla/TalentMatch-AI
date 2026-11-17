import { useCallback, useEffect, useRef, useState } from 'react'
import { getErrorMessage } from '../services/api'

/**
 * Load data from the API and track loading / error state.
 *
 *   const { data, loading, error, reload } = useApi(() => jobsApi.get(id), [id])
 *
 * - Re-fetches whenever a value in `deps` changes, or when reload() is called.
 * - While a new request is running, the previous data stays visible (no flicker).
 * - A late response from an old request is ignored, so results never arrive out of order.
 */
export function useApi(fetcher, deps = []) {
  const [reloadCount, setReloadCount] = useState(0)
  const key = JSON.stringify([deps, reloadCount])
  const [result, setResult] = useState({ key: null, data: undefined, error: null })
  const fetcherRef = useRef(fetcher)

  useEffect(() => {
    fetcherRef.current = fetcher
  })

  useEffect(() => {
    let cancelled = false
    fetcherRef.current().then(
      (data) => !cancelled && setResult({ key, data, error: null }),
      (error) => !cancelled && setResult((previous) => ({ key, data: previous.data, error: getErrorMessage(error) })),
    )
    return () => {
      cancelled = true
    }
  }, [key])

  const reload = useCallback(() => setReloadCount((count) => count + 1), [])
  return { data: result.data, error: result.error, loading: result.key !== key, reload }
}
