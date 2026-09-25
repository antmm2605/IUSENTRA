import { useState, type FormEvent } from 'react'
import { AlertTriangle, CheckCircle2, ShieldCheck, Upload } from 'lucide-react'
import { Badge } from '../dashboard'
import { patApi } from './patApi'
import type { DepositoPat, EsitoRiepilogo } from './types'

const STATI = ['in preparazione', 'riepilogo verificato', 'inviato', 'depositato', 'rifiutato']
const FIRMA: Record<string, string> = { pades: 'firmato PAdES', cades: 'firmato CAdES (.p7m)', assente: 'non firmato', non_verificabile: 'firma non verificabile' }

function Esito({ esito }: { esito: EsitoRiepilogo }) {
  if (!esito.leggibile) return <p className="iu-pat-errore">Il file non è un PDF leggibile: carica il riepilogo scaricato con «Genera riepilogo».</p>
  const mancanti = esito.documenti.filter((d) => !d.nelRiepilogo)
  return (
    <div className="iu-pat-esito">
      <p className={esito.conforme ? 'iu-pat-ok' : 'iu-pat-avviso'}>
        {esito.conforme ? <CheckCircle2 size={15}/> : <AlertTriangle size={15}/>}
        {esito.conforme ? ' Riepilogo firmato e coerente con i file del fascicolo: puoi inviarlo dal Formweb.'
          : ' Riepilogo da sistemare prima dell’invio.'}
      </p>
      <ul className="iu-pat-elenco">
        <li><strong>{esito.titolo ? `Riepilogo Deposito ${esito.titolo}` : 'Riepilogo deposito'}</strong><span>{esito.sede || 'sede non letta'} · {FIRMA[esito.firma] || esito.firma} · {esito.impronte.length} impronte</span></li>
        {esito.documenti.map((d) => (
          <li key={d.sha256}>{d.nelRiepilogo ? <CheckCircle2 size={14}/> : <AlertTriangle size={14}/>}<span>{d.nome}: {d.nelRiepilogo ? 'impronta uguale al file del fascicolo' : 'non nel riepilogo o file cambiato dopo il caricamento'}</span></li>
        ))}
        {esito.estranee.map((h) => <li key={h}><AlertTriangle size={14}/><span>Nel riepilogo c’è un file che il fascicolo non ha (impronta {h.slice(0, 12)}…)</span></li>)}
      </ul>
      {esito.firma !== 'pades' && esito.firma !== 'cades' ? <p className="iu-pat-nota">Firma il riepilogo con la tua firma digitale e ricaricalo qui per il controllo finale.</p> : null}
      {mancanti.length ? <p className="iu-pat-nota">Se hai scelto di non depositare un file, segnalo come «Non depositare» nella scheda Documenti.</p> : null}
    </div>
  )
}

