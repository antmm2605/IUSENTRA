import { useCallback, useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { CheckCircle2, ShieldCheck, Trash2, UserPlus, UsersRound } from 'lucide-react'
import { Badge } from '../dashboard'
import { CampoData } from '../../ui/CampoData'
import { oggiRoma } from '../../ui/campoDataValore'
import {
  condividiFascicolo,
  ErroreCollaboratori,
  leggiCollaboratoriFascicolo,
  revocaCollaboratoreFascicolo,
  type CollaboratoriFascicolo,
} from './collaboratoriFascicolo'
import './CollaboratoriFascicoloPanel.css'

/**
 * Collaboratori del singolo fascicolo: chi, oltre ai profili dello studio, può aprirlo e con quale ruolo.
 * Sostituisce la pagina classica /fascicoli/<id>/collaboratori (stessi permessi: fascicoli.scrivi
 * oppure gestore del fascicolo). Carica i dati solo quando il pannello è aperto.
 */
export function CollaboratoriFascicoloPanel({ fascicoloId, active }: { fascicoloId: string; active: boolean }) {
  const [dati, setDati] = useState<CollaboratoriFascicolo | null>(null)
  const [stato, setStato] = useState<'attesa' | 'caricamento' | 'pronto' | 'negato' | 'errore'>('attesa')
  const [errore, setErrore] = useState('')
  const [esito, setEsito] = useState('')
  const [invio, setInvio] = useState(false)
  const [utente, setUtente] = useState('')
  const [ruolo, setRuolo] = useState('LETTURA')
  const [scadenza, setScadenza] = useState('')
  const [note, setNote] = useState('')
  const [tag, setTag] = useState('')
  const [daRevocare, setDaRevocare] = useState('')

  const carica = useCallback(async () => {
    setStato('caricamento')
    try {
      setDati(await leggiCollaboratoriFascicolo(fascicoloId))
      setStato('pronto')
    } catch (reason) {
      setErrore(reason instanceof Error ? reason.message : 'Collaboratori non disponibili.')
      setStato(reason instanceof ErroreCollaboratori && reason.status === 403 ? 'negato' : 'errore')
    }
  }, [fascicoloId])

  useEffect(() => {
    if (active && stato === 'attesa') void carica()
  }, [active, stato, carica])

  async function aggiungi(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!utente) return
    setInvio(true)
    setErrore('')
    setEsito('')
    try {
      const risposta = await condividiFascicolo(fascicoloId, {
        id_utente: utente,
        ruolo,
        data_scadenza: scadenza,
        note: note.trim(),
        tags: tag.split(',').map((voce) => voce.trim()).filter(Boolean),
      })
      setEsito(risposta.messaggio)
      setUtente('')
      setScadenza('')
      setNote('')
      setTag('')
      await carica()
    } catch (reason) {
      setErrore(reason instanceof Error ? reason.message : 'Condivisione non riuscita.')
    } finally {
      setInvio(false)
    }
  }

  async function revoca(idUtente: string) {
    setInvio(true)
    setErrore('')
    setEsito('')
    try {
      const risposta = await revocaCollaboratoreFascicolo(fascicoloId, idUtente)
      setEsito(risposta.messaggio)
      setDaRevocare('')
      await carica()
    } catch (reason) {
      setErrore(reason instanceof Error ? reason.message : 'Revoca non riuscita.')
    } finally {
      setInvio(false)
    }
  }

  if (stato === 'attesa' || (stato === 'caricamento' && !dati)) return <p className="iu-empty">Caricamento dei collaboratori…</p>
  if (stato === 'negato') return <p className="iu-fas-collab__avviso"><ShieldCheck size={16}/>{errore}</p>
  if (!dati) return <div className="iu-fas-collab__avviso" role="alert"><span>{errore}</span><button type="button" onClick={() => void carica()}>Riprova</button></div>

  const descrizioneRuolo = dati.roleOptions.find((voce) => voce.value === ruolo)?.description || ''
  return (
    <div className="iu-fas-collab">
      <p className="iu-fas-section-intro">Profili dello studio che possono aprire questo fascicolo oltre a chi ha già il permesso sui fascicoli. Assegna il ruolo meno esteso e una scadenza se l’incarico è temporaneo.</p>
      {errore ? <p className="iu-fas-collab__msg iu-fas-collab__msg--errore" role="alert">{errore}</p> : null}
      {esito ? <p className="iu-fas-collab__msg" role="status"><CheckCircle2 size={15}/>{esito}</p> : null}
      {dati.collaborators.length ? (
        <ul className="iu-fas-collab__lista" aria-label="Collaboratori del fascicolo">
          {dati.collaborators.map((voce) => (
            <li key={voce.idUser} className={voce.expired ? 'is-scaduto' : undefined}>
              <div className="iu-fas-collab__chi">
                <strong>{voce.name}</strong>
                <span className="iu-fas-collab__meta">{voce.username}</span>
              </div>
              <div className="iu-fas-collab__stato">
                <Badge tone={voce.roleTone}>{voce.roleLabel}</Badge>
                {voce.expired ? <Badge tone="danger">Scaduto</Badge> : voce.expiring ? <Badge tone="warning">In scadenza</Badge> : null}
                <span className="iu-fas-collab__meta">Scadenza: {voce.deadlineLabel}</span>
                {voce.tags.map((etichetta) => <span className="iu-fas-collab__tag" key={etichetta}>{etichetta}</span>)}
              </div>
              {voce.notes ? <p className="iu-fas-collab__note">{voce.notes}</p> : null}
              <div className="iu-fas-collab__azioni">
                {daRevocare === voce.idUser ? (
                  <>
                    <span>Revocare l’accesso di {voce.name}?</span>
                    <button type="button" className="iu-fas-collab__pericolo" disabled={invio} onClick={() => void revoca(voce.idUser)}>Conferma revoca</button>
                    <button type="button" disabled={invio} onClick={() => setDaRevocare('')}>Annulla</button>
                  </>
                ) : (
                  <button type="button" disabled={invio} onClick={() => setDaRevocare(voce.idUser)}><Trash2 size={14}/>Revoca accesso</button>
                )}
              </div>
            </li>
          ))}
        </ul>
      ) : <p className="iu-empty"><UsersRound size={15}/> Nessun collaboratore su questo fascicolo.</p>}
      {dati.availableUsers.length ? (
        <form className="iu-fas-collab__form" onSubmit={aggiungi} aria-label="Aggiungi collaboratore al fascicolo">
          <label>Collaboratore
            <select value={utente} onChange={(event) => setUtente(event.target.value)} required>
              <option value="">Seleziona un profilo</option>
              {dati.availableUsers.map((voce) => <option key={voce.id} value={voce.id}>{voce.name} · {voce.username}</option>)}
            </select>
          </label>
          <label>Ruolo
            <select value={ruolo} onChange={(event) => setRuolo(event.target.value)}>
              {dati.roleOptions.map((voce) => <option key={voce.value} value={voce.value}>{voce.label}</option>)}
            </select>
          </label>
          <label>Scadenza dell’accesso (facoltativa)
            <CampoData min={oggiRoma()} value={scadenza} onChange={(valore) => setScadenza(valore)}/>
          </label>
          <label>Tag (separati da virgola)
            <input type="text" value={tag} onChange={(event) => setTag(event.target.value)} placeholder="es. udienza, CTU"/>
          </label>
          <label className="iu-fas-collab__largo">Note (facoltative)
            <input type="text" maxLength={1000} value={note} onChange={(event) => setNote(event.target.value)} placeholder="Motivo o perimetro della collaborazione"/>
          </label>
          {descrizioneRuolo ? <p className="iu-fas-collab__largo iu-fas-collab__aiuto">{descrizioneRuolo}</p> : null}
          <div className="iu-fas-collab__largo">
            <button type="submit" className="iu-fas-collab__invia" disabled={invio || !utente}><UserPlus size={15}/>{invio ? 'Salvataggio…' : 'Condividi il fascicolo'}</button>
          </div>
        </form>
      ) : <p className="iu-empty">Tutti gli utenti attivi hanno già accesso a questo fascicolo.</p>}
    </div>
  )
}
