import { useCallback, useEffect, useRef, useState, useSyncExternalStore, type RefObject } from 'react'
import { SupportCustomerController } from './controller'
import type { SupportCustomerBootstrap, SupportCustomerSession, SupportCustomerViewState } from './types'

const PAGE_FULLSCREEN_CLASS = 'support-customer-page--fullscreen'

export type SupportCustomerRoomApi = {
  state: SupportCustomerViewState
  controller: SupportCustomerController
  shellRef: RefObject<HTMLElement | null>
  remoteAudioRef: (element: HTMLAudioElement | null) => void
  toggleFullscreen: () => void
}

/**
 * Collega il controller della stanza cliente al ciclo di vita React.
 * Il controller nasce una sola volta (anche in StrictMode) e si monta/smonta
 * con l'effetto: timer, WebSocket, WebRTC e flussi vengono sempre rilasciati.
 */
export function useSupportCustomerRoom(
  bootstrap: SupportCustomerBootstrap,
  session: SupportCustomerSession,
): SupportCustomerRoomApi {
  const [controller] = useState(() => new SupportCustomerController(bootstrap, session))
  const state = useSyncExternalStore(controller.store.subscribe, controller.store.getSnapshot, controller.store.getSnapshot)
  const shellRef = useRef<HTMLElement | null>(null)

  useEffect(() => {
    controller.mount()
    return () => controller.unmount()
  }, [controller])

  useEffect(() => {
    document.body.classList.toggle(PAGE_FULLSCREEN_CLASS, state.fullscreen)
    return () => document.body.classList.remove(PAGE_FULLSCREEN_CLASS)
  }, [state.fullscreen])

  const remoteAudioRef = useCallback((element: HTMLAudioElement | null) => controller.bindRemoteAudio(element), [controller])
  const toggleFullscreen = useCallback(() => {
    void controller.toggleFullscreen(shellRef.current)
  }, [controller])

  return { state, controller, shellRef, remoteAudioRef, toggleFullscreen }
}
