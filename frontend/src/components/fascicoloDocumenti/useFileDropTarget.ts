import { useCallback, useRef, useState, type DragEvent, type RefObject } from 'react'

function hasFiles(event: DragEvent<HTMLElement>): boolean {
  return Array.from(event.dataTransfer?.types || []).includes('Files')
}

/**
 * Trascinamento di file su un form di caricamento: i file rilasciati vengono
 * assegnati all'input nativo, così il submit multipart resta quello esistente.
 */
export function useFileDropTarget(inputRef: RefObject<HTMLInputElement | null>, onFiles: (files: File[]) => void) {
  const [dragging, setDragging] = useState(false)
  const depth = useRef(0)

  const onDragEnter = useCallback((event: DragEvent<HTMLElement>) => {
    if (!hasFiles(event)) return
    event.preventDefault()
    depth.current += 1
    setDragging(true)
  }, [])

  const onDragOver = useCallback((event: DragEvent<HTMLElement>) => {
    if (!hasFiles(event)) return
    event.preventDefault()
    event.dataTransfer.dropEffect = 'copy'
  }, [])

  const onDragLeave = useCallback((event: DragEvent<HTMLElement>) => {
    if (!hasFiles(event)) return
    depth.current = Math.max(0, depth.current - 1)
    if (depth.current === 0) setDragging(false)
  }, [])

  const onDrop = useCallback((event: DragEvent<HTMLElement>) => {
    if (!hasFiles(event)) return
    event.preventDefault()
    depth.current = 0
    setDragging(false)
    const dropped = Array.from(event.dataTransfer.files || []).filter((file) => file.size > 0 || file.type)
    if (!dropped.length) return
    const input = inputRef.current
    if (input) {
      const transfer = new DataTransfer()
      dropped.forEach((file) => transfer.items.add(file))
      input.files = transfer.files
    }
    onFiles(dropped)
  }, [inputRef, onFiles])

  return { dragging, dropHandlers: { onDragEnter, onDragOver, onDragLeave, onDrop } }
}
