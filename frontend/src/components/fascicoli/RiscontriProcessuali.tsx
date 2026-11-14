import { useState } from 'react'
import { SourceDocumentModal, type SourceDocument } from '../SourceDocumentModal'
import "./riscontriProcessuali.css"

type ConclusioneProcessuale = {
  codice: string
  cosa: string
  stato_etichetta: string
  prova_o_motivo: string
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
  dubbi: { testo: string; manca: string }[]
}

export type RiscontriProcessualiData = {
  stato: 'da_preparare' | 'pronto'
  impronta?: string
  conclusioni?: ConclusioneProcessuale[]
}

export default function RiscontriProcessuali({ dati, fascicoloId }: {
  dati?: Pick<RiscontriProcessualiData, "conclusioni">
  fascicoloId?: string
}) {
  const [fonte, setFonte] = useState<(SourceDocument & { fascicoloId: string }) | null>(null)
  if (!dati?.conclusioni?.length) return null
  return (
    <section className="iu-fas-riscontri" aria-label="Riscontri del fascicolo">
      <SourceDocumentModal source={fonte?.fascicoloId === fascicoloId ? fonte : null} onClose={() => setFonte(null)}/>
      <h5>Riscontri del fascicolo</h5>
      {dati.conclusioni.map((voce, indice) => (
        <details key={voce.codice + '-' + indice}>
          <summary>{[voce.cosa, voce.termine?.scadenza, voce.stato_etichetta].filter(Boolean).join(' · ')}</summary>
          <dl>
            {voce.letto.documento && <><dt>Documento</dt><dd>{fascicoloId && voce.letto.tipo === 'documento' && voce.letto.documento_id ? (
                <button type="button" onClick={() => setFonte({
                  fascicoloId,
                  href: `/fascicoli/${encodeURIComponent(fascicoloId)}/documenti/${encodeURIComponent(voce.letto.documento_id || '')}/visualizza`,
                  label: voce.letto.documento, context: voce.cosa,
                })}>{voce.letto.documento}</button>
              ) : voce.letto.documento} {voce.letto.data}
              {voce.letto.brano && <blockquote>{voce.letto.brano}</blockquote>}</dd></>}
            {!!voce.norme.length && <><dt>Norme</dt><dd>{voce.norme.map((norma) => (
              <div key={norma.norma}><a href={norma.url} target="_blank" rel="noopener noreferrer">{norma.norma}</a></div>
            ))}</dd></>}
            {voce.come && <><dt>Come procedere</dt><dd>{voce.come}</dd></>}
            {voce.perche && <><dt>Conseguenza</dt><dd>{voce.perche}</dd></>}
            {voce.prova_o_motivo && <><dt>Riscontro</dt><dd>{voce.prova_o_motivo}</dd></>}
            {voce.termine ? <><dt>Termine</dt><dd>
              {[voce.termine.scadenza, voce.termine.situazione, voce.termine.natura].filter(Boolean).join(' · ')}
              {[voce.termine.decorrenza, voce.termine.evento_decorrenza, voce.termine.computo, voce.termine.sospensione_feriale,
                voce.termine.conseguenze, voce.termine.rimedi].filter(Boolean).map((testo) => <div key={testo}>{testo}</div>)}
            </dd></> : voce.motivo_senza_termine && <><dt>Termine</dt><dd>{voce.motivo_senza_termine}</dd></>}
          </dl>
          {!!voce.dubbi.length && <ul>{voce.dubbi.map((dubbio) => <li key={dubbio.testo}>{dubbio.testo} Serve {dubbio.manca}.</li>)}</ul>}
        </details>
      ))}
    </section>
  )
}
