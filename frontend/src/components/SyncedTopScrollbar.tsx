import { useEffect, useRef, useState, type ReactNode } from 'react'
import './SyncedTopScrollbar.css'

export function SyncedTopScrollbar({
  children,
  className,
}: {
  children: ReactNode
  className: string
}) {
  const topRef = useRef<HTMLDivElement>(null)
  const bodyRef = useRef<HTMLDivElement>(null)
  const [scrollWidth, setScrollWidth] = useState(0)

  useEffect(() => {
    const top = topRef.current
    const body = bodyRef.current
    if (!top || !body) return undefined

    let syncing = false
    const refresh = () => setScrollWidth(body.scrollWidth)
    const syncTop = () => {
      if (syncing) return
      syncing = true
      body.scrollLeft = top.scrollLeft
      syncing = false
    }
    const syncBody = () => {
      if (syncing) return
      syncing = true
      top.scrollLeft = body.scrollLeft
      syncing = false
    }

    refresh()
    const resizeObserver = new ResizeObserver(refresh)
    resizeObserver.observe(body)
    if (body.firstElementChild) resizeObserver.observe(body.firstElementChild)
    top.addEventListener('scroll', syncTop, { passive: true })
    body.addEventListener('scroll', syncBody, { passive: true })
    return () => {
      resizeObserver.disconnect()
      top.removeEventListener('scroll', syncTop)
      body.removeEventListener('scroll', syncBody)
    }
  }, [children])

  return (
    <>
      <div className="iu-top-scrollbar" ref={topRef} aria-hidden="true">
        <div style={{ width: `${scrollWidth}px` }} />
      </div>
      <div className={className} ref={bodyRef}>
        {children}
      </div>
    </>
  )
}
