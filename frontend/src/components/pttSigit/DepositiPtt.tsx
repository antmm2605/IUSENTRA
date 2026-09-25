import { useState, type FormEvent } from 'react'
import { Badge } from '../dashboard'
import { pttApi } from './pttApi'
import type { CatalogoPtt, DepositoPtt } from './types'

const tono = (stato: string) => stato.includes('anomalia') ? 'warning' : stato === 'rigettata' ? 'danger' : stato === 'depositata' || stato === 'acquisita' ? 'success' : 'info'

/** Lo stato della NIR come lo mostra «Completamento NIR» del PTT: ricevuta, esito dei controlli e numero di ruolo. */
export function DepositiPtt({ fascicoloId, tipo, catalogo, depositi, onAggiorna }: {
  fascicoloId: string
  tipo: string
  catalogo: CatalogoPtt | null
  depositi: DepositoPtt[]
  onAggiorna: () => void
}) {
  const [messaggio, setMessaggio] = useState('')
  const stati = catalogo?.statiNir || []
  const nomeTipo = (id: string) => catalogo?.depositi.find((d) => d.id === id)?.nome || id
  const invia = async (evento: FormEvent<HTMLFormElement>, id?: string) => {
    evento.preventDefault()
    const modulo = evento.currentTarget
    const f = new FormData(modulo)
    const dati: Record<string, unknown> = { stato: f.get('stato'), ricevuta: String(f.get('ricevuta') || '').trim(), rg: String(f.get('rg') || '').trim() }
    if (id) dati.id = id
    else { dati.tipo = f.get('tipo'); dati.note = String(f.get('note') || '').trim() }
    try {
      await pttApi.deposito(fascicoloId, dati)
      setMessaggio(id ? 'Stato aggiornato.' : 'Deposito registrato nel fascicolo.')
      if (!id) modulo.reset()
      onAggiorna()
    } catch (e) {
      setMessaggio(e instanceof Error ? e.message : 'Operazione non riuscita.')
    }
  }
  return (
    <div className="iu-pat-riepilogo">
      <p className="iu-pat-nota">Dopo «Trasmetti» il PTT invia via PEC la ricevuta di trasmissione e, entro 24 ore, l’esito dei controlli con il numero RGR/RGA. Le anomalie di formato si vedono solo nell’area riservata («Completamento NIR»).</p>
      <ul className="iu-pat-elenco">
        {depositi.map((d) => (
          <li key={d.id}>
            <div>
              <strong>{nomeTipo(d.tipo)}</strong>
              <span>{new Date(d.aggiornatoIl).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'short' })}{d.ricevuta ? ` · ricevuta ${d.ricevuta}` : ''}{d.rg ? ` · RG ${d.rg}` : ''}{d.note ? ` · ${d.note}` : ''}</span>
              <Badge tone={tono(d.stato)}>{d.stato}</Badge>
            </div>
            <form className="iu-pat-doc__scelte" onSubmit={(e) => void invia(e, d.id)}>
              <label className="iu-pat-compatto">Stato della NIR<select name="stato" defaultValue={d.stato}>{stati.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
              <label className="iu-pat-compatto">Identificativo ricevuta<input name="ricevuta" defaultValue={d.ricevuta || ''}/></label>
              <label className="iu-pat-compatto">RGR/RGA<input name="rg" defaultValue={d.rg || ''}/></label>
              <button type="submit">Aggiorna</button>
            </form>
          </li>
        ))}
        {!depositi.length ? <li>Nessun deposito registrato.</li> : null}
      </ul>
      <form className="iu-pat-carica" onSubmit={(e) => void invia(e)}>
        <h5>Registra un deposito</h5>
        <div className="iu-pat-form">
          <label>Tipologia<select name="tipo" defaultValue={tipo}>{(catalogo?.depositi || []).map((t) => <option key={t.id} value={t.id}>{t.nome}</option>)}</select></label>
          <label>Stato della NIR<select name="stato" defaultValue="trasmessa">{stati.map((s) => <option key={s} value={s}>{s}</option>)}</select></label>
          <label>Identificativo ricevuta<input name="ricevuta" placeholder="dalla ricevuta di trasmissione"/></label>
          <label>RGR/RGA<input name="rg" placeholder="es. 1234/2026"/></label>
          <label className="iu-pat-largo">Note<input name="note" maxLength={300} placeholder="es. depositato prima di IUSENTRA"/></label>
        </div>
        <div className="iu-pat-barra"><button type="submit" className="iu-pat-primario">Registra deposito</button>{messaggio ? <span role="status">{messaggio}</span> : null}</div>
      </form>
    </div>
  )
}
