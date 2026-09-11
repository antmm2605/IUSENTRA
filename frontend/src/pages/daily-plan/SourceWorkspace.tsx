import { useCallback, useEffect, useState } from 'react'
import { ChevronLeft, ChevronRight, ExternalLink, FileSearch, Maximize2, Minimize2 } from 'lucide-react'
import { OperationalModal } from '@/components/OperationalModal'
import { sourceViewerHref } from '@/components/SourceDocumentModal'
import { fetchDettaglioAttivita, fetchFontiAttivita } from './api'
import { SourceViewer } from './SourceViewer'
import { SourceWorkspacePanel } from './SourceWorkspacePanel'
import type { AttivitaDettaglio, AttivitaPiano, FonteAttivita } from './types'

export type FonteAperta = { item: AttivitaPiano; lista: AttivitaPiano[] }

type Props = {
  aperta: FonteAperta | null
  dataPiano: string
  writeProposalsEnabled: boolean
  busy: boolean
  esitoMessaggio: string
  onNavigate: (aperta: FonteAperta) => void
  onClose: () => void
  onAzione: (item: AttivitaPiano, action: string, params?: Record<string, unknown>) => Promise<boolean>
  onOpenDetail: (item: AttivitaPiano) => void
}

// azioni che chiudono l'attività corrente: si passa subito alla successiva
const AZIONI_CHE_AVANZANO = new Set(['complete', 'snooze'])

function inCampoDiTesto(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))
}

export function SourceWorkspace({
  aperta,
  dataPiano,
  writeProposalsEnabled,
  busy,
  esitoMessaggio,
  onNavigate,
  onClose,
  onAzione,
  onOpenDetail,
}: Props) {
  const [fonti, setFonti] = useState<FonteAttivita[]>([])
  const [fascicoloHref, setFascicoloHref] = useState('')
  const [messaggio, setMessaggio] = useState('')
  const [stato, setStato] = useState<'loading' | 'ready' | 'error'>('loading')
  const [attiva, setAttiva] = useState(0)
  const [dettaglio, setDettaglio] = useState<AttivitaDettaglio | null>(null)
  const [fullscreen, setFullscreen] = useState(false)
  const [tentativo, setTentativo] = useState(0)

  const item = aperta?.item || null
  const lista = aperta?.lista || []
  const indice = item ? lista.findIndex((row) => row.id === item.id) : -1
  const precedente = indice > 0 ? lista[indice - 1] : null
  const successiva = indice >= 0 && indice < lista.length - 1 ? lista[indice + 1] : null

  useEffect(() => {
    setFonti([])
    setDettaglio(null)
    setAttiva(0)
    setMessaggio('')
    if (!item) return undefined
    setStato('loading')
    const controller = new AbortController()
    Promise.all([
      fetchFontiAttivita(item.id, controller.signal),
      fetchDettaglioAttivita(item.id, controller.signal),
    ])
      .then(([payload, detail]) => {
        if (detail.ok && detail.attivita) setDettaglio(detail.attivita)
        if (!payload.ok) {
          setStato('error')
          return
        }
        setFonti(payload.fonti)
        setFascicoloHref(payload.fascicolo_href)
        setMessaggio(payload.messaggio || '')
        setStato('ready')
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === 'AbortError') return
        setStato('error')
      })
    return () => controller.abort()
  }, [item, tentativo])

  const vai = useCallback(
    (target: AttivitaPiano | null) => {
      if (target) onNavigate({ item: target, lista })
    },
    [lista, onNavigate],
  )

  useEffect(() => {
    if (!item) return undefined
    const onKey = (event: KeyboardEvent) => {
      if (event.altKey || event.ctrlKey || event.metaKey || inCampoDiTesto(event.target)) return
      if (event.key === 'ArrowLeft' && precedente) vai(precedente)
      if (event.key === 'ArrowRight' && successiva) vai(successiva)
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [item, precedente, successiva, vai])

  if (!aperta || !item) return null

  const eseguiAzione = async (action: string, params: Record<string, unknown> = {}) => {
    const riuscita = await onAzione(item, action, params)
    if (!riuscita || !AZIONI_CHE_AVANZANO.has(action)) return
    if (successiva) vai(successiva)
    else onClose()
  }

  const fonteCorrente = fonti[attiva]
  const sottotitolo = [item.fascicolo ? `Fascicolo ${item.fascicolo}` : '', item.cliente, lista.length > 1 && indice >= 0 ? `Attività ${indice + 1} di ${lista.length}` : '']
    .filter(Boolean)
    .join(' · ')

  return (
    <OperationalModal
      open
      ariaLabel={`Fonte dell’attività: ${item.titolo}`}
      eyebrow={<><FileSearch size={14} /> Fonte dell’attività</>}
      title={item.titolo}
      subtitle={sottotitolo}
      onClose={onClose}
      boxClassName={fullscreen ? 'iu-ag-source-modal__box--fullscreen' : ''}
      bodyClassName="grid grid-rows-[minmax(0,1fr)_auto] lg:grid-cols-[minmax(0,1fr)_340px] lg:grid-rows-1"
      actions={
        <>
          <button type="button" onClick={() => vai(precedente)} disabled={!precedente} title="Attività precedente (freccia sinistra)">
            <ChevronLeft size={14} /> Precedente
          </button>
          <button type="button" onClick={() => vai(successiva)} disabled={!successiva} title="Attività successiva (freccia destra)">
            Successiva <ChevronRight size={14} />
          </button>
          <button type="button" onClick={() => setFullscreen((value) => !value)} aria-pressed={fullscreen}>
            {fullscreen ? <Minimize2 size={14} /> : <Maximize2 size={14} />}
            {fullscreen ? 'Vista normale' : 'Tutto schermo'}
          </button>
          {fonteCorrente?.href ? (
            <a href={sourceViewerHref(fonteCorrente, false)} target="_blank" rel="noreferrer">
              <ExternalLink size={14} /> Apri originale
            </a>
          ) : null}
        </>
      }
    >
      <div className="relative min-h-0 min-w-0">
        <SourceViewer
          fonti={fonti}
          attiva={attiva}
          onSelect={setAttiva}
          stato={stato}
          messaggio={messaggio}
          fascicoloHref={fascicoloHref}
          onRetry={() => setTentativo((value) => value + 1)}
        />
      </div>
      <SourceWorkspacePanel
        item={item}
        dettaglio={dettaglio}
        dataPiano={dataPiano}
        fascicoloHref={fascicoloHref}
        writeProposalsEnabled={writeProposalsEnabled}
        busy={busy}
        esitoMessaggio={esitoMessaggio}
        onAzione={eseguiAzione}
        onOpenDetail={() => onOpenDetail(item)}
      />
    </OperationalModal>
  )
}
