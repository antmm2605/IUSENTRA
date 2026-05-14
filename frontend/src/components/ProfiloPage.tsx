import { useEffect, useState } from 'react'
import { KeyRound, LockKeyhole, Mail, RefreshCw, ShieldCheck, UserRound } from 'lucide-react'
import { Badge, Panel } from './dashboard'
import { JsonPostForm } from './JsonPostForm'
import './ProfiloPage.css'

type ProfilePayload = {
  ok: boolean
  user: {
    id: string
    username: string
    email: string
    nome_completo: string
    ruolo: string
    ultimo_accesso: string
  }
  security: {
    twoFactorEnabled: boolean
    setupSecret: string
    setupUri: string
  }
  passwordRequired: boolean
  message?: string
}

const emptyProfile: ProfilePayload = {
  ok: false,
  user: {
    id: '',
    username: '',
    email: '',
    nome_completo: '',
    ruolo: '',
    ultimo_accesso: '',
  },
  security: {
    twoFactorEnabled: false,
    setupSecret: '',
    setupUri: '',
  },
  passwordRequired: false,
}

function roleLabel(value: string): string {
  const role = value.toLowerCase()
  if (role === 'admin') return 'Amministratore'
  if (role === 'avvocato') return 'Avvocato'
  if (role === 'collaboratore') return 'Collaboratore'
  if (role === 'segreteria') return 'Segreteria'
  if (role === 'cliente') return 'Cliente'
  return value || 'Profilo studio'
}

export function ProfiloPage() {
  const [data, setData] = useState<ProfilePayload>(emptyProfile)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let active = true
    setLoading(true)
    fetch('/api/v1/ui/profilo', {
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    })
      .then(async (response) => {
        const payload = await response.json().catch(() => null) as ProfilePayload | null
        if (!response.ok || !payload?.ok) throw new Error(payload?.message || 'Profilo non disponibile.')
        return payload
      })
      .then((payload) => {
        if (active) {
          setData(payload)
          setError('')
        }
      })
      .catch((exc) => {
        if (active) setError(exc instanceof Error ? exc.message : 'Profilo non disponibile.')
      })
      .finally(() => {
        if (active) setLoading(false)
      })
    return () => {
      active = false
    }
  }, [])

  const displayName = data.user.nome_completo || data.user.username || 'Utente studio'

  return (
    <main className="iu-content iu-profile-page">
      <section className="iu-profile-hero">
        <div>
          <span><UserRound size={16} /> Profilo personale</span>
          <h1>{displayName}</h1>
          <p>Gestisci dati personali, password e verifica in due passaggi con controlli tracciati nello studio.</p>
        </div>
        <div className="iu-profile-hero__meta">
          <Badge tone={data.security.twoFactorEnabled ? 'success' : 'warning'}>
            {data.security.twoFactorEnabled ? 'Accesso protetto' : 'Protezione da completare'}
          </Badge>
          <strong>{roleLabel(data.user.ruolo)}</strong>
        </div>
      </section>

      {error ? <section className="iu-profile-alert"><RefreshCw size={16} /> {error}</section> : null}
      {loading ? <section className="iu-profile-alert"><RefreshCw size={16} /> Caricamento profilo...</section> : null}

      <section className="iu-profile-grid">
        <Panel title="Dati personali" subtitle="Nome ed email usati nello studio" icon={<UserRound size={17} />}>
          <JsonPostForm className="iu-profile-form" action="/profilo" redirectTo="/profilo" successMessage="Profilo aggiornato.">
            <input type="hidden" name="azione" value="aggiorna" />
            <label>
              <span>Nome completo</span>
              <input name="nome_completo" defaultValue={data.user.nome_completo} autoComplete="name" />
            </label>
            <label>
              <span>Email</span>
              <input name="email" type="email" defaultValue={data.user.email} autoComplete="email" />
            </label>
            <button type="submit"><Mail size={16} /> Salva dati</button>
          </JsonPostForm>
        </Panel>

        <Panel title="Password" subtitle="Aggiornamento credenziali personali" icon={<LockKeyhole size={17} />}>
          {data.passwordRequired ? <div className="iu-profile-warning">Per continuare imposta una nuova password personale.</div> : null}
          <JsonPostForm className="iu-profile-form" action="/profilo" redirectTo="/profilo" successMessage="Password aggiornata.">
            <input type="hidden" name="azione" value="password" />
            <label>
              <span>Password attuale</span>
              <input name="password_old" type="password" autoComplete="current-password" required />
            </label>
            <label>
              <span>Nuova password</span>
              <input name="password_new" type="password" autoComplete="new-password" minLength={8} required />
            </label>
            <button type="submit"><KeyRound size={16} /> Aggiorna password</button>
          </JsonPostForm>
        </Panel>

        <Panel title="Verifica in due passaggi" subtitle="Protezione dell'account personale" icon={<ShieldCheck size={17} />}>
          <div className="iu-profile-2fa">
            <strong>{data.security.twoFactorEnabled ? 'Verifica attiva' : 'Verifica non attiva'}</strong>
            <span>{data.security.twoFactorEnabled ? 'Ogni accesso puo essere confermato con codice temporaneo.' : 'Aggiungi un codice temporaneo generato dalla tua app di autenticazione.'}</span>
          </div>

          {!data.security.twoFactorEnabled && !data.security.setupSecret ? (
            <JsonPostForm className="iu-profile-form" action="/profilo" redirectTo="/profilo" successMessage="Configurazione avviata.">
              <input type="hidden" name="azione" value="2fa_genera" />
              <button type="submit"><ShieldCheck size={16} /> Avvia configurazione</button>
            </JsonPostForm>
          ) : null}

          {!data.security.twoFactorEnabled && data.security.setupSecret ? (
            <JsonPostForm className="iu-profile-form" action="/profilo" redirectTo="/profilo" successMessage="Verifica attivata.">
              <input type="hidden" name="azione" value="2fa_conferma" />
              <div className="iu-profile-secret">
                <span>Chiave configurazione</span>
                <strong>{data.security.setupSecret}</strong>
                {data.security.setupUri ? <a href={data.security.setupUri}>Apri nell'app di autenticazione</a> : null}
              </div>
              <label>
                <span>Codice dell'app</span>
                <input name="codice_2fa" inputMode="numeric" autoComplete="one-time-code" required />
              </label>
              <button type="submit"><ShieldCheck size={16} /> Conferma codice</button>
            </JsonPostForm>
          ) : null}

          {data.security.twoFactorEnabled ? (
            <JsonPostForm className="iu-profile-form" action="/profilo" redirectTo="/profilo" successMessage="Verifica disattivata.">
              <input type="hidden" name="azione" value="2fa_disattiva" />
              <label>
                <span>Password attuale</span>
                <input name="pwd_disattiva" type="password" autoComplete="current-password" required />
              </label>
              <button type="submit"><LockKeyhole size={16} /> Disattiva verifica</button>
            </JsonPostForm>
          ) : null}
        </Panel>
      </section>
    </main>
  )
}
