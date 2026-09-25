import { useState } from 'react'
import { FileUp } from 'lucide-react'
import { penaleApi } from './penaleApi'

type Esito = Awaited<ReturnType<typeof penaleApi.importa>>
const TIPI: Record<string, string> = { procedimenti: 'Procedimenti autorizzati', depositi: 'Depositi', udienze: 'Storico udienze' }

/** Import degli elenchi esportati dal PDP con «Esporta»: si prendono solo le righe di questo fascicolo. */
export function ImportaPdp({ fascicoloId, onImportato }: { fascicoloId: string; onImportato: () => void }) {
  const [file, setFile] = useState<File | null>(null)
  const [anteprima, setAnteprima] = useState<Esito | null>(null)
  const [fatto, setFatto] = useState<Esito | null>(null)
  const [errore, setErrore] = useState('')
  const [lavoro, setLavoro] = useState(false)
  const esegui = async (prova: boolean, scelto = file) => {
    if (!scelto) return
    setLavoro(true); setErrore('')
    const dati = new FormData()
    dati.append('export', scelto, scelto.name)
    dati.append('anteprima', prova ? '1' : '0')
    try {
      const esito = await penaleApi.importa(fascicoloId, dati)
      if (prova) { setAnteprima(esito); setFatto(null) } else { setFatto(esito); setAnteprima(null); onImportato() }
    } catch (e) { setErrore(e instanceof Error ? e.message : 'Import non riuscito.') } finally { setLavoro(false) }
  }
  return (
    <div className="iu-pdp-importa">
      <p className="iu-pdp-nota">Sul PDP apri «Procedimenti Autorizzati», «Depositi» o lo «Stato procedimento → Storico udienze», premi <strong>Esporta</strong> e carica qui il file.
        Le udienze future entrano in agenda; i depositi aggiornano il loro stato; i procedimenti autorizzano questo fascicolo.</p>
      <label className="iu-pdp-carica">
        <FileUp size={15}/> {file ? file.name : 'Scegli il file esportato (.xlsx o .csv)'}
        <input type="file" accept=".xlsx,.csv" onChange={(e) => { const f = e.target.files?.[0] || null; setFile(f); setFatto(null); void esegui(true, f) }}/>
      </label>
      {anteprima ? (
        <div className="iu-pdp-esito-import">
          <strong>{TIPI[anteprima.tipo] || anteprima.tipo}</strong>
          <span>{anteprima.pertinenti} righe di questo fascicolo su {anteprima.totale}{anteprima.ignorate ? ` (${anteprima.ignorate} di altri procedimenti, ignorate)` : ''}.</span>
          <button type="button" className="iu-pdp-primario" disabled={lavoro || !anteprima.pertinenti} onClick={() => void esegui(false)}>Importa {anteprima.pertinenti} righe</button>
        </div>
      ) : null}
      {fatto ? (
        <p className="iu-pdp-ok" role="status">
          Import completato: {fatto.importati} nuove, {fatto.aggiornati} aggiornate{fatto.inAgenda ? `, ${fatto.inAgenda} udienze in agenda` : ''}.
        </p>
      ) : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </div>
  )
}
