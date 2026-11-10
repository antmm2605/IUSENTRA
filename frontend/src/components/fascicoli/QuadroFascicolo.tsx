import { useCallback, useEffect, useState } from 'react'
import type { MouseEvent } from 'react'
import { ChevronRight, Gauge, RefreshCw } from 'lucide-react'
import { ApiClientError, ensureJson } from '../../lib/apiClient'
import { Badge } from '../dashboard'
import { isSezioneFascicoloId } from './SezioneFascicolo'
import type { SezioneFascicoloId } from './SezioneFascicolo'
import './QuadroFascicolo.css'

/**
 * Quadro del fascicolo (riorganizzazione approvata dall'avvocato il 10/11/2026): una riga per tema
 * — prossimo passo, termini, economia, notifiche, documenti — e ogni riga porta alla sua sezione.
 * I dati vengono da GET /api/v1/ui/fascicoli/<id>/quadro, che dichiara anche lo stato unico della
 * pratica mostrato nella testata. Se il servizio non esiste (404) il quadro non compare e la pagina
 * resta integra; se la lettura non riesce lo si dice in italiano, senza rompere le sezioni sotto.
 */

export type QuadroTema = 'prossimo_passo' | 'termini' | 'economia' | 'notifiche' | 'documenti'
export type QuadroLivello = 'ok' | 'info' | 'attenzione' | 'urgente'
export type QuadroStatoPratica = { codice: string; etichetta: string; dettaglio: string }
export type QuadroRiga = { tema: QuadroTema; titolo: string; testo: string; livello: QuadroLivello; sezione: SezioneFascicoloId }
export type QuadroFascicoloDati = { stato: QuadroStatoPratica; righe: QuadroRiga[]; generatoIl: string }
export type QuadroLettura =
  | { fase: 'caricamento' }
  | { fase: 'pronto'; dati: QuadroFascicoloDati }
  | { fase: 'errore'; messaggio: string }
  | { fase: 'assente' }

const ORDINE_TEMI: QuadroTema[] = ['prossimo_passo', 'termini', 'economia', 'notifiche', 'documenti']
const LIVELLI: QuadroLivello[] = ['ok', 'info', 'attenzione', 'urgente']
const SEZIONE_DEL_TEMA: Record<QuadroTema, SezioneFascicoloId> = {
  prossimo_passo: 'sezione-andamento',
  termini: 'sezione-termini',
  economia: 'sezione-economia',
  notifiche: 'sezione-comunicazioni',
  documenti: 'sezione-documenti',
}
const ETICHETTA_LIVELLO: Record<QuadroLivello, string> = {
  ok: 'In ordine',
  info: 'Da sapere',
  attenzione: 'Da verificare',
  urgente: 'Urgente',
}
const TONO_LIVELLO: Record<QuadroLivello, 'success' | 'info' | 'warning' | 'danger'> = {
  ok: 'success',
  info: 'info',
  attenzione: 'warning',
  urgente: 'danger',
}
const MESSAGGIO_ERRORE = 'Il quadro del fascicolo non è disponibile in questo momento. Le sezioni qui sotto restano consultabili.'

