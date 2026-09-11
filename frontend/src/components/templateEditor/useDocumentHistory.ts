import { useCallback, useMemo, useRef, useState, type RefObject } from 'react'
import { cleanEditorHtml } from './editorArtifacts'
import { EditorHistory, type HistorySnapshot } from './editorHistory'
import { getTextBookmark, restoreTextBookmark } from './selectionBookmark'

const TYPING_GROUP_MS = 450

/** Annulla/ripeti del documento con passi separati per digitazione e comandi. */
export function useDocumentHistory(editorRef: RefObject<HTMLDivElement | null>, onRestored: () => void) {
  const historyRef = useRef(new EditorHistory())
  const timerRef = useRef<number | undefined>(undefined)
  const restoredRef = useRef(onRestored)
  restoredRef.current = onRestored
  const [state, setState] = useState({ canUndo: false, canRedo: false })

  const refresh = useCallback(() => {
    const history = historyRef.current
    setState((current) => (
      current.canUndo === history.canUndo && current.canRedo === history.canRedo
        ? current
        : { canUndo: history.canUndo, canRedo: history.canRedo }
    ))
  }, [])

  const snapshot = useCallback((): HistorySnapshot | null => {
    const editor = editorRef.current
    if (!editor) return null
    return { html: cleanEditorHtml(editor.innerHTML), bookmark: getTextBookmark(editor) }
  }, [editorRef])

  const commitNow = useCallback(() => {
    window.clearTimeout(timerRef.current)
    timerRef.current = undefined
    const current = snapshot()
    if (!current) return
    historyRef.current.commit(current)
    refresh()
  }, [refresh, snapshot])

  const scheduleCommit = useCallback(() => {
    window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(commitNow, TYPING_GROUP_MS)
  }, [commitNow])

  const reset = useCallback(() => {
    window.clearTimeout(timerRef.current)
    timerRef.current = undefined
    historyRef.current.reset(snapshot())
    refresh()
  }, [refresh, snapshot])

  /** Contenuto sostituito dal programma (modello, proposta Lex, importazione): annullabile se c'era già un documento. */
  const recordReplacement = useCallback(() => {
    const current = snapshot()
    if (!current) return
    window.clearTimeout(timerRef.current)
    timerRef.current = undefined
    historyRef.current.commit(current)
    refresh()
  }, [refresh, snapshot])

  const apply = useCallback((entry: HistorySnapshot | null) => {
    const editor = editorRef.current
    if (!editor || !entry) return false
    editor.innerHTML = entry.html
    editor.focus({ preventScroll: true })
    restoreTextBookmark(editor, entry.bookmark)
    restoredRef.current()
    refresh()
    return true
  }, [editorRef, refresh])

  const undo = useCallback(() => {
    if (timerRef.current !== undefined) commitNow()
    return apply(historyRef.current.undo())
  }, [apply, commitNow])

  const redo = useCallback(() => {
    if (timerRef.current !== undefined) commitNow()
    return apply(historyRef.current.redo())
  }, [apply, commitNow])

  return useMemo(() => ({
    canUndo: state.canUndo,
    canRedo: state.canRedo,
    commitNow,
    scheduleCommit,
    reset,
    recordReplacement,
    undo,
    redo,
  }), [state, commitNow, scheduleCommit, reset, recordReplacement, undo, redo])
}
