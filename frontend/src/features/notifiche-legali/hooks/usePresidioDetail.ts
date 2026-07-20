import { useCallback, useEffect, useState } from 'react'
import {
  classifyPresidioError,
  getPresidio,
  getPresidioEvidence,
  getPresidioTransitions,
} from '../api/presidiApi'
import type {
  PresidioDetailPayload,
  PresidioEvidencePayload,
  PresidioResourceStatus,
  PresidioTransitionsPayload,
} from '../types'

export type PresidioDetailData = {
  detail: PresidioDetailPayload
  evidence: PresidioEvidencePayload
  transitions: PresidioTransitionsPayload
}

type DetailState = {
  status: PresidioResourceStatus
  data: PresidioDetailData | null
  message: string
}

const initialState: DetailState = {
  status: 'idle',
  data: null,
  message: '',
}

export function usePresidioDetail(id: string | null) {
  const [state, setState] = useState<DetailState>(initialState)
  const [reloadToken, setReloadToken] = useState(0)
  const refresh = useCallback(() => setReloadToken((value) => value + 1), [])

  useEffect(() => {
    if (!id) {
      setState(initialState)
      return undefined
    }

    const controller = new AbortController()
    setState((current) => ({
      ...current,
      status: current.data ? 'refreshing' : 'loading',
      message: '',
    }))

    void Promise.all([
      getPresidio(id, controller.signal),
      getPresidioEvidence(id, controller.signal),
      getPresidioTransitions(id, controller.signal),
    ])
      .then(([detail, evidence, transitions]) => {
        setState({
          status: 'ready',
          data: { detail, evidence, transitions },
          message: '',
        })
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
  }, [id, reloadToken])

  return {
    ...state,
    refresh,
    busy: state.status === 'loading' || state.status === 'refreshing',
  }
}
