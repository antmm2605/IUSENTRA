import type { ComponentProps } from 'react'
import { Badge } from '../dashboard'
import './QuadroFascicolo.css'

type Tono = ComponentProps<typeof Badge>['tone']

/**
 * Testata del fascicolo: chi, dove, contro chi, quanto vale e in che stato è la pratica, in due righe.
 * RG · ufficio (rito) · giudice — cliente c. controparte · valore · stato unico.
 * Lo stato è uno solo: quello dichiarato dal quadro del fascicolo quando c'è, altrimenti lo stato
 * registrato della pratica (mai «In corso» accanto a «Pronto per archivio»).
 */
export function TestataFascicolo({ rg, ufficio, rito, giudice, cliente, controparte, valore, stato, statoTono, statoDettaglio, difensoreControparte, valoreDagliAtti, fonteControparte, fonteValore }:{
  rg: string
  ufficio: string
  rito: string
  giudice: string
  cliente: string
  controparte: string
  valore: number
  stato: string
  statoTono: Tono
  statoDettaglio?: string
  /** Dagli atti (modello della causa): il difensore della controparte, distinto dalla parte (art. 1 R.D. 1611/1933). */
  difensoreControparte?: string
  /** Dagli atti: il valore dichiarato nell'atto introduttivo o la sua mancanza (art. 14, comma 2, D.P.R. 115/2002). */
  valoreDagliAtti?: string
  fonteControparte?: string
  fonteValore?: string
}) {
  const ufficioRito = [ufficio, rito ? `(${rito})` : ''].filter(Boolean).join(' ')
  const numeroRuolo = rg.replace(/^\s*R\.?\s*G\.?\s*/i, '').trim()
  const primaRiga = [numeroRuolo ? `RG ${numeroRuolo}` : 'RG non indicato', ufficioRito || 'Ufficio non indicato', giudice ? `Giudice ${giudice}` : ''].filter(Boolean)
  const parti = [cliente || 'Cliente non collegato', controparte ? `c. ${controparte}` : ''].filter(Boolean).join(' ')
  const valoreLabel = valore > 0
    ? `Valore ${valore.toLocaleString('it-IT', { style: 'currency', currency: 'EUR' })}`
    : valoreDagliAtti || 'Valore non indicato'
  return (
    <section className="iu-fas-testata" aria-label="Dati essenziali del fascicolo">
      <p className="iu-fas-testata__riga">{primaRiga.map((voce, index) => <span key={voce}>{index ? <i aria-hidden="true">·</i> : null}{voce}</span>)}</p>
      <p className="iu-fas-testata__riga iu-fas-testata__riga--parti">
        <strong title={fonteControparte ? `Controparte da: ${fonteControparte}` : undefined}>{parti}</strong>
        {difensoreControparte ? <span><i aria-hidden="true">·</i>difesa da {difensoreControparte}</span> : null}
        <span title={valore <= 0 && fonteValore ? `Da: ${fonteValore}` : undefined}><i aria-hidden="true">·</i>{valoreLabel}</span>
        <span className="iu-fas-testata__stato" title={statoDettaglio || undefined}><Badge tone={statoTono}>{stato}</Badge></span>
      </p>
    </section>
  )
}
