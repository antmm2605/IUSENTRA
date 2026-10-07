import { useEffect, useRef, useSyncExternalStore } from 'react'
import { SourceDocumentWorkWindow } from './SourceDocumentModal'
import { closeParentSourceOwner, openSourceWindow, clearSourceWindows, closeSourceWindow, sourceWindowsSnapshot, subscribeSourceWindows } from './sourceWindowEvents'
import { sourceWorkDescriptor } from './sourceWorkDescriptor'
export function SourceWorkWindows({ sessionKey }: { sessionKey: string }) {
  const session = useRef(sessionKey)
  useEffect(() => {
    const frameOwners = new WeakMap<HTMLIFrameElement, string>()
    let frameSequence = 0
    const message = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || typeof event.data?.owner !== 'string' || event.data.owner.length > 300) return
      if (event.data.type === 'iusentra:close-source-owner' && window.parent !== window && event.source === window.parent) {
        closeParentSourceOwner(event.data.owner)
        return
      }
      if (event.data.type !== 'iusentra:open-source-window') return
      const frame = [...document.querySelectorAll('iframe')].find(item => item.contentWindow === event.source)
      const source = sourceWorkDescriptor(event.data.source, window.location.origin)
      if (!frame || !source) return
      let frameOwner = frameOwners.get(frame)
      if (!frameOwner) { frameOwner = `source-frame-${++frameSequence}`; frameOwners.set(frame, frameOwner) }
      const owner = event.data.owner
      openSourceWindow(source, `${frameOwner}:${owner}`, () => {
        if (frame.isConnected) frame.contentWindow?.postMessage({ type: 'iusentra:close-source-owner', owner }, window.location.origin)
      })
    }
    window.addEventListener('message', message)
    return () => window.removeEventListener('message', message)
  }, [])
  useEffect(() => { if (session.current !== sessionKey) { clearSourceWindows(); session.current = sessionKey } }, [sessionKey])
  const entries = useSyncExternalStore(subscribeSourceWindows,sourceWindowsSnapshot)
  if (session.current !== sessionKey) return null
  return <>{entries.map(entry => <SourceDocumentWorkWindow key={entry.id} source={entry.source} focusToken={entry.focusToken} onClose={() => closeSourceWindow(entry.id)}/>)}</>
}