import { useEffect, useRef, useState } from 'react'
import { ensureJson } from '../../lib/apiClient'
import './patFormweb.css'

type Voce = { codice: string; descrizione: string }
type Catalogo = {
  ok: boolean
  sedi: Array<Voce & { ambito: string }>
  tipiRicorsoTar: Voce[]
  tipiRicorsoCds: Voce[]
  contributo: string[]
  posizioni: string[]
  sede?: Voce & { ambito: string }
}

const URL_CATALOGO = '/api/v1/ui/amministrativo/catalogo-apertura'

/**
 * Dati della bozza Formweb chiesti già all'apertura del fascicolo amministrativo: sede come la scrive il
 * Portale dell'Avvocato (proposta dall'ufficio indicato), tipo di ricorso, NRG, posizione, contributo.
 */
export function PatApertura() {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [errore, setErrore] = useState('')
  const [sede, setSede] = useState('')
  const scelta = useRef(false)
  const ancora = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    const abort = new AbortController()
    ensureJson<Catalogo>(URL_CATALOGO, { signal: abort.signal }).then(setCatalogo)
      .catch(() => { if (!abort.signal.aborted) setErrore('Elenco del Portale dell’Avvocato non disponibile: completerai i dati nella sezione «Deposito amministrativo».') })
    return () => abort.abort()
  }, [])

  useEffect(() => {
    const modulo = ancora.current?.closest('form')
    if (!modulo || !catalogo) return undefined
    let abort = new AbortController()
    let attesa = 0
    const aggiorna = (evento?: Event) => {
      if ((evento?.target as HTMLElement | null)?.getAttribute?.('name') !== 'tribunale' && evento) return
      window.clearTimeout(attesa)
      attesa = window.setTimeout(() => {
        const ufficio = String(new FormData(modulo).get('tribunale') || '').trim()
        abort.abort()
        abort = new AbortController()
        if (!ufficio || scelta.current) return
        ensureJson<Catalogo>(`${URL_CATALOGO}?${new URLSearchParams({ ufficio })}`, { signal: abort.signal })
          .then((esito) => { if (!scelta.current && esito.sede?.codice) setSede(esito.sede.codice) })
          .catch(() => undefined)
      }, 350)
    }
    aggiorna()
    modulo.addEventListener('change', aggiorna)
    modulo.addEventListener('input', aggiorna)
    return () => { window.clearTimeout(attesa); abort.abort(); modulo.removeEventListener('change', aggiorna); modulo.removeEventListener('input', aggiorna) }
  }, [catalogo])

  if (errore) return <p className="iu-fas-field--wide">{errore}</p>
  if (!catalogo) return <p className="iu-fas-field--wide" ref={ancora}>Caricamento delle scelte del Portale dell’Avvocato…</p>
  const ambito = catalogo.sedi.find((s) => s.codice === sede)?.ambito || ''
  const tipi = ambito === 'CDS' || ambito === 'CGARS' ? catalogo.tipiRicorsoCds : catalogo.tipiRicorsoTar
  return (
    <>
      <p className="iu-fas-field--wide iu-pat-nota" ref={ancora}>
        Nel Formweb la bozza nasce con sede, primo ricorrente e tipologia: indicali ora e IUSENTRA preparerà la scheda da seguire.
      </p>
      <label className="iu-fas-field"><span>Sede nel Portale dell’Avvocato</span>
        <select name="pat_sede" value={sede} onChange={(e) => { scelta.current = true; setSede(e.target.value) }}>
          <option value="">Dall’ufficio indicato sopra</option>
          {catalogo.sedi.map((s) => <option key={s.codice} value={s.codice}>{s.descrizione}</option>)}
        </select></label>
      <label className="iu-fas-field"><span>{ambito === 'CDS' || ambito === 'CGARS' ? 'Tipo di appello' : 'Tipo di ricorso'}</span>
        <select name="pat_tipo_ricorso" defaultValue=""><option value="">Da scegliere</option>{tipi.map((t) => <option key={t.codice} value={t.codice}>{t.descrizione}</option>)}</select></label>
      <label className="iu-fas-field"><span>Posizione dell’assistito</span>
        <select name="pat_posizione" defaultValue="ricorrente">{catalogo.posizioni.map((p) => <option key={p} value={p}>{p.charAt(0).toUpperCase() + p.slice(1)}</option>)}</select></label>
      <label className="iu-fas-field"><span>NRG (se il ricorso è già iscritto)</span><input name="pat_nrg" inputMode="numeric" maxLength={9} placeholder="es. 202600123"/></label>
      <label className="iu-fas-field"><span>Contributo unificato</span>
        <select name="pat_cu" defaultValue=""><option value="">Da scegliere</option>{catalogo.contributo.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
    </>
  )
}
