import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react'
import { ID_SEZIONI_DOCUMENTO } from './sezioniDocumento'
import type { FascicoloDocument } from '../../fascicoliData'
import {
  DEFAULT_DOCUMENT_SORT,
  compareDocuments,
  isDocumentSortKey,
  type DocumentSortKey,
} from './documentListOrdering'
import { buildDocumentSearchIndex, searchDocumentIndex, type DocumentSearchMode } from './documentSearch'
import {
  dimenticaVistaDocumenti,
  leggiVistaDocumenti,
  salvaVistaDocumenti,
  VISTA_DOCUMENTI_PREDEFINITA,
} from '../../services/vistaDocumentiPreferenze'

export type DocumentStatusFilter = 'tutti' | 'da_firmare' | 'da_verificare'

export type DocumentListEntry<T> = {
  id: string
  document: FascicoloDocument
  sectionId: string
  pendingReview: boolean
  searchExtra: string[]
  value: T
}

const SORT_STORAGE_KEY = 'iusentra.fascicolo.documenti.ordinamento'

/** Sezioni ammesse: le stesse dichiarate dal catalogo documentale. */
const SEZIONI_AMMESSE = new Set(['tutte', ...ID_SEZIONI_DOCUMENTO])
const STATI_AMMESSI = new Set<DocumentStatusFilter>(['tutti', 'da_firmare', 'da_verificare'])

function readStoredSort(): DocumentSortKey {
  try {
    const stored = window.localStorage.getItem(SORT_STORAGE_KEY)
    return isDocumentSortKey(stored) ? stored : DEFAULT_DOCUMENT_SORT
  } catch {
    return DEFAULT_DOCUMENT_SORT
  }
}

function isStatusFilter(value: string): value is DocumentStatusFilter {
  return STATI_AMMESSI.has(value as DocumentStatusFilter)
}

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false
  return target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName)
}

function matchesStatus<T>(entry: DocumentListEntry<T>, status: DocumentStatusFilter): boolean {
  if (status === 'da_firmare') return !entry.document.signed
  if (status === 'da_verificare') return entry.pendingReview
  return true
}

