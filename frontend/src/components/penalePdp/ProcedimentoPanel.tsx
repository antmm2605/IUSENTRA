import { useState, type FormEvent } from 'react'
import { CalendarDays, Plus, Trash2 } from 'lucide-react'
import { penaleApi } from './penaleApi'
import { dataOra, type Quadro } from './types'

type Props = { fascicoloId: string; quadro: Quadro; onAggiorna: () => void }

function valori(evento: FormEvent<HTMLFormElement>): Record<string, unknown> {
  const dati = new FormData(evento.currentTarget)
  return Object.fromEntries([...dati.entries()].map(([k, v]) => [k, v === 'on' ? true : v]))
}

/** Registri del procedimento negli uffici che attraversa e soggetti rappresentati con il ruolo PDP. */
export function ProcedimentoPanel({ fascicoloId, quadro, onAggiorna }: Props) {
  const [messaggio, setMessaggio] = useState('')
  const [errore, setErrore] = useState('')
  const esegui = async (azione: () => Promise<unknown>, fatto: string, form?: HTMLFormElement) => {
    setErrore(''); setMessaggio('')
    try { await azione(); setMessaggio(fatto); form?.reset(); onAggiorna() } catch (e) { setErrore(e instanceof Error ? e.message : 'Operazione non riuscita.') }
  }
  const p = quadro.procedimento
  return (
    <div className="iu-pdp-procedimento">
      <section>
        <h4>Procedimento autorizzato</h4>
        <p className="iu-pdp-nota">È «autorizzato» quando nel registro dell’ufficio c’è il tuo codice fiscale: il PDP lo mostra fra i procedimenti autorizzati e solo lì si depositano gli atti successivi.</p>
        <div className="iu-pdp-riga">
          <label className="iu-pdp-spunta"><input type="checkbox" checked={p.autorizzato}
            onChange={(e) => void esegui(() => penaleApi.procedimento(fascicoloId, { autorizzato: e.target.checked, fonte: 'Verificato dall’avvocato sul PDP' }), 'Stato del procedimento aggiornato.')}/>
            Il procedimento compare fra i miei procedimenti autorizzati</label>
          <label className="iu-pdp-spunta"><input type="checkbox" checked={p.avocatoPg}
            onChange={(e) => void esegui(() => penaleApi.procedimento(fascicoloId, { avocatoPg: e.target.checked }), 'Avocazione aggiornata.')}/>
            Avocato dalla Procura Generale</label>
        </div>
        {p.fonteAutorizzazione ? <small>{p.fonteAutorizzazione}{p.autorizzatoIl ? ` · ${dataOra(p.autorizzatoIl)}` : ''}</small> : null}
      </section>
      <section>
        <h4>Registri</h4>
        {quadro.registri.length ? (
          <ul className="iu-pdp-lista">
            {quadro.registri.map((r) => (
              <li key={r.id}>
                <strong>{r.protocollo}</strong><span>{r.ufficioEtichetta}{r.magistrato ? ` · ${r.magistrato}` : ''}</span>
                {r.corrente ? <em>ufficio attuale</em> : null}
                <button type="button" aria-label={`Elimina ${r.protocollo}`} onClick={() => void esegui(() => penaleApi.eliminaRegistro(fascicoloId, r.id), 'Registro eliminato.')}><Trash2 size={14}/></button>
              </li>
            ))}
          </ul>
        ) : <p className="iu-pdp-nota">Nessun registro: aggiungi l’ufficio e il numero del procedimento, come nel PDP («PM: N2023/1096»).</p>}
        <form className="iu-pdp-form" onSubmit={(e) => { e.preventDefault(); void esegui(() => penaleApi.registro(fascicoloId, valori(e)), 'Registro salvato.', e.currentTarget) }}>
          <label>Ufficio<select name="ufficio" required defaultValue="">{[<option key="" value="" disabled>Scegli</option>, ...quadro.uffici.map((u) => <option key={u.codice} value={u.codice}>{u.descrizione}</option>)]}</select></label>
          <label>Registro<select name="registro" defaultValue="N">{quadro.registriTipi.map((r) => <option key={r.codice} value={r.codice}>{r.descrizione}</option>)}</select></label>
          <label>Numero<input name="numero" inputMode="numeric" required placeholder="1096"/></label>
          <label>Anno<input name="anno" inputMode="numeric" required maxLength={4} placeholder="2023"/></label>
          <label>Magistrato<input name="magistrato" placeholder="facoltativo"/></label>
          <label className="iu-pdp-spunta"><input type="checkbox" name="corrente" defaultChecked/> Ufficio attuale</label>
          <button type="submit"><Plus size={14}/> Aggiungi registro</button>
        </form>
      </section>
      <section>
        <h4>Soggetti rappresentati</h4>
        {quadro.soggetti.length ? (
          <ul className="iu-pdp-lista">
            {quadro.soggetti.map((s) => (
              <li key={s.id}>
                <strong>{s.nome}</strong><span>{s.ruoloEtichetta}{s.codiceFiscale ? ` · ${s.codiceFiscale}` : ''}</span><em>{s.iniziali}</em>
                <button type="button" aria-label={`Elimina ${s.nome}`} onClick={() => void esegui(() => penaleApi.eliminaSoggetto(fascicoloId, s.id), 'Soggetto eliminato.')}><Trash2 size={14}/></button>
              </li>
            ))}
          </ul>
        ) : <p className="iu-pdp-nota">Nessun soggetto: ogni deposito PDP è fatto nell’interesse di soggetti precisi, con il loro ruolo.</p>}
        <form className="iu-pdp-form" onSubmit={(e) => { e.preventDefault(); void esegui(() => penaleApi.soggetto(fascicoloId, valori(e)), 'Soggetto salvato.', e.currentTarget) }}>
          <label>Nome e cognome o denominazione<input name="nome" required/></label>
          <label>Ruolo<select name="ruolo" required defaultValue="">{[<option key="" value="" disabled>Scegli</option>, ...quadro.ruoli.map((r) => <option key={r.codice} value={r.codice}>{r.descrizione}</option>)]}</select></label>
          <label>Codice fiscale<input name="codiceFiscale" maxLength={16}/></label>
          <label>Natura<select name="natura" defaultValue="fisica"><option value="fisica">Persona fisica</option><option value="giuridica">Persona giuridica</option></select></label>
          <button type="submit"><Plus size={14}/> Aggiungi soggetto</button>
        </form>
      </section>
      {quadro.udienze.length ? (
        <section>
          <h4>Udienze dal PDP</h4>
          <ul className="iu-pdp-lista">
            {quadro.udienze.map((u) => (
              <li key={u.id}><CalendarDays size={14}/><strong>{dataOra(u.quando)}</strong><span>{[u.ufficio, u.aula && `aula ${u.aula}`, u.luogo, u.causale].filter(Boolean).join(' · ')}</span>{u.inAgenda ? <em>in agenda</em> : null}</li>
            ))}
          </ul>
        </section>
      ) : null}
      {messaggio ? <p className="iu-pdp-ok" role="status">{messaggio}</p> : null}
      {errore ? <p className="iu-pdp-errore" role="alert">{errore}</p> : null}
    </div>
  )
}
