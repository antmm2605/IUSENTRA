import { useState } from 'react'
import { AlertTriangle, CheckCircle2, Download, FileSignature } from 'lucide-react'
import { patApi } from './patApi'
import type { DocumentoPat, ParteFormweb } from './types'

const RUOLI_PARTE = [['ricorrente', 'Ricorrente'], ['resistente', 'Resistente'], ['controinteressato', 'Controinteressato'], ['escludi', 'Non nel deposito']]
const RUOLI_DOC = [['atto', 'Atto (ricorso/atto)'], ['procura', 'Procura alle liti'], ['allegato', 'Documento allegato'], ['notifica', 'Notifica (relata e atto)'], ['contributo', 'Ricevuta contributo'], ['escludi', 'Non depositare']]

const nomeParte = (p: ParteFormweb) => p.denominazione || [p.cognome, p.nome].filter(Boolean).join(' ') || 'Parte senza nome'

/** Le parti con il ruolo del Formweb e il foglio Excel ufficiale per «Carica Excel». */
export function PartiPat({ fascicoloId, parti, onRuolo }: { fascicoloId: string; parti: ParteFormweb[]; onRuolo: (id: string, ruolo: string) => Promise<void> }) {
  const conta = (r: string) => parti.filter((p) => p.ruolo === r).length
  return (
    <div className="iu-pat-parti">
      <div className="iu-pat-barra">
        {['ricorrente', 'resistente', 'controinteressato'].map((r) => conta(r) ? (
          <a key={r} href={patApi.excel(fascicoloId, r)} download><Download size={14}/> Excel {r === 'controinteressato' ? 'controinteressati' : `${r.slice(0, -1)}i`} ({conta(r)})</a>
        ) : null)}
      </div>
      <p className="iu-pat-nota">Il foglio è quello ufficiale del portale: nella scheda «Parti» usa «Carica Excel» per ricorrenti, resistenti e controinteressati.</p>
      <ul className="iu-pat-elenco">
        {parti.map((p) => (
          <li key={p.id}>
            <div>
              <strong>{nomeParte(p)}</strong>
              <span>{p.tipologia}{p.codiceFiscale ? ` · ${p.codiceFiscale}` : ' · senza codice fiscale'}{p.pec ? ` · ${p.pec}` : ''}</span>
            </div>
            <label className="iu-pat-compatto">Ruolo nel Formweb
              <select value={p.ruolo} onChange={(e) => void onRuolo(p.id, e.target.value)}>
                {RUOLI_PARTE.map(([v, e]) => <option key={v} value={v}>{e}</option>)}
              </select></label>
          </li>
        ))}
        {!parti.length ? <li>Nessuna parte: aggiungi cliente e controparti nella sezione Soggetti del fascicolo.</li> : null}
      </ul>
    </div>
  )
}

function RigaDocumento({ doc, onSalva }: { doc: DocumentoPat; onSalva: (ruolo: string, descrizione: string) => Promise<void> }) {
  const [descrizione, setDescrizione] = useState(doc.descrizione)
  const esclusa = doc.ruolo === 'escludi'
  return (
    <li className={esclusa ? 'is-escluso' : ''}>
      <div>
        <strong>{doc.nomeProposto}</strong>
        <span>{doc.nome !== doc.nomeProposto ? `Nel fascicolo: ${doc.nome} · ` : ''}{(doc.dimensione / 1024 / 1024).toFixed(2).replace('.', ',')} MB
          {doc.firma === 'pades' ? ' · firmato PAdES' : doc.firma === 'cades' ? ' · firmato CAdES' : ''}</span>
        {doc.esiti.map((e) => (
          <small key={e.codice} className={e.livello === 'errore' ? 'iu-pat-testo-errore' : ''}><AlertTriangle size={12}/> {e.messaggio}</small>
        ))}
        {!doc.esiti.length && !esclusa ? <small className="iu-pat-testo-ok"><CheckCircle2 size={12}/> Accettato dal Formweb</small> : null}
      </div>
      <div className="iu-pat-doc__scelte">
        <label className="iu-pat-compatto">Ruolo
          <select value={doc.ruolo} onChange={(e) => void onSalva(e.target.value, descrizione)}>
            {RUOLI_DOC.map(([v, e]) => <option key={v} value={v}>{e}</option>)}
          </select></label>
        {!esclusa ? (
          <label className="iu-pat-compatto">Natura e descrizione ({descrizione.length}/150)
            <input value={descrizione} maxLength={150} onChange={(e) => setDescrizione(e.target.value)} onBlur={() => { if (descrizione !== doc.descrizione) void onSalva(doc.ruolo, descrizione) }}/></label>
        ) : null}
      </div>
    </li>
  )
}

/** I file del fascicolo come li vuole il Formweb: nome ammesso, formato, firma, ruolo e descrizione. */
export function DocumentiPat({ fascicoloId, documenti, onSalva }: {
  fascicoloId: string
  documenti: DocumentoPat[]
  onSalva: (id: string, ruolo: string, descrizione: string) => Promise<void>
}) {
  const scelti = documenti.filter((d) => d.ruolo !== 'escludi')
  const bloccanti = scelti.filter((d) => d.bloccante).length
  return (
    <div className="iu-pat-documenti">
      <div className="iu-pat-barra">
        <a className="iu-pat-primario" href={patApi.pacchetto(fascicoloId)} download><FileSignature size={15}/> Scarica i {scelti.length} file con i nomi del Formweb</a>
        <span className={bloccanti ? 'iu-pat-testo-errore' : 'iu-pat-testo-ok'}>{bloccanti ? `${bloccanti} file da sistemare prima del deposito` : 'Nessun file bloccante'}</span>
      </div>
      <p className="iu-pat-nota">Il Formweb accetta nei nomi solo lettere, cifre, spazi e «_»: il pacchetto rinomina i file e aggiunge un indice con l’impronta SHA-256 di ciascuno. Si caricano fino a 5 file per volta.</p>
      <ul className="iu-pat-elenco">
        {documenti.map((doc) => <RigaDocumento key={doc.id} doc={doc} onSalva={(ruolo, descr) => onSalva(doc.id, ruolo, descr)}/>)}
        {!documenti.length ? <li>Nessun documento nel fascicolo: caricali nella sezione «Documenti e atti».</li> : null}
      </ul>
    </div>
  )
}
