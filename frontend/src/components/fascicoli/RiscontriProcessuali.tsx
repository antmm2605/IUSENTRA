import { useState } from 'react'
import { NormativeArticleLink } from '../NormativeArticleLink'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'
import "./riscontriProcessuali.css"

type ConclusioneProcessuale = {
  codice: string
  cosa: string
  stato?: string
  stato_etichetta: string
  prova_o_motivo: string
  prova_notifica?: { invio_id: string; accettazione_id: string; consegne_ids: string[] }
  come: string
  perche: string
  letto: { documento: string; documento_id?: string; tipo?: string; data: string; brano: string }
  norme: { norma: string; url: string }[]
  termine?: {
    scadenza: string; situazione: string; natura: string; decorrenza: string
    evento_decorrenza: string; computo: string; sospensione_feriale: string
    conseguenze: string; rimedi: string
  }
  motivo_senza_termine?: string
  dubbi: { testo: string; manca: string; fonte?: { tipo: string; oggetto_id: string; nome: string } }[]
}

export type RiscontriProcessualiData = {
  stato: 'da_preparare' | 'pronto'
  impronta?: string
  aggiornamento_pendente?: boolean
  conclusioni?: ConclusioneProcessuale[]
}

function statoRiscontro(voce: ConclusioneProcessuale): string {
  if (voce.codice === 'notifica_ricorso_decreto_415' && voce.stato === 'non_dovuto') {
    return 'Ordine storico'
  }
  return voce.stato_etichetta
}

export default function RiscontriProcessuali({ dati, fascicoloId, nellaRiga = false }: {
  dati?: Pick<RiscontriProcessualiData, "conclusioni" | "aggiornamento_pendente">
  fascicoloId?: string
  nellaRiga?: boolean
}) {
  const [fonte, setFonte] = useState<(SourceDocument & { fascicoloId: string }) | null>(null)
  if (!dati?.conclusioni?.length) return null
  const apriDocumento = (id: string, label: string, context: string) => {
    if (!fascicoloId) return
    setFonte({
      fascicoloId,
      href: `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(id)}/visualizza`,
      label, context,
    })
  }
  return (
    <section className={nellaRiga ? 'iu-fas-riscontri iu-fas-riscontri--riga' : 'iu-fas-riscontri'} aria-label="Riscontri del fascicolo">
      <SourceDocumentModal source={fonte?.fascicoloId === fascicoloId ? fonte : null} onClose={() => setFonte(null)}/>
      {!nellaRiga && <h5>Riscontri del fascicolo</h5>}
      {dati.aggiornamento_pendente && <p role="status">Ultimo riscontro salvato. Aggiornamento in corso.</p>}
      {dati.conclusioni.map((voce, indice) => (
        <details key={voce.codice + '-' + indice}>
          <summary>{nellaRiga && dati.conclusioni?.length === 1
            ? 'Motivazione e riscontri'
            : [voce.cosa, voce.termine?.scadenza, statoRiscontro(voce)].filter(Boolean).join(' · ')}</summary>
          <dl>
            {voce.letto.documento && <><dt>Documento</dt><dd>{fascicoloId && voce.letto.tipo === 'documento' && voce.letto.documento_id ? (
                <button type="button" onClick={() => apriDocumento(voce.letto.documento_id || '', voce.letto.documento, voce.cosa)}>{voce.letto.documento}</button>
              ) : voce.letto.documento} {voce.letto.data}
              {voce.letto.brano && <blockquote>{voce.letto.brano}</blockquote>}</dd></>}
            {!!voce.norme.length && <><dt>Norme</dt><dd>{voce.norme.map((norma) => (
              <div key={norma.norma}>
                {norma.url ? <NormativeArticleLink url={norma.url} article={norma.norma}>{norma.norma}</NormativeArticleLink> : norma.norma}
              </div>
            ))}</dd></>}
            {voce.come && <><dt>Come procedere</dt><dd>{voce.come}</dd></>}
            {voce.perche && <><dt>Conseguenza</dt><dd>{voce.perche}</dd></>}
            {voce.prova_o_motivo && <><dt>Riscontro</dt><dd>
              {voce.prova_o_motivo}
              {fascicoloId && voce.prova_notifica && [
                { id: voce.prova_notifica.invio_id, label: voce.codice === 'notifica_ordinata' ? 'PEC di rinnovazione' : 'PEC di notifica' },
                { id: voce.prova_notifica.accettazione_id, label: 'Ricevuta di accettazione' },
                ...voce.prova_notifica.consegne_ids.map((id, index) => ({
                  id, label: `Ricevuta di consegna ${index + 1}`,
                })),
              ].filter(({ id }, index, fonti) => id && fonti.findIndex((fonte) => fonte.id === id) === index).map(({ id, label }) => <div key={id}>
                <button type="button" onClick={() => apriDocumento(id, label, voce.cosa)}>{label}</button>
              </div>)}
            </dd></>}
            {voce.termine ? <><dt>Termine</dt><dd>
              {[voce.termine.scadenza, voce.termine.situazione, voce.termine.natura].filter(Boolean).join(' · ')}
              {[voce.termine.decorrenza, voce.termine.evento_decorrenza, voce.termine.computo, voce.termine.sospensione_feriale,
                voce.termine.conseguenze, voce.termine.rimedi].filter(Boolean).map((testo) => <div key={testo}>{testo}</div>)}
            </dd></> : voce.motivo_senza_termine && <><dt>Termine</dt><dd>{voce.motivo_senza_termine}</dd></>}
          </dl>
          {!!voce.dubbi.length && <ul>{voce.dubbi.map((dubbio) => {
            const documento = dubbio.fonte
            return <li key={dubbio.testo}>
              {dubbio.testo} Serve {dubbio.manca}.
              {fascicoloId && documento?.tipo === 'documento' && documento.oggetto_id !== voce.letto.documento_id &&
                <div><button type="button" onClick={() => apriDocumento(documento.oggetto_id, documento.nome, voce.cosa)}>
                  {documento.nome}
                </button></div>}
            </li>
          })}</ul>}
        </details>
      ))}
    </section>
  )
}
