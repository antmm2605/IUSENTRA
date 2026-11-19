import { lazy, Suspense, useEffect, useState } from 'react'
import { CheckCircle2, Circle, ExternalLink } from 'lucide-react'
import { apiJson } from '../../lib/apiClient'
import { generateFascicoloProforma } from '../../fascicoliData'
import { Badge } from '../dashboard'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'
import { LoadingState } from '../../ui/LoadingState'
import type { RiscontriProcessualiData } from './RiscontriProcessuali'

const RiscontriProcessuali = lazy(() => import('./RiscontriProcessuali'))

// Conto economico del fascicolo: le voci con la fonte che le giustifica e il percorso
// sentenza → proforma → pagamento → fattura di pari importo → conferma (art. 6 e art. 21 D.P.R. 633/1972).
// Lo stesso pannello si apre dalla vista economica dei fascicoli e dentro il fascicolo.

type Tono = 'neutral' | 'primary' | 'success' | 'warning' | 'danger'
type Fonte = { label: string; href: string; norma?: string }
type Riga = { voce: string; etichetta: string; importoLabel: string; stato: string; tono: Tono; dettaglio: string; fonti: Fonte[]; norma: string }
type Azione = { label: string; href?: string; comando?: 'genera_proforma' }
type Passo = { codice: string; etichetta: string; fatto: boolean; dettaglio?: string; azione?: Azione }
type ContoEconomico = { ok: boolean; aggiornamentoPendente?: boolean; riscontriProcessuali?: RiscontriProcessualiData; message?: string; righe: Riga[]; percorso: { passi: Passo[]; prossimoPasso: string } }

const VUOTO: ContoEconomico = { ok: false, message: 'Conto economico non disponibile in questo momento.', righe: [], percorso: { passi: [], prossimoPasso: '' } }
const RISCONTRI_PER_RIGA: Readonly<Record<string, string>> = { sentenza: 'spese_liquidate', contributo_unificato: 'contributo_unificato' }

