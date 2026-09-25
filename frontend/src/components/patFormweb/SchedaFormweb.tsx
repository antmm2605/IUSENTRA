import { useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleDashed, Copy, Download, ExternalLink, FileArchive } from 'lucide-react'
import { patApi } from './patApi'
import type { CatalogoPat, Riga, Scheda } from './types'

const ICONE = {
  ok: <CheckCircle2 size={15} aria-label="Pronto"/>,
  manca: <AlertTriangle size={15} aria-label="Da indicare"/>,
  verifica: <AlertTriangle size={15} aria-label="Da verificare"/>,
  facoltativo: <CircleDashed size={15} aria-label="Facoltativo"/>,
}

function RigaScheda({ riga, fascicoloId }: { riga: Riga; fascicoloId: string }) {
  const [copiato, setCopiato] = useState(false)
  const copia = async () => {
    try {
      await navigator.clipboard.writeText(riga.valore)
      setCopiato(true)
      window.setTimeout(() => setCopiato(false), 1500)
    } catch {
      setCopiato(false)
    }
  }
  return (
    <li className={`iu-pat-riga iu-pat-riga--${riga.stato}`}>
      <span className="iu-pat-riga__stato">{ICONE[riga.stato]}</span>
      <div className="iu-pat-riga__testo">
        <strong>{riga.etichetta}</strong>
        <span>{riga.valore}</span>
        {riga.descrizione ? <span className="iu-pat-riga__descr">Natura del documento: {riga.descrizione}</span> : null}
        {riga.nota ? <small>{riga.nota}</small> : null}
      </div>
      <div className="iu-pat-riga__azioni">
        {riga.excel ? <a href={patApi.excel(fascicoloId, riga.excel)} download><Download size={14}/> Excel</a> : null}
        {riga.copia ? <button type="button" onClick={() => void copia()} aria-label={`Copia ${riga.etichetta}`}><Copy size={14}/> {copiato ? 'Copiato' : 'Copia'}</button> : null}
      </div>
    </li>
  )
}

/** La scheda da seguire nel Formweb: stessi passi e stesse schede del portale, con i dati già pronti da copiare. */
export function SchedaFormweb({ fascicoloId, scheda, catalogo, tipo, onTipo }: {
  fascicoloId: string
  scheda: Scheda
  catalogo: CatalogoPat | null
  tipo: string
  onTipo: (tipo: string) => void
}) {
  const totale = scheda.sezioni.reduce((n, s) => n + s.righe.filter((r) => r.stato !== 'facoltativo').length, 0)
  const pronti = scheda.sezioni.reduce((n, s) => n + s.righe.filter((r) => r.stato === 'ok').length, 0)
  return (
    <div className="iu-pat-scheda">
      <div className="iu-pat-tipi" role="radiogroup" aria-label="Tipo di deposito Formweb">
        {(catalogo?.depositi || []).map((d) => (
          <button key={d.id} type="button" role="radio" aria-checked={tipo === d.id} className={tipo === d.id ? 'is-attiva' : ''} onClick={() => onTipo(d.id)}>
            {d.nome}
          </button>
        ))}
      </div>
      <div className="iu-pat-avanzamento">
        <div>
          <strong>{scheda.nome}</strong>
          <span>{pronti} di {totale} dati pronti{scheda.mancanti.length ? ` · ${scheda.mancanti.length} da indicare` : ''}{scheda.daVerificare.length ? ` · ${scheda.daVerificare.length} da verificare` : ''}</span>
          <meter min={0} max={Math.max(totale, 1)} value={pronti} aria-label="Dati pronti per il Formweb"/>
        </div>
        <div className="iu-pat-avanzamento__azioni">
          <a className="iu-pat-primario" href={patApi.pacchetto(fascicoloId)} download><FileArchive size={15}/> Scarica i file pronti</a>
          <a className="iu-pat-primario" href={scheda.link} target="_blank" rel="noreferrer"><ExternalLink size={15}/> Apri nel Formweb</a>
        </div>
      </div>
      <ol className="iu-pat-sezioni">
        {scheda.sezioni.map((sezione, indice) => (
          <li key={sezione.titolo}>
            <h5><span>{indice + 1}</span>{sezione.titolo}</h5>
            <ul className="iu-pat-righe">
              {sezione.righe.map((riga, i) => <RigaScheda key={`${riga.etichetta}-${i}`} riga={riga} fascicoloId={fascicoloId}/>)}
            </ul>
          </li>
        ))}
      </ol>
    </div>
  )
}
