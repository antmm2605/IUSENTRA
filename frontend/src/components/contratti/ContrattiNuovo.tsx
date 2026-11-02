import { useEffect, useState, type FormEvent } from 'react'
import { ArrowLeft, FilePlus2 } from 'lucide-react'
import { ETICHETTE_FORMA, ETICHETTE_QUALIFICAZIONE, creaPratica, getFamiglia, type Famiglia } from '../../contrattiData'
import { Badge } from '../../ui/Badge'
import { Button, ButtonLink } from '../../ui/Button'
import { EmptyState } from '../../ui/EmptyState'
import { LoadingState } from '../../ui/LoadingState'
import { Page } from '../../ui/Page'
import { Panel } from '../../ui/Panel'
import { SceltaFascicolo } from './SceltaFascicolo'

export function ContrattiNuovo({ contrattoId }: { contrattoId: string }) {
  const [famiglia, setFamiglia] = useState<Famiglia | null>(null)
  const [titolo, setTitolo] = useState('')
  const [cliente, setCliente] = useState('')
  const [fascicolo, setFascicolo] = useState('')
  const [errore, setErrore] = useState('')
  const [invio, setInvio] = useState(false)

  useEffect(() => {
    let attivo = true
    getFamiglia(contrattoId).then((dati) => {
      if (!attivo) return
      setFamiglia(dati)
      if (dati.ok) setTitolo(dati.contratto.nome)
    })
    return () => { attivo = false }
  }, [contrattoId])

  async function avvia(evento: FormEvent) {
    evento.preventDefault()
    setInvio(true)
    setErrore('')
    const esito = await creaPratica({ contratto_id: contrattoId, titolo: titolo.trim(), cliente: cliente.trim(), fascicolo_id: fascicolo })
    setInvio(false)
    if (esito.ok && esito.pratica) window.location.assign(`/contratti/pratiche/${esito.pratica.id}`)
    else setErrore(esito.message || 'Creazione non riuscita.')
  }

  const indietro = <ButtonLink tone="neutral" href="/contratti"><ArrowLeft size={16} aria-hidden="true" /> Catalogo</ButtonLink>
  if (!famiglia) return <Page title="Contratti" actions={indietro}><LoadingState title="Caricamento della scheda" /></Page>
  if (!famiglia.ok) return <Page title="Contratti" actions={indietro}><EmptyState title="Contratto non disponibile" message={famiglia.message} /></Page>
  const c = famiglia.contratto
  const domande = c.domande.length + famiglia.domande_comuni.length

  return (
    <Page title={c.nome} subtitle="Scheda del contratto e avvio della pratica guidata." actions={indietro} className="iu-ctr">
      <div className="iu-ctr-due">
        <Panel title="Scheda del contratto">
          <div className="iu-ctr-card__badge">
            <Badge tone="neutral">{ETICHETTE_QUALIFICAZIONE[c.qualificazione] || c.qualificazione}</Badge>
            <Badge tone={c.forma === 'atto_pubblico' || c.forma === 'scrittura_autenticata' ? 'warning' : 'info'}>{ETICHETTE_FORMA[c.forma]}</Badge>
          </div>
          {c.note ? <p className="iu-ctr-nota">{c.note}</p> : null}
          <h4>Riferimenti normativi</h4>
          <ul className="iu-ctr-elenco">{c.riferimenti.map((r) => <li key={r}>{r}</li>)}</ul>
          {c.varianti.length ? (
            <>
              <h4>Varianti guidate</h4>
              <ul className="iu-ctr-elenco">{c.varianti.map((v) => <li key={v.id}><strong>{v.nome}</strong> — {v.riferimenti.join('; ')}</li>)}</ul>
            </>
          ) : null}
          <h4>Struttura della bozza ({famiglia.clausole.length} articoli)</h4>
          <ol className="iu-ctr-elenco iu-ctr-elenco--numerato">{famiglia.clausole.map((cl) => <li key={cl.chiave}>{cl.titolo} <small>({cl.norma})</small></li>)}</ol>
          <p className="iu-ctr-nota">Il questionario comprende {domande} domande ({c.domande.length} specifiche e {famiglia.domande_comuni.length} comuni a tutti i contratti).</p>
        </Panel>
        <Panel title="Avvia la pratica">
          <form className="iu-ctr-form" onSubmit={avvia}>
            <label>
              <span>Titolo della pratica</span>
              <input type="text" value={titolo} required maxLength={200} onChange={(evento) => { const valore = evento.currentTarget.value; setTitolo(valore) }} />
            </label>
            <label>
              <span>Cliente</span>
              <input type="text" value={cliente} maxLength={200} placeholder="Nome o ragione sociale" onChange={(evento) => { const valore = evento.currentTarget.value; setCliente(valore) }} />
            </label>
            <SceltaFascicolo valore={fascicolo} onChange={(id, scelto) => { setFascicolo(id); if (scelto && !cliente) setCliente(scelto.cliente) }} />
            {errore ? <p className="iu-ctr-errore" role="alert">{errore}</p> : null}
            <Button type="submit" disabled={invio || !titolo.trim()} aria-busy={invio}><FilePlus2 size={16} aria-hidden="true" /> Crea pratica e apri il questionario</Button>
          </form>
        </Panel>
      </div>
    </Page>
  )
}
