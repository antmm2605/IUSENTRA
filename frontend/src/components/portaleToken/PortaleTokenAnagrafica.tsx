import { useState, type FormEvent, type ReactNode } from 'react'
import { Building2, CalendarDays, CreditCard, Mail, MapPin, Phone, Save, Shield, ShieldAlert, ShieldCheck, Smartphone, User } from 'lucide-react'
import { percorsoSezione, type DatiAnagrafica } from '../../portaleTokenData'
import { LinkSezione, type Naviga } from './PortaleTokenComuni'

type Recapiti = DatiAnagrafica['recapiti']

type Props = {
  token: string
  dati: DatiAnagrafica
  occupato: boolean
  onNaviga: Naviga
  onSalva: (recapiti: Recapiti) => void
}

function Dato({ icona, etichetta, children }: { icona: ReactNode; etichetta: string; children: ReactNode }) {
  return (
    <div className="iu-ptk-dato">
      <span className="iu-ptk-dato__icona" aria-hidden="true">{icona}</span>
      <div>
        <dt>{etichetta}</dt>
        <dd>{children}</dd>
      </div>
    </div>
  )
}

function CampoRecapito({ id, etichetta, icona, type, value, placeholder, autoComplete, onChange }: {
  id: string
  etichetta: string
  icona: ReactNode
  type: 'tel' | 'email'
  value: string
  placeholder: string
  autoComplete: string
  onChange: (valore: string) => void
}) {
  return (
    <div>
      <label className="iu-ptk-etichetta" htmlFor={id}>{icona}{etichetta}</label>
      <input
        id={id}
        className="iu-ptk-campo"
        type={type}
        value={value}
        placeholder={placeholder}
        autoComplete={autoComplete}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  )
}

export function PortaleTokenAnagrafica({ token, dati, occupato, onNaviga, onSalva }: Props) {
  const [recapiti, setRecapiti] = useState<Recapiti>(dati.recapiti)
  const { anagrafica, intestazione } = dati
  const permessi = intestazione.permessi
  const nessunRecapito = !dati.recapiti.cellulare && !dati.recapiti.telefono && !dati.recapiti.email

  function aggiorna(campo: keyof Recapiti, valore: string) {
    setRecapiti((correnti) => ({ ...correnti, [campo]: valore }))
  }

  function invia(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!occupato) onSalva(recapiti)
  }

  return (
    <div className="iu-ptk-pagina">
      <header className="iu-ptk-intro">
        <h1>I miei dati</h1>
        <p>Visualizza e aggiorna i tuoi recapiti.</p>
      </header>

      <section aria-labelledby="iu-ptk-anagrafici">
        <h2 id="iu-ptk-anagrafici" className="iu-ptk-sezione-titolo">Dati anagrafici</h2>
        <dl className="iu-ptk-card iu-ptk-dati">
          <Dato icona={<User size={18} />} etichetta="Nome completo"><strong>{anagrafica.nomeCompleto}</strong></Dato>
          {anagrafica.tipo === 'PF' && anagrafica.dataNascita ? (
            <Dato icona={<CalendarDays size={18} />} etichetta="Data di nascita">{anagrafica.dataNascita}</Dato>
          ) : null}
          {anagrafica.tipo === 'PF' && anagrafica.codiceFiscale ? (
            <Dato icona={<CreditCard size={18} />} etichetta="Codice fiscale">{anagrafica.codiceFiscale}</Dato>
          ) : null}
          {anagrafica.tipo === 'PG' && anagrafica.partitaIva ? (
            <Dato icona={<Building2 size={18} />} etichetta="Partita IVA">{anagrafica.partitaIva}</Dato>
          ) : null}
          {anagrafica.indirizzo ? (
            <Dato icona={<MapPin size={18} />} etichetta="Indirizzo">{anagrafica.indirizzo}</Dato>
          ) : null}
        </dl>
      </section>

      <section aria-labelledby="iu-ptk-recapiti">
        <h2 id="iu-ptk-recapiti" className="iu-ptk-sezione-titolo">Recapiti</h2>
        {permessi.modificaAnagrafica ? (
          <form className="iu-ptk-modulo" onSubmit={invia}>
            <div className="iu-ptk-card iu-ptk-colonna">
              <CampoRecapito id="iu-ptk-cellulare" etichetta="Cellulare" icona={<Smartphone size={16} aria-hidden="true" />} type="tel" value={recapiti.cellulare} placeholder="+39 000 000 0000" autoComplete="tel" onChange={(v) => aggiorna('cellulare', v)} />
              <CampoRecapito id="iu-ptk-telefono" etichetta="Telefono fisso" icona={<Phone size={16} aria-hidden="true" />} type="tel" value={recapiti.telefono} placeholder="02 000000" autoComplete="tel" onChange={(v) => aggiorna('telefono', v)} />
              <CampoRecapito id="iu-ptk-email" etichetta="Email" icona={<Mail size={16} aria-hidden="true" />} type="email" value={recapiti.email} placeholder="nome@esempio.it" autoComplete="email" onChange={(v) => aggiorna('email', v)} />
            </div>
            <button type="submit" className="iu-ptk-btn iu-ptk-btn--primario iu-ptk-btn--pieno" disabled={occupato}>
              <Save size={18} aria-hidden="true" />{occupato ? 'Salvataggio in corso…' : 'Salva modifiche'}
            </button>
          </form>
        ) : (
          <div className="iu-ptk-card iu-ptk-colonna">
            {dati.recapiti.cellulare ? (
              <a className="iu-ptk-contatto" href={`tel:${dati.recapiti.cellulare}`}><Smartphone size={16} aria-hidden="true" />{dati.recapiti.cellulare}</a>
            ) : null}
            {dati.recapiti.telefono ? (
              <a className="iu-ptk-contatto" href={`tel:${dati.recapiti.telefono}`}><Phone size={16} aria-hidden="true" />{dati.recapiti.telefono}</a>
            ) : null}
            {dati.recapiti.email ? (
              <a className="iu-ptk-contatto" href={`mailto:${dati.recapiti.email}`}><Mail size={16} aria-hidden="true" />{dati.recapiti.email}</a>
            ) : null}
            {nessunRecapito ? <p className="iu-ptk-muted iu-ptk-centrato">Nessun recapito registrato.</p> : null}
          </div>
        )}
      </section>

      <section aria-labelledby="iu-ptk-privacy-gdpr">
        <h2 id="iu-ptk-privacy-gdpr" className="iu-ptk-sezione-titolo">Privacy GDPR</h2>
        <div className="iu-ptk-card iu-ptk-riga">
          {intestazione.privacyFirmata ? (
            <>
              <ShieldCheck size={26} className="iu-ptk-icona-ok" aria-hidden="true" />
              <span>
                <strong>Consenso firmato</strong>
                <span className="iu-ptk-meta">Il {intestazione.dataFirmaPrivacy || '—'}</span>
              </span>
            </>
          ) : permessi.firmaPrivacy ? (
            <>
              <ShieldAlert size={26} className="iu-ptk-icona-avviso" aria-hidden="true" />
              <strong className="iu-ptk-flessibile">Consenso non ancora firmato</strong>
              <LinkSezione href={percorsoSezione(token, 'privacy')} sezione="privacy" onNaviga={onNaviga} className="iu-ptk-btn iu-ptk-btn--avviso">Firma</LinkSezione>
            </>
          ) : (
            <>
              <Shield size={26} className="iu-ptk-muted" aria-hidden="true" />
              <span className="iu-ptk-muted">Non richiesto.</span>
            </>
          )}
        </div>
      </section>
    </div>
  )
}
