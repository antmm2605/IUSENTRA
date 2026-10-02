import { useEffect } from 'react'
import type { RefObject } from 'react'
export function useViewerPageTools(reader: RefObject<HTMLIFrameElement | null>, editable: boolean, setPage: (page: number) => void, setOpen: (open: boolean) => void, setArmed: (armed: boolean) => void) {
  useEffect(() => {
    const show = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.source !== reader.current?.contentWindow || event.data?.type !== 'iusentra.document.openPageTools' || !editable) return
      setPage(Math.max(1, Number(event.data.page) || 1)); setArmed(false); setOpen(true)
    }
    window.addEventListener('message', show)
    return () => window.removeEventListener('message', show)
  }, [reader, editable, setPage, setOpen, setArmed])
}