export function ContoEconomicoPanel({ fascicoloId, active = true, onReady }:{ fascicoloId:string; active?:boolean; onReady?: () => void }) {
  const [conto, setConto] = useState<ContoEconomico | null>(null)
  const [ricarica, setRicarica] = useState(0)
  const [messaggio, setMessaggio] = useState('')
  const [inCorso, setInCorso] = useState(false)
  const [fonteAperta, setFonteAperta] = useState<SourceDocument | null>(null)
  const esegui = async (azione: Azione) => {
    if (azione.comando !== 'genera_proforma') return
    setInCorso(true)
    try {
      const esito = await generateFascicoloProforma(fascicoloId)
      setMessaggio(esito.message)
      setRicarica((n) => n + 1)
    } catch (err) {
      setMessaggio(err instanceof Error ? err.message : 'Non ho potuto preparare la proforma.')
    } finally {
      setInCorso(false)
    }
  }
  useEffect(() => {
    if (!active || !fascicoloId) return
    const controller = new AbortController()
    setConto(null)
    setFonteAperta(null)
    const url = `/api/v1/ui/fascicoli/${encodeURIComponent(fascicoloId)}/conto-economico`
    async function leggiConto() {
      const dati = await apiJson<ContoEconomico>(url, VUOTO, { signal: controller.signal, activity: 'Lettura del conto economico…' })
      if (controller.signal.aborted) return
      setConto(dati)
      if (dati.aggiornamentoPendente) {
        const corrente = await apiJson<ContoEconomico>(url, VUOTO, {
          signal: controller.signal, activity: false, headers: { 'X-Iusentra-Solo-Corrente': '1' },
        })
        if (controller.signal.aborted || !corrente.ok || corrente.aggiornamentoPendente) return
        setConto(corrente)
        onReady?.()
      } else if (dati.ok) {
        onReady?.()
      }
    }
    void leggiConto().catch(() => {
      if (!controller.signal.aborted) setConto((precedente) => precedente ?? VUOTO)
    })
    return () => controller.abort()
  }, [active, fascicoloId, ricarica, onReady])
  if (!active) return null
  if (!conto) return <LoadingState title="Conto economico" message="Raccolta di importi e fonti del fascicolo."/>
  if (!conto.ok) return <p className="iu-conto__vuoto">{conto.message || VUOTO.message}</p>
  const riscontri = conto.riscontriProcessuali
  const conclusioni = riscontri?.conclusioni ?? []
  const codiciDelleRighe = new Set(conto.righe.map((riga) => RISCONTRI_PER_RIGA[riga.voce]))
  const altriRiscontri = conclusioni.filter((voce) => !codiciDelleRighe.has(voce.codice))
  return (
    <section className="iu-conto" aria-label="Conto economico del fascicolo">
      <SourceDocumentModal source={fonteAperta} onClose={() => setFonteAperta(null)}/>
      {conto.aggiornamentoPendente && <p className="iu-conto__messaggio" role="status">Ultimo conto salvato. Aggiornamento delle fonti in corso.</p>}
      <ol className="iu-conto__percorso" aria-label="Percorso dal pagamento alla fattura">
        {conto.percorso.passi.map((passo) => (
          <li key={passo.codice} className={passo.fatto ? 'iu-conto__passo iu-conto__passo--fatto' : 'iu-conto__passo'}>
            {passo.fatto ? <CheckCircle2 size={16} aria-hidden="true"/> : <Circle size={16} aria-hidden="true"/>}
            <span>{passo.etichetta}</span>
            {passo.dettaglio ? <small>{passo.dettaglio}</small> : null}
            {!conto.aggiornamentoPendente && passo.azione?.href ? <a className="iu-conto__azione" href={passo.azione.href}>{passo.azione.label}</a> : null}
            {!conto.aggiornamentoPendente && passo.azione?.comando ? <button type="button" className="iu-conto__azione" disabled={inCorso} onClick={() => passo.azione && void esegui(passo.azione)}>{passo.azione.label}</button> : null}
          </li>
        ))}
      </ol>
      {messaggio ? <p className="iu-conto__messaggio" role="status">{messaggio}</p> : null}
      {!conto.aggiornamentoPendente && conto.percorso.prossimoPasso ? <p className="iu-conto__prossimo"><strong>Prossimo passo</strong> {conto.percorso.prossimoPasso}</p> : null}
      {altriRiscontri.length > 0 && <Suspense fallback={null}>
        <RiscontriProcessuali fascicoloId={fascicoloId} dati={{ ...riscontri, conclusioni: altriRiscontri }}/>
      </Suspense>}
      <table className="iu-conto__tabella">
        <thead><tr><th scope="col">Voce</th><th scope="col">Importo</th><th scope="col">Stato</th><th scope="col">Fonte</th></tr></thead>
        <tbody>
          {conto.righe.map((riga) => {
            const riscontriDellaRiga = conclusioni.filter((voce) => voce.codice === RISCONTRI_PER_RIGA[riga.voce])
            return (
            <tr key={riga.voce}>
              <th scope="row">{riga.etichetta}{riga.norma ? <small>{riga.norma}</small> : null}</th>
              <td className="iu-conto__importo">{riga.importoLabel || '—'}</td>
              <td>
                <Badge tone={riga.tono}>{riga.stato}</Badge>
                {riga.dettaglio ? <small>{riga.dettaglio}</small> : null}
                {riscontriDellaRiga.length > 0 && <Suspense fallback={null}>
                  <RiscontriProcessuali fascicoloId={fascicoloId} dati={{ ...riscontri, conclusioni: riscontriDellaRiga }} nellaRiga/>
                </Suspense>}
              </td>
              <td>
                {riga.fonti.length ? (
                  <ul className="iu-conto__fonti">
                    {riga.fonti.map((fonte) => (
                      <li key={`${fonte.href}-${fonte.label}`}>
                        {fonte.href ? <a href={fonte.href} onClick={(event) => {
                          // La fatturazione apre una finestra operativa tramite la navigazione dello studio.
                          if (fonte.href.startsWith('/fatturazione?') || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return
                          event.preventDefault()
                          setFonteAperta({ href: fonte.href, label: fonte.label, context: riga.etichetta })
                        }}>{fonte.label} <ExternalLink size={12} aria-hidden="true"/></a> : <span>{fonte.label}</span>}
                        {fonte.norma ? <small>{fonte.norma}</small> : null}
                      </li>
                    ))}
                  </ul>
                ) : <span className="iu-conto__senza-fonte">Nessuna fonte</span>}
              </td>
            </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
