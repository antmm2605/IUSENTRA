import { lazy, Suspense, useEffect, useState } from 'react'
import { formatDateIt } from '../formatting'
import { SourceDocumentModal, type SourceDocument } from './SourceDocumentModal'
import './VerificaNotifichePanel.css'
import VerificaNotificheForm, { type ContestoVerificato } from './VerificaNotificheForm'

const ConoscenzaNotifichePanel = lazy(() => import('./ConoscenzaNotifichePanel'))

export type VerificaNotifiche = {
  ok: boolean; message: string; fascicolo_id: string; puo_verificare: boolean; documenti: Array<{ id: string; nome: string }>
  obblighi: Array<{
    chiave: string; documento: string; atti: string; stato: string; motivo: string; scadenza: string
    formula: string; fonti: string[]; avvertenze: string; dopo: string; verifiche: string[]; source_href: string
    destinatari: Array<{ nome: string; presso: string; fonte: string }>
    documentoId: string; contesto_verificato?: ContestoVerificato
    dati_mancanti?: Array<{ campo: string; descrizione: string }>
    calcoli: Array<{ explanation: string; formula: string; destinazione_da_verificare: boolean; requiresLegalReview: boolean }>
    fonti_verificate: Array<{ id: string; titolo: string; reader_url: string }>
  }>
}

export default function VerificaNotifichePanel({ fascicoloId, verifica, documentoId, onSaved }: { fascicoloId?: string; verifica?: VerificaNotifiche; documentoId?: string; onSaved?: () => void }) {
  const [data, setData] = useState<VerificaNotifiche | null>(verifica || null)
  const [errore, setErrore] = useState('')
  const [source, setSource] = useState<SourceDocument | null>(null)
  const [catalogo, setCatalogo] = useState(false)
  useEffect(() => {
    if (verifica) { setData(verifica); return }
    if (!fascicoloId) return
    const controller = new AbortController()
    void fetch(`/api/v1/ui/controllo-studio/fascicoli/${encodeURIComponent(fascicoloId)}/verifica-notifiche`, {
      credentials: 'same-origin', headers: { Accept: 'application/json' }, signal: controller.signal,
    }).then(async (response) => {
      const payload = await response.json() as VerificaNotifiche
      if (!response.ok || !payload.ok) throw new Error(payload.message || 'Verifica non disponibile.')
      setData(payload)
    }).catch((error: unknown) => {
      if (!controller.signal.aborted) setErrore(error instanceof Error ? error.message : 'Verifica non disponibile.')
    })
    return () => controller.abort()
  }, [fascicoloId, verifica])
  return <section className="iu-cs-verifica" aria-label="Verifica degli obblighi di notifica">
    <h3>Atti da notificare e termini</h3>
    {errore ? <p role="alert">{errore}</p> : !data ? <p role="status">Consultazione delle letture del fascicolo…</p> : <>
      <p>{data.message}</p>
      {data.obblighi.filter((item) => !documentoId || item.documentoId === documentoId).map((item) => <article key={item.chiave}>
        <h4>{item.atti}</h4><p><strong>Documento:</strong> {item.documento}</p>
        <p><strong>Valutazione:</strong> {item.stato === 'facoltativo' ? 'Scelta del difensore' : item.stato === 'notificato' ? 'Prova verificata' : 'Da esaminare'}</p>
        {item.motivo ? <p>{item.motivo}</p> : null}
        <p><strong>Data proposta:</strong> {item.scadenza ? formatDateIt(item.scadenza) : 'Non determinabile dai dati disponibili'}</p>
        {item.formula ? <p><strong>Regola:</strong> {item.formula}</p> : null}
        {item.calcoli?.map((calcolo, index) => <div key={index}><p><strong>Computo:</strong> {calcolo.formula}</p><p>{calcolo.explanation}</p>{calcolo.destinazione_da_verificare ? <p>Conferma Italia/estero prima di usare la data.</p> : null}</div>)}
        <ul>{item.destinatari.map((destinatario) => <li key={destinatario.nome}>{destinatario.nome} · {destinatario.presso} · {destinatario.fonte}</li>)}</ul>
        <p><strong>Fonti:</strong> {item.fonti.join('; ')}</p>
        {item.fonti_verificate?.map((fonte) => <button key={fonte.id} type="button" onClick={() => setSource({ href: fonte.reader_url, label: fonte.titolo, context: 'Fonte ufficiale della regola di notifica' })}>Leggi {fonte.titolo}</button>)}
        {item.avvertenze ? <p>{item.avvertenze}</p> : null}
        {item.dopo ? <p><strong>Dopo la notifica:</strong> {item.dopo}</p> : null}
        <ul>{item.verifiche.map((testo) => <li key={testo}>{testo}</li>)}</ul>
        <button type="button" className="iu-cs-aggiorna" onClick={() => setSource({ href: item.source_href,
          label: item.documento, context: item.atti })}>Leggi il documento</button>
        {data.puo_verificare ? <VerificaNotificheForm fascicoloId={data.fascicolo_id} documentoId={item.documentoId} documenti={data.documenti} contesto={item.contesto_verificato}
          onRead={(id) => { const doc = data.documenti.find((d) => d.id === id); if (doc) setSource({ href: `/fascicoli/${encodeURIComponent(data.fascicolo_id)}/documenti/${encodeURIComponent(id)}/visualizza`, label: doc.nome, context: item.atti }) }}
          onSaved={(updated) => { setData(updated); onSaved?.() }}/>
          : <p>Per confermare i dati servono i permessi di modifica del fascicolo e lettura delle comunicazioni.</p>}
      </article>)}
    </>}
    <button type="button" className="iu-cs-aggiorna" aria-expanded={catalogo} onClick={() => setCatalogo(!catalogo)}>{catalogo ? 'Chiudi la ricerca' : 'Consulta altri casi di notifica'}</button>
    {catalogo ? <Suspense fallback={<p role="status">Apertura della ricerca…</p>}><ConoscenzaNotifichePanel/></Suspense> : null}
    <SourceDocumentModal source={source} onClose={() => setSource(null)}/>
  </section>
}
