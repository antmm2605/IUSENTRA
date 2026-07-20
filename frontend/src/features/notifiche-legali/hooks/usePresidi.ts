import { useCallback, useEffect, useState } from 'react'
import { classifyPresidioError, getPresidi } from '../api/presidiApi'
import type { PresidioListFilters, PresidioListPayload, PresidioResourceStatus } from '../types'

type PresidiState = {
  status: PresidioResourceStatus
  data: PresidioListPayload | null
  message: string
}

const initialState: PresidiState = {
  status: 'idle',
  data: null,
  message: '',
}

export function usePresidi(filters: PresidioListFilters) {
  const [state, setState] = useState<PresidiState>(initialState)
  const [reloadToken, setReloadToken] = useState(0)
  const refresh = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    setState((current) => ({
      ...current,
      status: current.data ? 'refreshing' : 'loading',
      message: '',
    }))

    void getPresidi(filters, controller.signal)
      .then((data) => {
        setState({ status: 'ready', data, message: '' })
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        const failure = classifyPresidioError(error)
        setState((current) => ({
          status: failure.status,
          data: current.data,
          message: failure.message,
        }))
      })

    return () => controller.abort()
  }, [filters, reloadToken])

  return {
    ...state,
    refresh,
    busy: state.status === 'loading' || state.status === 'refreshing',
  }
}
