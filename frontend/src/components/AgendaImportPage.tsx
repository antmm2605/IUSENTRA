import { type FormEvent, useState } from 'react'
import { AlertTriangle, CalendarCheck, CheckCircle2, Download, FileUp, Link2, Loader2, Settings2, UploadCloud } from 'lucide-react'
import { Button, Panel } from './dashboard'
import { csrfToken } from '../formSubmit'
import './AgendaImportPage.css'

export function AgendaImportPage() {
  const [status, setStatus] = useState<{ tone: 'idle' | 'loading' | 'success' | 'error'; message: string }>({
    tone: 'idle',
    message: '',
  })
  const csrf = csrfToken()

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const data = new FormData(form)
    if (csrf && !data.has('_csrf_token')) {
      data.set('_csrf_token', csrf)
    }
    setStatus({ tone: 'loading', message: 'Preparazione anteprima in corso.' })
    try {
      const response = await fetch('/agenda/importa', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'text/html,application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(csrf ? { 'X-CSRFToken': csrf } : {}),
        },
        body: data,
      })
      const html = await response.text()
      if (!response.ok) {
        throw new Error('Non ho potuto leggere il calendario. Controlla i dati e riprova.')
      }
      if (!html.trim()) {
        throw new Error('Anteprima non disponibile. Controlla file o indirizzo calendario e riprova.')
      }
      setStatus({ tone: 'success', message: 'Anteprima pronta. Apertura del controllo eventi.' })
      window.setTimeout(() => {
        document.open()
        document.write(html)
        document.close()
      }, 80)
    } catch (error) {
      setStatus({
        tone: 'error',
        message: error instanceof Error ? error.message : 'Importazione non riuscita. Controlla i campi e riprova.',
      })
    }
  }

  const statusIcon = status.tone === 'loading'
    ? <Loader2 size={16} aria-hidden="true" />
    : status.tone === 'success'
      ? <CheckCircle2 size={16} aria-hidden="true" />
      : status.tone === 'error'
        ? <AlertTriangle size={16} aria-hidden="true" />
        : null

  return (
    <main className="iu-content iu-agenda-import-page">
      <section className="iu-agenda-import-hero">
        <div>
          <span><UploadCloud size={16} /> Agenda studio</span>
          <h1>Importa calendario</h1>
          <p>Carica un file ICS oppure leggi un calendario remoto autorizzato, controllando tipo evento e promemoria prima dell'importazione.</p>
        </div>
        <div className="iu-agenda-import-hero__actions">
          <Button href="/agenda"><CalendarCheck size={15} /> Agenda</Button>
          <Button href="/impostazioni/calendario"><Settings2 size={15} /> Calendari</Button>
        </div>
      </section>

      <section className="iu-agenda-import-grid">
        <form className="iu-agenda-import-form" encType="multipart/form-data" onSubmit={handleSubmit}>
          {csrf ? <input type="hidden" name="_csrf_token" value={csrf} /> : null}
          <input type="hidden" name="fase" value="upload" />
          <header>
            <FileUp size={18} />
            <div>
              <strong>Sorgente calendario</strong>
              <span>Scegli file locale o URL remoto, poi conferma gli eventi nella schermata di anteprima.</span>
            </div>
          </header>

          <div className="iu-agenda-import-choice" role="group" aria-label="Tipo sorgente calendario">
            <label>
              <input type="radio" name="modalita_import" value="file" defaultChecked />
              <span><FileUp size={16} /> File ICS</span>
            </label>
            <label>
              <input type="radio" name="modalita_import" value="url" />
              <span><Link2 size={16} /> URL calendario</span>
            </label>
          </div>

          <label>
            <span>File calendario</span>
            <input type="file" name="file_ics" accept=".ics,text/calendar" />
          </label>
          <label>
            <span>URL calendario remoto</span>
            <input type="url" name="source_url" placeholder="https://..." />
          </label>
          <div className="iu-agenda-import-row">
            <label>
              <span>Sorgente</span>
              <select name="sorgente" defaultValue="generico">
                <option value="generico">Calendario esterno</option>
                <option value="google">Google Calendar</option>
                <option value="outlook">Outlook / Microsoft 365</option>
                <option value="apple">Apple Calendar</option>
                <option value="webcal">Webcal</option>
              </select>
            </label>
            <label>
              <span>Tipo predefinito</span>
              <select name="default_tipo" defaultValue="ALTRO">
                <option value="UDIENZA">Udienza</option>
                <option value="CONSULTAZIONE">Consultazione</option>
                <option value="RIUNIONE">Riunione</option>
                <option value="DEPOSITO">Deposito</option>
                <option value="SCADENZA">Scadenza</option>
                <option value="ALTRO">Altro</option>
              </select>
            </label>
          </div>
          <div className="iu-agenda-import-row">
            <label>
              <span>Promemoria</span>
              <select name="default_reminder_minuti" defaultValue="60">
                <option value="15">15 minuti prima</option>
                <option value="30">30 minuti prima</option>
                <option value="60">1 ora prima</option>
                <option value="1440">1 giorno prima</option>
              </select>
            </label>
            <label>
              <span>Nome profilo remoto</span>
              <input type="text" name="profile_name" placeholder="Calendario studio" />
            </label>
          </div>
          <label className="iu-agenda-import-check">
            <input type="checkbox" name="salva_profilo" value="1" />
            <span>Salva la sorgente remota nelle impostazioni calendario</span>
          </label>
          {status.tone !== 'idle' ? (
            <div className={`iu-agenda-import-status is-${status.tone}`} role={status.tone === 'error' ? 'alert' : 'status'}>
              {statusIcon}
              <span>{status.message}</span>
            </div>
          ) : null}
          <footer>
            <button type="submit" disabled={status.tone === 'loading'}><Download size={16} /> {status.tone === 'loading' ? 'Preparazione...' : 'Carica anteprima'}</button>
            <a href="/agenda">Annulla</a>
          </footer>
        </form>

        <aside className="iu-agenda-import-side">
          <Panel title="Prima di importare" subtitle="Controlli operativi" icon={<CalendarCheck size={17} />}>
            <div className="iu-agenda-import-checklist">
              <span>Gli eventi vengono mostrati in anteprima prima del salvataggio.</span>
              <span>Gli orari gia occupati restano presidiati dal controllo dell'agenda.</span>
              <span>Le sorgenti remote possono essere collegate alla sincronizzazione calendari.</span>
            </div>
          </Panel>
          <Panel title="Azioni collegate" subtitle="Calendari e appuntamenti" icon={<Settings2 size={17} />}>
            <div className="iu-agenda-import-links">
              <a href="/agenda/nuovo">Nuovo appuntamento</a>
              <a href="/impostazioni/calendario">Sincronizzazione calendari</a>
              <a href="/scadenziario">Scadenziario</a>
            </div>
          </Panel>
        </aside>
      </section>
    </main>
  )
}
