import { useState } from 'react'
import { FileSignature, Plus, Trash2, Upload } from 'lucide-react'
import { penaleApi } from './penaleApi'
import { dimensione, RUOLI_FILE, type FileScelto, type Quadro } from './types'

type Props = {
  fascicoloId: string
  documenti: Quadro['documenti']
  scelti: FileScelto[]
  contestuali: Array<{ codice: string; nome: string }>
  ammetteContestuali: boolean
  abilitanteRichiesto: boolean
  onCambia: (file: FileScelto[]) => void
  onCaricato: (documentoId: string) => Promise<void> | void
}

/** Composizione del deposito come nel PDP: atto principale, contestuali, atto abilitante, allegati. */
export function DocumentiDeposito({ fascicoloId, documenti, scelti, contestuali, ammetteContestuali, abilitanteRichiesto, onCambia, onCaricato }: Props) {
  const [documento, setDocumento] = useState('')
  const [ruolo, setRuolo] = useState(scelti.some((f) => f.ruolo === 'principale') ? 'allegato' : 'principale')
  const [caricamento, setCaricamento] = useState(false)
  const [errore, setErrore] = useState('')
  const nome = (id: string) => documenti.find((d) => d.id === id)
  const ruoli = RUOLI_FILE.filter((r) => (r.valore !== 'contestuale' || ammetteContestuali) && (r.valore !== 'principale' || !scelti.some((f) => f.ruolo === 'principale')))
  const aggiungi = (documentoId: string, ruoloScelto = ruolo) => {
    if (!documentoId || scelti.some((f) => f.documentoId === documentoId)) return
    onCambia([...scelti, { documentoId, ruolo: ruoloScelto, oggetto: '', tipoAtto: '' }])
    setDocumento('')
    setRuolo('allegato')
  }
  const modifica = (indice: number, patch: Partial<FileScelto>) => onCambia(scelti.map((f, i) => (i === indice ? { ...f, ...patch } : f)))
  const carica = async (file: File | undefined) => {
    if (!file) return
    setCaricamento(true); setErrore('')
    try {
      const esito = await penaleApi.caricaDocumento(fascicoloId, file)
      await onCaricato(esito.documento_id)
      aggiungi(esito.documento_id)
    } catch (e) { setErrore(e instanceof Error ? e.message : 'Caricamento non riuscito.') } finally { setCaricamento(false) }
  }
  return (
    <div className="iu-pdp-documenti">
      {abilitanteRichiesto ? (
        <p className="iu-pdp-avviso">Nomina in Procura senza avviso 408, 411 o 415-bis nel fascicolo: serve l’<strong>atto abilitante</strong> (es. verbale di identificazione, decreto di sequestro, certificato 335).</p>
      ) : null}
      {scelti.length ? (
        <ul className="iu-pdp-file">
          {scelti.map((f, i) => {
            const doc = nome(f.documentoId)
            return (
              <li key={f.documentoId}>
                <FileSignature size={15}/>
                <div className="iu-pdp-file__nome"><strong>{doc?.nome || f.documentoId}</strong><span>{doc ? `${dimensione(doc.dimensione)}${doc.firmato ? ' · firmato' : ''}` : ''}</span></div>
                <select aria-label="Ruolo nel deposito" value={f.ruolo} onChange={(e) => modifica(i, { ruolo: e.target.value })}>
                  {RUOLI_FILE.filter((r) => r.valore !== 'contestuale' || ammetteContestuali).map((r) => <option key={r.valore} value={r.valore}>{r.etichetta}</option>)}
                </select>
                {f.ruolo === 'contestuale' ? (
                  <select aria-label="Tipo atto contestuale" value={f.tipoAtto} onChange={(e) => modifica(i, { tipoAtto: e.target.value })}>
                    <option value="">Tipo atto…</option>
                    {contestuali.map((c) => <option key={c.codice} value={c.codice}>{c.nome}</option>)}
                  </select>
                ) : null}
                {f.ruolo === 'abilitante' || f.ruolo === 'allegato' ? (
                  <input aria-label="Oggetto" placeholder="Oggetto (max 100 caratteri)" maxLength={100} value={f.oggetto} onChange={(e) => modifica(i, { oggetto: e.target.value })}/>
                ) : null}
                <button type="button" aria-label="Togli dal deposito" onClick={() => onCambia(scelti.filter((_, j) => j !== i))}><Trash2 size={14}/></button>
              </li>
            )
          })}
        </ul>
      ) : <p className="iu-pdp-nota">Aggiungi almeno l’atto principale firmato (PAdES o CAdES).</p>}
      <div className="iu-pdp-aggiungi">
        <select aria-label="Documento del fascicolo" value={documento} onChange={(e) => setDocumento(e.target.value)}>
          <option value="">Documento del fascicolo…</option>
          {documenti.filter((d) => !scelti.some((f) => f.documentoId === d.id)).map((d) => <option key={d.id} value={d.id}>{d.nome}</option>)}
        </select>
        <select aria-label="Come" value={ruolo} onChange={(e) => setRuolo(e.target.value)}>
          {ruoli.map((r) => <option key={r.valore} value={r.valore}>{r.etichetta}</option>)}
        </select>
        <button type="button" disabled={!documento} onClick={() => aggiungi(documento)}><Plus size={14}/> Aggiungi</button>
        <label className="iu-pdp-carica">
          <Upload size={14}/> {caricamento ? 'Caricamento…' : 'Carica dal computer'}
          <input type="file" disabled={caricamento} onChange={(e) => { void carica(e.target.files?.[0]); e.target.value = '' }}/>
        </label>
      </div>
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </div>
  )
}
