import { useEffect, useRef, useState } from 'react'
import { ensureJson } from '../../lib/apiClient'
import type { Sede } from './types'
import '../patFormweb/patFormweb.css'

type Catalogo = {
  ok: boolean
  sedi: Sede[]
  attiImpugnati: string[]
  pubblicaUdienza: string[]
  posizioni: string[]
  scaglioni: Array<{ fino: number | null; cut: number }>
  corte?: Sede | null
}

const URL_CATALOGO = '/api/v1/ui/tributario/catalogo-apertura'

function cutDaValore(valore: string, scaglioni: Catalogo['scaglioni']): number | null {
  const testo = valore.replace(/\s|€/g, '')
  if (!testo) return null
  const numero = Number(testo.includes(',') ? testo.replace(/\./g, '').replace(',', '.') : testo)
  if (Number.isNaN(numero)) return null
  return scaglioni.find((s) => s.fino === null || numero <= s.fino)?.cut ?? null
}

/**
 * Dati della nota di iscrizione a ruolo chiesti già all'apertura del fascicolo tributario: Corte (proposta
 * dall'ufficio indicato), atto impugnato con notifica e valore della lite (CUT subito), data di notifica del
 * ricorso da cui decorrono i 30 giorni per costituirsi.
 */
export function PttApertura() {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [errore, setErrore] = useState('')
  const [corte, setCorte] = useState('')
  const [valore, setValore] = useState('')
  const scelta = useRef(false)
  const ancora = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    const abort = new AbortController()
    ensureJson<Catalogo>(URL_CATALOGO, { signal: abort.signal }).then(setCatalogo)
      .catch(() => { if (!abort.signal.aborted) setErrore('Elenco delle Corti non disponibile: completerai i dati nella sezione «Deposito tributario».') })
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
          .then((esito) => { if (!scelta.current && esito.corte?.codice) setCorte(esito.corte.codice) })
          .catch(() => undefined)
      }, 350)
    }
    aggiorna()
    modulo.addEventListener('change', aggiorna)
    modulo.addEventListener('input', aggiorna)
    return () => { window.clearTimeout(attesa); abort.abort(); modulo.removeEventListener('change', aggiorna); modulo.removeEventListener('input', aggiorna) }
  }, [catalogo])

  if (errore) return <p className="iu-fas-field--wide">{errore}</p>
  if (!catalogo) return <p className="iu-fas-field--wide" ref={ancora}>Caricamento delle Corti di giustizia tributaria…</p>
  const cut = cutDaValore(valore, catalogo.scaglioni)
  return (
    <>
      <p className="iu-fas-field--wide iu-pat-nota" ref={ancora}>
        La nota di iscrizione a ruolo chiede Corte, atto impugnato e valore della lite: indicali ora e IUSENTRA calcola CUT e termine per costituirti.
      </p>
      <label className="iu-fas-field iu-fas-field--wide"><span>Corte di giustizia tributaria</span>
        <select name="ptt_corte" value={corte} onChange={(e) => { scelta.current = true; setCorte(e.target.value) }}>
          <option value="">Dall’ufficio indicato sopra</option>
          {['1', '2'].map((grado) => (
            <optgroup key={grado} label={grado === '1' ? 'Primo grado' : 'Secondo grado'}>
              {catalogo.sedi.filter((s) => s.grado === grado).map((s) => <option key={s.codice} value={s.codice}>{s.nome}</option>)}
            </optgroup>
          ))}
        </select></label>
      <label className="iu-fas-field"><span>Posizione dell’assistito</span>
        <select name="ptt_posizione" defaultValue="ricorrente"><option value="ricorrente">Ricorrente</option><option value="resistente">Resistente</option></select></label>
      <label className="iu-fas-field"><span>Atto impugnato</span>
        <select name="ptt_atto_tipo" defaultValue=""><option value="">Da scegliere</option>{catalogo.attiImpugnati.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
      <label className="iu-fas-field"><span>Numero dell’atto</span><input name="ptt_atto_numero" maxLength={120}/></label>
      <label className="iu-fas-field"><span>Ufficio che l’ha emesso</span><input name="ptt_atto_ufficio" maxLength={120} placeholder="es. Direzione provinciale di Bari"/></label>
      <label className="iu-fas-field"><span>Atto notificato il</span><input type="date" name="ptt_atto_notifica"/></label>
      <label className="iu-fas-field"><span>Periodo d’imposta</span><input name="ptt_periodo" maxLength={20} placeholder="es. 2021"/></label>
      <label className="iu-fas-field"><span>Valore della lite (€){cut !== null ? ` · CUT € ${cut}` : ''}</span>
        <input name="ptt_valore" inputMode="decimal" value={valore} onChange={(e) => setValore(e.target.value)} placeholder="tributo senza interessi e sanzioni"/></label>
      <label className="iu-fas-field"><span>Ricorso notificato il (per il termine di 30 giorni)</span><input type="date" name="ptt_notifica_ricorso"/></label>
      <label className="iu-fas-field"><span>Numero di ruolo (se già iscritto)</span><input name="ptt_rg" maxLength={20} placeholder="es. 1234/2026"/></label>
      <label className="iu-fas-field"><span>Trattazione</span>
        <select name="ptt_pubblica_udienza" defaultValue=""><option value="">No (camera di consiglio)</option>{catalogo.pubblicaUdienza.slice(1).map((v) => <option key={v} value={v}>{v}</option>)}</select></label>
    </>
  )
}
