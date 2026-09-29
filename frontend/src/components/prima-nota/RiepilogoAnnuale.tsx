import { useEffect, useState } from 'react'
import { Calculator, FileDown } from 'lucide-react'

type Mese = { mese: string; incassi: number; pagamenti: number }
type Riepilogo = {
  ok: boolean
  message?: string
  anno?: number
  regime?: 'forfettario' | 'ordinario'
  compensi_incassati?: number
  anticipazioni_rimborsate?: number
  anticipazioni_per_clienti?: number
  spese_deducibili?: number
  contributi_previdenziali_versati?: number
  imposte_versate?: number
  mesi?: Mese[]
  stima?: Record<string, string | number>
  registro_iva?: { liquidazioni: Array<Record<string, string | number>>; proforma_escluse: number; totale_imponibile: number; totale_iva: number; fatture: number; note: string[] }
  note?: string[]
  avvisi?: string[]
}

const euro = (valore: number | undefined) => new Intl.NumberFormat('it-IT', { style: 'currency', currency: 'EUR' }).format(Number(valore || 0))

const ETICHETTE_STIMA: Record<string, string> = {
  reddito_forfettario: 'Reddito forfettario (78%)',
  contributi_dedotti: 'Contributi dedotti',
  imponibile: 'Imponibile',
  aliquota: 'Aliquota imposta sostitutiva',
  imposta_sostitutiva: 'Imposta sostitutiva stimata',
  reddito_lavoro_autonomo: 'Reddito di lavoro autonomo stimato',
}

/** Riepilogo per cassa dell'anno (art. 54 TUIR; L. 190/2014) e IVA a debito dalle fatture trasmesse. */
export function RiepilogoAnnuale() {
  const annoCorrente = new Date().getFullYear()
  const [anno, setAnno] = useState(annoCorrente)
  const [startup, setStartup] = useState(false)
  const [dati, setDati] = useState<Riepilogo | null>(null)

  useEffect(() => {
    const controllo = new AbortController()
    setDati(null)
    fetch(`/api/v1/ui/prima-nota/riepilogo?anno=${anno}${startup ? '&startup=1' : ''}`, { credentials: 'same-origin', signal: controllo.signal, headers: { Accept: 'application/json' } })
      .then((r) => r.json())
      .then((payload: Riepilogo) => setDati(payload))
      .catch(() => { if (!controllo.signal.aborted) setDati({ ok: false, message: 'Riepilogo non disponibile.' }) })
    return () => controllo.abort()
  }, [anno, startup])

  const anni = Array.from({ length: 6 }, (_, i) => annoCorrente - i)
  return (
    <section className="iu-pn-annual" aria-label="Riepilogo dell'anno">
      <header>
        <div>
          <strong><Calculator size={16}/> Riepilogo dell'anno per il commercialista</strong>
          <span>Compensi e spese per cassa, stima del reddito e IVA a debito delle fatture trasmesse.</span>
        </div>
        <div className="iu-pn-annual__controls">
          <label><span>Anno</span>
            <select value={anno} onChange={(e) => setAnno(Number(e.target.value))}>
              {anni.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
          </label>
          {dati?.regime === 'forfettario' ? (
            <label className="iu-pn-annual__check"><input type="checkbox" checked={startup} onChange={(e) => setStartup(e.target.checked)}/> Primi cinque anni (5%)</label>
          ) : null}
        </div>
      </header>
      {!dati ? <p role="status">Calcolo del riepilogo…</p> : !dati.ok ? <p role="alert">{dati.message}</p> : (
        <>
          <div className="iu-pn-annual__grid">
            <article><small>Compensi incassati</small><strong>{euro(dati.compensi_incassati)}</strong></article>
            <article><small>Spese deducibili</small><strong>{euro(dati.spese_deducibili)}</strong></article>
            <article><small>Contributi Cassa Forense versati</small><strong>{euro(dati.contributi_previdenziali_versati)}</strong></article>
            <article><small>Anticipazioni per i clienti (art. 15)</small><strong>{euro(dati.anticipazioni_per_clienti)}</strong></article>
          </div>
          {dati.stima ? (
            <dl className="iu-pn-annual__estimate">
              <div className="iu-pn-annual__row"><dt>Regime</dt><dd>{dati.regime === 'forfettario' ? 'Forfettario (L. 190/2014)' : 'Ordinario o semplificato (art. 54 TUIR)'}</dd></div>
              {Object.entries(dati.stima).filter(([k]) => k in ETICHETTE_STIMA).map(([k, v]) => (
                <div key={k} className="iu-pn-annual__row"><dt>{ETICHETTE_STIMA[k]}</dt><dd>{k === 'aliquota' ? `${v}%` : euro(Number(v))}</dd></div>
              ))}
            </dl>
          ) : null}
          {dati.registro_iva ? (
            <div className="iu-pn-annual__iva">
              <strong>IVA a debito ({dati.registro_iva.fatture} fatture trasmesse, {euro(dati.registro_iva.totale_imponibile)} di imponibile)</strong>
              <ul>
                {dati.registro_iva.liquidazioni.map((l) => (
                  <li key={String(l.periodo)}>{l.periodo}: {euro(Number(l.iva_a_debito))}{l.interessi_1_per_cento ? ` + interessi 1% ${euro(Number(l.interessi_1_per_cento))}` : ''}</li>
                ))}
                {!dati.registro_iva.liquidazioni.length ? <li>Nessuna fattura trasmessa nell'anno.</li> : null}
              </ul>
              {dati.registro_iva.proforma_escluse ? <small>{dati.registro_iva.proforma_escluse} parcelle non trasmesse allo SdI escluse (avvisi di parcella).</small> : null}
              <a href={`/prima-nota/registro-iva.csv?anno=${dati.anno}`}><FileDown size={15}/> Registro fatture emesse (CSV)</a>
            </div>
          ) : null}
          {(dati.avvisi || []).map((a) => <p key={a} className="iu-pn-annual__warn">{a}</p>)}
          <ul className="iu-pn-annual__notes">{[...(dati.note || []), ...(dati.registro_iva?.note || [])].map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
    </section>
  )
}

export default RiepilogoAnnuale
