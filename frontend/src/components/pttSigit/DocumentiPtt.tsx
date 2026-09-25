import { useState } from 'react'
import { AlertTriangle, CheckCircle2, FileArchive, ShieldCheck } from 'lucide-react'
import { pttApi } from './pttApi'
import type { CatalogoPtt, Controllo, DocumentoPtt } from './types'

const RUOLI = [['atto', 'Atto principale (firmato)'], ['allegato', 'Allegato'], ['escludi', 'Non depositare']]
const mb = (n: number) => `${(n / 1024 / 1024).toFixed(2).replace('.', ',')} MB`

function RigaDocumento({ doc, catalogo, onSalva }: { doc: DocumentoPtt; catalogo: CatalogoPtt | null; onSalva: (dati: { ruolo: string; tipologia: string; descrizione: string }) => Promise<void> }) {
  const [descrizione, setDescrizione] = useState(doc.descrizione)
  const esclusa = doc.ruolo === 'escludi'
  const salva = (dati: Partial<{ ruolo: string; tipologia: string; descrizione: string }>) =>
    void onSalva({ ruolo: doc.ruolo, tipologia: doc.tipologia, descrizione, ...dati })
  return (
    <li className={esclusa ? 'is-escluso' : ''}>
      <div>
        <strong>{doc.nome}</strong>
        <span>{mb(doc.dimensione)}{doc.firma === 'pades' ? ' · firmato PAdES' : doc.firma === 'cades' ? ' · firmato CAdES (.p7m)' : ' · non firmato'}</span>
        {doc.esiti.map((e) => <small key={e.codice} className={e.livello === 'errore' ? 'iu-pat-testo-errore' : ''}><AlertTriangle size={12}/> {e.messaggio}</small>)}
        {!doc.esiti.length && !esclusa ? <small className="iu-pat-testo-ok"><CheckCircle2 size={12}/> Accettato al caricamento</small> : null}
      </div>
      <div className="iu-pat-doc__scelte">
        <label className="iu-pat-compatto">Ruolo
          <select value={doc.ruolo} onChange={(e) => salva({ ruolo: e.target.value, tipologia: e.target.value === 'allegato' ? doc.tipologia || 'ALTRI DOCUMENTI' : '' })}>
            {RUOLI.map(([v, e]) => <option key={v} value={v}>{e}</option>)}
          </select></label>
        {doc.ruolo === 'allegato' ? (
          <label className="iu-pat-compatto">Tipologia (Appendice B)
            <select value={doc.tipologia} onChange={(e) => salva({ tipologia: e.target.value })}>
              {(catalogo?.allegati || [doc.tipologia]).map((v) => <option key={v} value={v}>{v}</option>)}
            </select></label>
        ) : null}
        {doc.ruolo === 'allegato' && doc.tipologia === 'ALTRI DOCUMENTI' ? (
          <label className="iu-pat-compatto">Descrizione ({descrizione.length}/70)
            <input value={descrizione} maxLength={70} onChange={(e) => setDescrizione(e.target.value)} onBlur={() => { if (descrizione !== doc.descrizione) salva({ descrizione }) }}/></label>
        ) : null}
      </div>
    </li>
  )
}

/** I file come li vuole il PTT: atto firmato per primo, allegati con la tipologia dell'Appendice B, controlli prima dell'invio. */
export function DocumentiPtt({ fascicoloId, documenti, catalogo, onSalva }: {
  fascicoloId: string
  documenti: DocumentoPtt[]
  catalogo: CatalogoPtt | null
  onSalva: (id: string, dati: { ruolo: string; tipologia: string; descrizione: string }) => Promise<void>
}) {
  const [controllo, setControllo] = useState<Controllo | null>(null)
  const [stato, setStato] = useState('')
  const scelti = documenti.filter((d) => d.ruolo !== 'escludi')
  const peso = scelti.reduce((n, d) => n + d.dimensione, 0)
  const controlla = async () => {
    setStato('Controllo dei file in corso…')
    try {
      setControllo(await pttApi.controllo(fascicoloId))
      setStato('')
    } catch (e) {
      setStato(e instanceof Error ? e.message : 'Controllo non riuscito.')
    }
  }
  return (
    <div className="iu-pat-documenti">
      <div className="iu-pat-barra">
        <button type="button" className="iu-pat-primario" onClick={() => void controlla()}><ShieldCheck size={15}/> Controlla i file come il SIGIT</button>
        <a href={pttApi.pacchetto(fascicoloId)} download><FileArchive size={15}/> Scarica i {scelti.length} file in ordine</a>
        <span className={peso > 100 * 1024 * 1024 || scelti.length > 50 ? 'iu-pat-testo-errore' : ''}>{scelti.length}/50 file · {mb(peso)} su 100 MB</span>
        {stato ? <span role="status">{stato}</span> : null}
      </div>
      {controllo ? (
        <div className="iu-pat-esito">
          <p className={controllo.conforme ? 'iu-pat-ok' : 'iu-pat-avviso'}>{controllo.conforme ? <CheckCircle2 size={15}/> : <AlertTriangle size={15}/>}
            {controllo.conforme ? ' Nessuna anomalia bloccante: puoi caricare i file nel PTT.' : ' Ci sono anomalie bloccanti: sistemale prima della trasmissione.'}</p>
          <ul className="iu-pat-elenco">
            {controllo.deposito.map((e) => <li key={e.codice}><AlertTriangle size={14}/><span>{e.messaggio}</span></li>)}
            {controllo.file.filter((f) => f.esiti.length).map((f) => (
              <li key={f.id}><div><strong>{f.nome}</strong>{f.esiti.map((e) => <small key={e.codice} className={e.livello === 'errore' ? 'iu-pat-testo-errore' : ''}>{e.messaggio}</small>)}</div></li>
            ))}
          </ul>
        </div>
      ) : null}
      <p className="iu-pat-nota">Atti: PDF/A nativo firmato CAdES o PAdES. Allegati: firma facoltativa; PDF/A, TIFF ed EML si conservano a norma, gli altri formati ammessi sono solo protocollati; niente ZIP. Fino a 50 MB per file, 100 MB e 50 file per deposito, nomi fino a 100 caratteri.</p>
      <ul className="iu-pat-elenco">
        {documenti.map((doc) => <RigaDocumento key={doc.id} doc={doc} catalogo={catalogo} onSalva={(dati) => onSalva(doc.id, dati)}/>)}
        {!documenti.length ? <li>Nessun documento nel fascicolo: caricali nella sezione «Documenti e atti».</li> : null}
      </ul>
    </div>
  )
}
