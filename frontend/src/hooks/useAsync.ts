import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../lib/format'

export interface AsyncState<T> {
  data: T | null
  error: string | null
  loading: boolean
  reload: () => Promise<void>
  setData: (updater: T | null | ((prev: T | null) => T | null)) => void
}

/**
 * Загрузка данных с состоянием loading/error и перезагрузкой.
 * deps — зависимости, при изменении которых запрос повторяется.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const fnRef = useRef(fn)
  fnRef.current = fn
  // счётчик защищает от гонки: устаревший ответ не перезапишет свежий
  const seq = useRef(0)

  const run = useCallback(async () => {
    const id = ++seq.current
    setLoading(true)
    setError(null)
    try {
      const res = await fnRef.current()
      if (id === seq.current) setData(res)
    } catch (e) {
      if (id === seq.current) setError(errorMessage(e, 'Не удалось загрузить данные'))
    } finally {
      if (id === seq.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    void run()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, error, loading, reload: run, setData }
}