/** Verifica del riepilogo generato dal Formweb e registro dei depositi PAT del fascicolo. */
export function RiepilogoDepositi({ fascicoloId, tipo, tipi, depositi, onAggiorna }: {
  fascicoloId: string
  tipo: string
  tipi: Array<{ id: string; nome: string }>
  depositi: DepositoPat[]
  onAggiorna: () => void
}) {
  const [esito, setEsito] = useState<EsitoRiepilogo | null>(null)
  const [messaggio, setMessaggio] = useState('')
  const verifica = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const file = (evento.currentTarget.elements.namedItem('riepilogo') as HTMLInputElement).files?.[0]
    if (!file) { setMessaggio('Scegli il riepilogo scaricato dal Formweb.'); return }
    setMessaggio('Verifica in corso…')
    try {
      const risposta = await patApi.riepilogo(fascicoloId, file, tipo)
      setEsito(risposta.esito)
      setMessaggio('Riepilogo salvato tra i documenti del fascicolo.')
      onAggiorna()
    } catch (e) {
      setMessaggio(e instanceof Error ? e.message : 'Verifica non riuscita.')
    }
  }
  const aggiorna = async (evento: FormEvent<HTMLFormElement>, id: string) => {
    evento.preventDefault()
    const f = new FormData(evento.currentTarget)
    try {
      await patApi.deposito(fascicoloId, { id, stato: f.get('stato'), identificativo: String(f.get('identificativo') || '').trim() })
      onAggiorna()
    } catch (e) {
      setMessaggio(e instanceof Error ? e.message : 'Aggiornamento non riuscito.')
    }
  }
  const registra = async (evento: FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    const modulo = evento.currentTarget
    const f = new FormData(modulo)
    try {
      await patApi.deposito(fascicoloId, { tipo: f.get('tipo'), stato: f.get('stato'), identificativo: String(f.get('identificativo') || '').trim(), note: String(f.get('note') || '').trim() })
      setMessaggio('Deposito registrato nel fascicolo.')
      modulo.reset()
      onAggiorna()
    } catch (e) {
      setMessaggio(e instanceof Error ? e.message : 'Registrazione non riuscita.')
    }
  }
  return (
    <div className="iu-pat-riepilogo">
      <form className="iu-pat-carica" onSubmit={(e) => void verifica(e)}>
        <h5><ShieldCheck size={16}/> Verifica il riepilogo prima di inviarlo</h5>
        <p className="iu-pat-nota">Dopo «Genera riepilogo» scarica il PDF e caricalo qui: IUSENTRA confronta l’impronta di ogni file con quelli del fascicolo e controlla la firma. Nulla viene inviato al portale.</p>
        <div className="iu-pat-barra">
          <input type="file" name="riepilogo" accept=".pdf,.p7m,application/pdf"/>
          <button type="submit" className="iu-pat-primario"><Upload size={15}/> Verifica</button>
          {messaggio ? <span role="status">{messaggio}</span> : null}
        </div>
      </form>
      {esito ? <Esito esito={esito}/> : null}
      <h5>Depositi del fascicolo</h5>
      <ul className="iu-pat-elenco">
        {depositi.map((d) => (
          <li key={d.id}>
            <div>
              <strong>{tipi.find((t) => t.id === d.tipo)?.nome || d.tipo}</strong>
              <span>{new Date(d.aggiornatoIl).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })}{d.identificativo ? ` · identificativo ${d.identificativo}` : ''}{d.note ? ` · ${d.note}` : ''}</span>
              <Badge tone={d.stato === 'depositato' ? 'success' : d.stato === 'rifiutato' ? 'danger' : 'info'}>{d.stato}</Badge>
            </div>
            <form className="iu-pat-doc__scelte" onSubmit={(e) => void aggiorna(e, d.id)}>
              <label className="iu-pat-compatto">Stato sul portale<select name="stato" defaultValue={d.stato}>{STATI.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
              <label className="iu-pat-compatto">Identificativo deposito<input name="identificativo" defaultValue={d.identificativo || ''}/></label>
              <button type="submit">Aggiorna</button>
            </form>
          </li>
        ))}
        {!depositi.length ? <li>Nessun deposito registrato: nasce con la verifica del riepilogo o si registra qui sotto se è già stato fatto.</li> : null}
      </ul>
      <form className="iu-pat-carica" onSubmit={(e) => void registra(e)}>
        <h5>Registra un deposito già fatto</h5>
        <p className="iu-pat-nota">Per i depositi fatti prima di usare IUSENTRA o fuori dal fascicolo: stato e identificativo come li mostra «Elenco depositi» del portale. Nessun invio.</p>
        <div className="iu-pat-form">
          <label>Tipo di deposito<select name="tipo" defaultValue={tipo}>{tipi.map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}</select></label>
          <label>Stato sul portale<select name="stato" defaultValue="depositato">{STATI.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label>Identificativo deposito<input name="identificativo" placeholder="dalla ricevuta del portale"/></label>
          <label className="iu-pat-largo">Note<input name="note" maxLength={300} placeholder="es. ricorso depositato il …"/></label>
        </div>
        <div className="iu-pat-barra"><button type="submit" className="iu-pat-primario">Registra deposito</button></div>
      </form>
    </div>
  )
}
