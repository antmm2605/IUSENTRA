import { useEffect, useRef, useState, type RefObject } from 'react'
import { ensureJson } from '../../lib/apiClient'
import './penalePdp.css'

type Voce = { codice: string; descrizione: string }
type Sede = { distretto: string; circondario: string; sede: string; codiceSede: string }
type Catalogo = { ok: boolean; uffici: Voce[]; registri: Voce[]; ruoli: Voce[]; sede?: Sede }

const URL_CATALOGO = '/api/v1/ui/penale/catalogo-apertura'

/** Dove scegliere l'ufficio sul PDP, ricavato dall'ufficio giudiziario indicato nel modulo. */
function useSedePdp(ancora: RefObject<HTMLElement | null>) {
  const [sede, setSede] = useState<Sede | null>(null)
  useEffect(() => {
    const modulo = ancora.current?.closest('form')
    if (!modulo) return undefined
    let abort = new AbortController()
    let attesa = 0
    const aggiorna = () => {
      window.clearTimeout(attesa)
      attesa = window.setTimeout(() => {
        const dati = new FormData(modulo)
        const ufficio = String(dati.get('tribunale') || '').trim()
        abort.abort()
        abort = new AbortController()
        if (!ufficio) { setSede(null); return }
        const query = new URLSearchParams({ ufficio, codice: String(dati.get('pdp_ufficio') || 'PM-U') })
        ensureJson<Catalogo>(`${URL_CATALOGO}?${query}`, { signal: abort.signal })
          .then((esito) => setSede(esito.sede ?? null))
          .catch(() => { if (!abort.signal.aborted) setSede(null) })
      }, 350)
    }
    aggiorna()
    modulo.addEventListener('change', aggiorna)
    modulo.addEventListener('input', aggiorna)
    return () => { window.clearTimeout(attesa); abort.abort(); modulo.removeEventListener('change', aggiorna); modulo.removeEventListener('input', aggiorna) }
  }, [ancora])
  return sede
}

function AnteprimaSede({ sede }: { sede: Sede | null }) {
  if (!sede) return <small>Indica l'ufficio giudiziario del fascicolo: qui vedrai distretto, circondario e sede da scegliere sul PDP.</small>
  if (!sede.circondario) return <small>Ufficio non riconosciuto nei codificati del PDP: distretto e circondario si scelgono sul portale.</small>
  return (
    <small className="iu-pdp-apertura__sede">
      Sul PDP, «Ufficio Destinazione»: <strong>{sede.distretto}</strong> → <strong>{sede.circondario}</strong>
      {sede.sede ? <> → <strong>{sede.sede}</strong></> : ' → sede da scegliere sul portale'}
    </small>
  )
}

/**
 * Dati del Portale Deposito atti Penali chiesti già all'apertura del fascicolo penale
 * (maschera «Ufficio Destinazione» e «Identificazione Procedimento»). Tutti facoltativi:
 * se numero e anno mancano si usano quelli del fascicolo.
 */
export function ProcedimentoPdpApertura({ annoPredefinito }: { annoPredefinito: string }) {
  const [catalogo, setCatalogo] = useState<Catalogo | null>(null)
  const [errore, setErrore] = useState('')
  const ancora = useRef<HTMLParagraphElement>(null)
  const sede = useSedePdp(ancora)
  useEffect(() => {
    const abort = new AbortController()
    ensureJson<Catalogo>(URL_CATALOGO, { signal: abort.signal })
      .then(setCatalogo)
      .catch(() => { if (!abort.signal.aborted) setErrore('Catalogo del PDP non disponibile: potrai completare i dati dalla sezione «Deposito penale».') })
    return () => abort.abort()
  }, [])
  if (errore) return <p className="iu-fas-field--wide">{errore}</p>
  if (!catalogo) return <p className="iu-fas-field--wide" ref={ancora}>Caricamento delle scelte del PDP…</p>
  const opzioni = (voci: Voce[]) => voci.map((v) => <option key={v.codice} value={v.codice}>{v.descrizione}</option>)
  return (
    <>
      <p className="iu-fas-field--wide iu-pdp-apertura" ref={ancora}><AnteprimaSede sede={sede}/></p>
      <label className="iu-fas-field"><span>Ufficio sul PDP</span>
        <select name="pdp_ufficio" defaultValue="PM-U">{opzioni(catalogo.uffici)}</select></label>
      <label className="iu-fas-field"><span>Registro</span>
        <select name="pdp_registro" defaultValue="N">{opzioni(catalogo.registri)}</select></label>
      <label className="iu-fas-field"><span>Numero registro (RGNR)</span>
        <input name="pdp_numero" inputMode="numeric" placeholder="se vuoto, il numero di ruolo del fascicolo"/></label>
      <label className="iu-fas-field"><span>Anno registro</span>
        <input name="pdp_anno" inputMode="numeric" defaultValue={annoPredefinito} maxLength={4}/></label>
      <label className="iu-fas-field"><span>Magistrato (P.M./G.I.P.)</span><input name="pdp_magistrato"/></label>
      <label className="iu-fas-field"><span>Ruolo dell'assistito</span>
        <select name="pdp_ruolo" defaultValue="IND">{opzioni(catalogo.ruoli)}</select></label>
      <label className="iu-fas-field"><span>Altro soggetto rappresentato</span><input name="pdp_altro_nome" placeholder="facoltativo"/></label>
      <label className="iu-fas-field"><span>Ruolo dell'altro soggetto</span>
        <select name="pdp_altro_ruolo" defaultValue=""><option value="">—</option>{opzioni(catalogo.ruoli)}</select></label>
      <label className="iu-fas-check-field iu-fas-check-field--wide">
        <input type="checkbox" name="pdp_autorizzato" value="1"/>
        <span>Procedimento già autorizzato sul PDP</span>
        <small>Spunta se la nomina è già stata accolta: si sbloccano subito gli atti successivi. Altrimenti il primo deposito sarà la nomina.</small>
      </label>
    </>
  )
}