function testo(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

/** Legge la risposta del servizio; restituisce null se non rispetta il contratto. */
export function normalizzaQuadro(payload: unknown): QuadroFascicoloDati | null {
  if (!payload || typeof payload !== 'object') return null
  const record = payload as Record<string, unknown>
  if (record.ok !== true || !Array.isArray(record.righe)) return null
  const stato = record.stato && typeof record.stato === 'object' ? record.stato as Record<string, unknown> : {}
  const righe: QuadroRiga[] = []
  for (const item of record.righe) {
    if (!item || typeof item !== 'object') continue
    const riga = item as Record<string, unknown>
    const tema = testo(riga.tema) as QuadroTema
    if (!ORDINE_TEMI.includes(tema)) continue
    const livello = (LIVELLI.includes(testo(riga.livello) as QuadroLivello) ? testo(riga.livello) : 'info') as QuadroLivello
    const sezione = testo(riga.sezione)
    righe.push({
      tema,
      titolo: testo(riga.titolo),
      testo: testo(riga.testo),
      livello,
      sezione: isSezioneFascicoloId(sezione) ? sezione : SEZIONE_DEL_TEMA[tema],
    })
  }
  righe.sort((a, b) => ORDINE_TEMI.indexOf(a.tema) - ORDINE_TEMI.indexOf(b.tema))
  return {
    stato: { codice: testo(stato.codice), etichetta: testo(stato.etichetta), dettaglio: testo(stato.dettaglio) },
    righe,
    generatoIl: testo(record.generato_il),
  }
}

/** Lettura del quadro con le quattro situazioni: caricamento, pronto, errore, servizio assente. */
export function useQuadroFascicolo(fascicoloId: string): { lettura: QuadroLettura; riprova: () => void } {
  const [lettura, setLettura] = useState<QuadroLettura>({ fase: 'caricamento' })
  const [tentativo, setTentativo] = useState(0)
  useEffect(() => {
    if (!fascicoloId) return undefined
    const controller = new AbortController()
    setLettura({ fase: 'caricamento' })
    ensureJson<unknown>(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/quadro`, { signal: controller.signal, activity: false })
      .then((payload) => {
        if (controller.signal.aborted) return
        const dati = normalizzaQuadro(payload)
        // Una risposta che non rispetta il contratto vale come servizio non ancora presente.
        setLettura(dati ? { fase: 'pronto', dati } : { fase: 'assente' })
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return
        // 404/405: il servizio del quadro non c'è ancora su questa installazione.
        if (error instanceof ApiClientError && (error.status === 404 || error.status === 405)) { setLettura({ fase: 'assente' }); return }
        setLettura({ fase: 'errore', messaggio: MESSAGGIO_ERRORE })
      })
    return () => controller.abort()
  }, [fascicoloId, tentativo])
  const riprova = useCallback(() => setTentativo((n) => n + 1), [])
  // Obblighi di notifica non ancora calcolati: si calcolano una volta in sfondo (l'endpoint salva la sintesi)
  // e poi si rilegge il quadro, così la riga dice lo stato vero invece di «da calcolare».
  const [notificheCalcolate, setNotificheCalcolate] = useState('')
  useEffect(() => {
    if (lettura.fase !== 'pronto' || notificheCalcolate === fascicoloId) return undefined
    const daCalcolare = lettura.dati.righe.some((riga) => riga.tema === 'notifiche' && /da calcolare/i.test(riga.testo))
    if (!daCalcolare) return undefined
    setNotificheCalcolate(fascicoloId)
    const controller = new AbortController()
    ensureJson<unknown>(`/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/obblighi-notifica`, { signal: controller.signal, activity: false })
      .then(() => { if (!controller.signal.aborted) setTentativo((n) => n + 1) })
      .catch(() => undefined)
    return () => controller.abort()
  }, [lettura, fascicoloId, notificheCalcolate])
  return { lettura, riprova }
}

function oraAggiornamento(iso: string): string {
  if (!iso) return ''
  const data = new Date(iso)
  if (Number.isNaN(data.getTime())) return ''
  return data.toLocaleString('it-IT', { timeZone: 'Europe/Rome', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
}

export function QuadroFascicolo({ lettura, onRiprova, onApriSezione }:{
  lettura: QuadroLettura
  onRiprova: () => void
  onApriSezione: (sezione: SezioneFascicoloId) => void
}) {
  if (lettura.fase === 'assente') return null
  const apri = (sezione: SezioneFascicoloId) => (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault()
    onApriSezione(sezione)
  }
  const aggiornato = lettura.fase === 'pronto' ? oraAggiornamento(lettura.dati.generatoIl) : ''
  return (
    <section id="quadro-fascicolo" className="iu-quadro-fascicolo" aria-labelledby="quadro-fascicolo-titolo">
      <header className="iu-quadro-fascicolo__header">
        <h2 id="quadro-fascicolo-titolo"><Gauge size={17} aria-hidden="true"/> Quadro del fascicolo</h2>
        {aggiornato ? <small>Aggiornato al {aggiornato}</small> : null}
      </header>
      {lettura.fase === 'caricamento' ? <p className="iu-quadro-fascicolo__stato" role="status">Lettura del quadro del fascicolo…</p> : null}
      {lettura.fase === 'errore' ? (
        <div className="iu-quadro-fascicolo__stato iu-quadro-fascicolo__stato--errore" role="alert">
          <span>{lettura.messaggio}</span>
          <button type="button" onClick={onRiprova}><RefreshCw size={14} aria-hidden="true"/> Riprova</button>
        </div>
      ) : null}
      {lettura.fase === 'pronto' && !lettura.dati.righe.length ? <p className="iu-quadro-fascicolo__stato">Nessuna indicazione da segnalare sul fascicolo.</p> : null}
      {lettura.fase === 'pronto' && lettura.dati.righe.length ? (
        <ul className="iu-quadro-fascicolo__righe">
          {lettura.dati.righe.map((riga) => (
            <li key={riga.tema}>
              <a className={`iu-quadro-fascicolo__riga iu-quadro-fascicolo__riga--${riga.livello}`} href={`#${riga.sezione}`} onClick={apri(riga.sezione)}>
                <span className="iu-quadro-fascicolo__tema">{riga.titolo}</span>
                <span className="iu-quadro-fascicolo__testo">{riga.testo}</span>
                <span className="iu-quadro-fascicolo__livello"><Badge tone={TONO_LIVELLO[riga.livello]}>{ETICHETTA_LIVELLO[riga.livello]}</Badge></span>
                <ChevronRight className="iu-quadro-fascicolo__vai" size={16} aria-hidden="true"/>
              </a>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  )
}