export function useDocumentListControls<T>(entries: DocumentListEntry<T>[]) {
  const [query, setQuery] = useState('')
  const [sort, setSortState] = useState<DocumentSortKey>(readStoredSort)
  const [section, setSection] = useState('tutte')
  const [status, setStatus] = useState<DocumentStatusFilter>('tutti')
  const [applicaFiltriSalvati, setApplicaFiltriSalvati] = useState(false)
  const [vistaSenzaRisultati, setVistaSenzaRisultati] = useState(false)
  const filtriScelti = useRef(false)
  const setSezioneScelta = (next: string) => {
    filtriScelti.current = true
    setApplicaFiltriSalvati(false)
    setVistaSenzaRisultati(false)
    setStatus(statoVisibile)
    setSection(next)
  }
  const setStatoScelto = (next: DocumentStatusFilter) => {
    filtriScelti.current = true
    setApplicaFiltriSalvati(false)
    setVistaSenzaRisultati(false)
    setSection(sezioneVisibile)
    setStatus(next)
  }
  const searchRef = useRef<HTMLInputElement>(null)
  const deferredQuery = useDeferredValue(query)

  // Vista salvata dallo studio: si applica all'apertura e resta il riferimento
  // per capire se quella a schermo e' gia' quella salvata.
  const [vistaSalvata, setVistaSalvata] = useState(VISTA_DOCUMENTI_PREDEFINITA)
  const [vistaConfigurata, setVistaConfigurata] = useState(false)
  const [vistaStato, setVistaStato] = useState<'inattivo' | 'carico' | 'salvo'>('carico')
  const [vistaMessaggio, setVistaMessaggio] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    leggiVistaDocumenti(controller.signal)
      .then((salvata) => {
        if (controller.signal.aborted) return
        setVistaSalvata(salvata.preferences)
        setVistaConfigurata(salvata.configured)
        if (!salvata.configured) return
        // La preferenza dello studio prevale sull'ordinamento locale del browser.
        if (isDocumentSortKey(salvata.preferences.sort)) setSortState(salvata.preferences.sort)
        if (filtriScelti.current) return
        setApplicaFiltriSalvati(true)
        if (SEZIONI_AMMESSE.has(salvata.preferences.section)) setSection(salvata.preferences.section)
        if (isStatusFilter(salvata.preferences.status)) setStatus(salvata.preferences.status)
      })
      .catch(() => { /* vista non leggibile: restano i predefiniti */ })
      .finally(() => { if (!controller.signal.aborted) setVistaStato('inattivo') })
    return () => controller.abort()
  }, [])

  const setSort = useCallback((next: DocumentSortKey) => {
    setSortState(next)
    try {
      window.localStorage.setItem(SORT_STORAGE_KEY, next)
    } catch {
      // Preferenza non persistibile (navigazione privata): l'ordinamento resta valido nella sessione.
    }
  }, [])

  const indexed = useMemo(
    () => entries.map((entry) => ({ item: entry, index: buildDocumentSearchIndex(entry.document, entry.searchExtra) })),
    [entries],
  )

  // Ricerca per pertinenza: sigle e sinonimi forensi, radici, refusi e date in
  // qualunque formato; se nessun documento contiene tutti i termini propone i più simili.
  const searchResult = useMemo(() => searchDocumentIndex(indexed, deferredQuery), [indexed, deferredQuery])
  const searchMode: DocumentSearchMode = searchResult.mode
  const relevanceActive = searchMode === 'esatta' || searchMode === 'simili'

  const relevanceRank = useMemo(
    () => new Map(searchResult.items.map(({ item }, position) => [item.id, position])),
    [searchResult],
  )

  const matchingQuery = useMemo(() => searchResult.items.map(({ item }) => item), [searchResult])

  // Durante il caricamento del catalogo un filtro salvato può non avere ancora riscontri.
  // L'inventario resta visibile. Un filtro selezionato esplicitamente conserva anche l'esito vuoto.
  const filtriSalvatiSenzaRisultati = applicaFiltriSalvati && entries.length > 0
    && !entries.some((entry) => (section === 'tutte' || entry.sectionId === section) && matchesStatus(entry, status))
  useEffect(() => {
    if (filtriSalvatiSenzaRisultati) setVistaSenzaRisultati(true)
  }, [filtriSalvatiSenzaRisultati])
  const usaInventario = vistaSenzaRisultati || filtriSalvatiSenzaRisultati
  const sezioneVisibile = usaInventario ? 'tutte' : section
  const statoVisibile = usaInventario ? 'tutti' : status

  const sectionCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const entry of matchingQuery) {
      if (!matchesStatus(entry, statoVisibile)) continue
      counts.set(entry.sectionId, (counts.get(entry.sectionId) || 0) + 1)
    }
    return counts
  }, [matchingQuery, statoVisibile])

  const statusCounts = useMemo(() => {
    const inSection = matchingQuery.filter((entry) => sezioneVisibile === 'tutte' || entry.sectionId === sezioneVisibile)
    return {
      tutti: inSection.length,
      da_firmare: inSection.filter((entry) => matchesStatus(entry, 'da_firmare')).length,
      da_verificare: inSection.filter((entry) => matchesStatus(entry, 'da_verificare')).length,
      firma_non_confermata: inSection.filter((entry) => entry.document.signatureCheck === 'non_confermata').length,
    } satisfies Record<DocumentStatusFilter, number> & { firma_non_confermata: number }
  }, [matchingQuery, sezioneVisibile])

  const visible = useMemo(
    () => matchingQuery
      .filter((entry) => (sezioneVisibile === 'tutte' || entry.sectionId === sezioneVisibile) && matchesStatus(entry, statoVisibile))
      .sort((a, b) => (relevanceActive ? (relevanceRank.get(a.id) ?? 0) - (relevanceRank.get(b.id) ?? 0) : 0) || compareDocuments(sort, a.document, b.document)),
    [matchingQuery, sezioneVisibile, statoVisibile, sort, relevanceActive, relevanceRank],
  )

  const filtersActive = Boolean(query.trim()) || sezioneVisibile !== 'tutte' || statoVisibile !== 'tutti'

  const resetFilters = useCallback(() => {
    filtriScelti.current = true
    setApplicaFiltriSalvati(false)
    setVistaSenzaRisultati(false)
    setQuery('')
    setSection('tutte')
    setStatus('tutti')
    searchRef.current?.focus()
  }, [])

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if (event.key !== '/' || event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return
      const input = searchRef.current
      if (!input || !input.isConnected) return
      event.preventDefault()
      input.focus()
      input.select()
    }
    window.addEventListener('keydown', listener)
    return () => window.removeEventListener('keydown', listener)
  }, [])

  // La ricerca non entra nella vista salvata: e' una domanda del momento, non
  // un modo di guardare l'archivio.
  const vistaCorrente = useMemo(() => ({ sort, section: sezioneVisibile, status: statoVisibile }), [sort, sezioneVisibile, statoVisibile])
  const vistaModificata =
    vistaCorrente.sort !== vistaSalvata.sort ||
    vistaCorrente.section !== vistaSalvata.section ||
    vistaCorrente.status !== vistaSalvata.status

  const salvaVista = useCallback(async () => {
    setVistaStato('salvo')
    setVistaMessaggio('')
    try {
      const salvata = await salvaVistaDocumenti(vistaCorrente)
      setVistaSalvata(salvata.preferences)
      setVistaConfigurata(salvata.configured)
      setVistaMessaggio('Vista salvata: i prossimi fascicoli si apriranno così.')
    } catch (errore) {
      setVistaMessaggio(errore instanceof Error ? errore.message : 'Vista non salvata. Riprova.')
    } finally {
      setVistaStato('inattivo')
    }
  }, [vistaCorrente])

  const ripristinaVista = useCallback(async () => {
    setVistaStato('salvo')
    setVistaMessaggio('')
    try {
      const salvata = await dimenticaVistaDocumenti()
      setVistaSalvata(salvata.preferences)
      setVistaConfigurata(false)
      setVistaSenzaRisultati(false)
      setApplicaFiltriSalvati(false)
      setSortState(DEFAULT_DOCUMENT_SORT)
      setSection('tutte')
      setStatus('tutti')
      setVistaMessaggio('Vista riportata ai valori predefiniti.')
    } catch (errore) {
      setVistaMessaggio(errore instanceof Error ? errore.message : 'Vista non ripristinata. Riprova.')
    } finally {
      setVistaStato('inattivo')
    }
  }, [])

  return {
    query,
    setQuery,
    sort,
    setSort,
    section: sezioneVisibile,
    setSection: setSezioneScelta,
    status: statoVisibile,
    setStatus: setStatoScelto,
    searchRef,
    visible,
    searchMode,
    relevanceActive,
    total: entries.length,
    sectionCounts,
    statusCounts,
    filtersActive,
    resetFilters,
    vistaConfigurata,
    vistaModificata,
    vistaStato,
    vistaMessaggio: vistaMessaggio || (usaInventario ? 'La vista salvata non mostrava atti all’apertura. Mostro tutti i documenti.' : ''),
    salvaVista,
    ripristinaVista,
  }
}

export type DocumentListControls<T> = ReturnType<typeof useDocumentListControls<T>>
