/**
 * Cronologia annulla/ripeti del documento.
 *
 * L'impaginazione modifica il DOM fuori dai comandi del browser, quindi la
 * cronologia nativa di contentEditable non è affidabile: si registrano istantanee
 * dell'HTML pulito (senza spaziatori) con la posizione del cursore.
 */

import type { TextBookmark } from './selectionBookmark'

export type HistorySnapshot = {
  html: string
  bookmark: TextBookmark | null
}

export class EditorHistory {
  private past: HistorySnapshot[] = []
  private future: HistorySnapshot[] = []
  private present: HistorySnapshot | null = null

  constructor(private readonly limit = 200) {}

  reset(snapshot: HistorySnapshot | null) {
    this.past = []
    this.future = []
    this.present = snapshot
  }

  /** Registra lo stato corrente; restituisce true se è un nuovo passo annullabile. */
  commit(snapshot: HistorySnapshot): boolean {
    if (this.present && this.present.html === snapshot.html) {
      this.present = { ...this.present, bookmark: snapshot.bookmark }
      return false
    }
    if (this.present) {
      this.past.push(this.present)
      if (this.past.length > this.limit) this.past.shift()
    }
    this.present = snapshot
    this.future = []
    return true
  }

  undo(): HistorySnapshot | null {
    const previous = this.past.pop()
    if (!previous) return null
    if (this.present) this.future.push(this.present)
    this.present = previous
    return previous
  }

  redo(): HistorySnapshot | null {
    const next = this.future.pop()
    if (!next) return null
    if (this.present) this.past.push(this.present)
    this.present = next
    return next
  }

  get canUndo() {
    return this.past.length > 0
  }

  get canRedo() {
    return this.future.length > 0
  }
}
