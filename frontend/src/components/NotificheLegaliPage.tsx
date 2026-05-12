import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileCheck2,
  FileSignature,
  Inbox,
  LockKeyhole,
  Mail,
  Scale,
  Send,
  ShieldCheck,
  UploadCloud,
  UserRound,
} from 'lucide-react'
import { Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyNotificheLegaliData,
  getNotificheLegaliData,
  postLegalWorkflow,
  type LegalWorkflowResult,
  type NotificheLegaliData,
} from '../notificheLegaliData'
import './NotificheLegaliPage.css'

type TabKey = 'notifica' | 'deposito' | 'cliente'

const emptyResult: LegalWorkflowResult = {
  ok: false,
  blockers: [],
  warnings: [],
  subject: '',
  body: '',
  relataText: '',
  nextActions: [],
}

function Field({
  label,
  children,
  wide = false,
  hint,
}: {
  label: string
  children: ReactNode
  wide?: boolean
  hint?: string
}) {
  return (
    <label className={`iu-legal-field ${wide ? 'iu-legal-field--wide' : ''}`}>
      <span>{label}</span>
      {children}
      {hint ? <small>{hint}</small> : null}
    </label>
  )
}

function ResultPanel({ result }: { result: LegalWorkflowResult }) {
  if (!result.message && !result.blockers.length && !result.warnings.length && !result.relataText && !result.body) {
    return (
      <Panel title="Esito controllo" subtitle="Compila i dati e avvia la verifica" icon={<ShieldCheck size={17} />}>
        <p className="iu-legal-empty">IUSENTRA prepara il testo e segnala i blocchi, poi l'avvocato controlla, firma e invia.</p>
      </Panel>
    )
  }
  return (
    <Panel
      title={result.ok ? 'Controllo superato' : 'Da completare'}
      subtitle={result.message || 'Risultato verifica'}
      icon={result.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
      className={result.ok ? 'iu-legal-result--ok' : 'iu-legal-result--warn'}
    >
      {result.blockers.length ? (
        <div className="iu-legal-list iu-legal-list--blockers">
          {result.blockers.map((item) => <span key={item}><AlertTriangle size={15} /> {item}</span>)}
        </div>
      ) : null}
      {result.warnings.length ? (
        <div className="iu-legal-list">
          {result.warnings.map((item) => <span key={item}><ShieldCheck size={15} /> {item}</span>)}
        </div>
      ) : null}
      {result.subject ? <div className="iu-legal-output"><span>Oggetto</span><strong>{result.subject}</strong></div> : null}
      {result.body ? <pre className="iu-legal-preview">{result.body}</pre> : null}
      {result.relataText ? <pre className="iu-legal-preview iu-legal-preview--relata">{result.relataText}</pre> : null}
      {result.nextActions.length ? (
        <div className="iu-legal-list iu-legal-list--actions">
          {result.nextActions.map((item) => <span key={item}><CheckCircle2 size={15} /> {item}</span>)}
        </div>
      ) : null}
    </Panel>
  )
}

function WorkflowCard({
  active,
  icon,
  title,
  text,
  onClick,
}: {
  active: boolean
  icon: React.ReactNode
  title: string
  text: string
  onClick: () => void
}) {
  return (
    <button className={`iu-legal-flow-card ${active ? 'is-active' : ''}`} type="button" onClick={onClick}>
      {icon}
      <strong>{title}</strong>
      <span>{text}</span>
    </button>
  )
}

export function NotificheLegaliPage() {
  const [data, setData] = useState<NotificheLegaliData>(emptyNotificheLegaliData)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabKey>('notifica')
  const [result, setResult] = useState<LegalWorkflowResult>(emptyResult)
  const [working, setWorking] = useState(false)

  const [notifica, setNotifica] = useState({
    avvocato_nome: '',
    avvocato_cf: '',
    avvocato_foro: '',
    studio_indirizzo: '',
    studio_citta: '',
    mittente_pec: '',
    fonte_pec_mittente: 'ReGIndE',
    mittente_pec_pubblico_elenco: true,
    assistito_nome: '',
    assistito_cf: '',
    ruolo_destinatario: 'controparte',
    destinatario_nome: '',
    destinatario_pec: '',
    fonte_pec_destinatario: 'reginde',
    data_verifica_pec: '',
    nome_file: '',
    descrizione_documento: '',
    origine_documento: 'originale',
    attestazione_conformita: '',
    procedimento_pendente: false,
    ufficio_giudiziario: '',
    sezione: '',
    numero_rg: '',
    anno_rg: '',
    ricevuta_completa: true,
    relata_firmata: false,
    approvazione_avvocato: false,
  })

  const [deposito, setDeposito] = useState({
    atto_notificato: '',
    relata_firmata: '',
    destinatario_nome: '',
    rac_file: '',
    rdac_file: '',
    dati_atto_ricevute: '',
  })

  const [cliente, setCliente] = useState({
    cliente_nome: '',
    ufficio_giudiziario: '',
    numero_rg: '',
    anno_rg: '',
    provvedimento_descrizione: '',
  })

  useEffect(() => {
    let active = true
    getNotificheLegaliData()
      .then((payload) => {
        if (!active) return
        setData(payload)
        setNotifica((current) => ({
          ...current,
          avvocato_nome: payload.defaults.avvocatoNome,
          avvocato_cf: payload.defaults.avvocatoCf,
          avvocato_foro: payload.defaults.avvocatoForo,
          studio_indirizzo: payload.defaults.studioIndirizzo,
          studio_citta: payload.defaults.studioCitta,
          mittente_pec: payload.defaults.mittentePec,
          fonte_pec_mittente: payload.defaults.fontePecMittente || 'ReGIndE',
        }))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const selectedOrigin = useMemo(() => data.originiDocumento.find((item) => item.value === notifica.origine_documento), [data.originiDocumento, notifica.origine_documento])

  const run = async (key: TabKey) => {
    setWorking(true)
    setResult({ ...emptyResult, message: 'Controllo in corso...' })
    const endpoint = key === 'notifica' ? data.azioni.notifica : key === 'deposito' ? data.azioni.provaDeposito : data.azioni.comunicazioneCliente
    const payload = key === 'notifica'
      ? { ...notifica, oggetto_pec: data.mandatorySubject, documenti: [{ nome_file: notifica.nome_file, descrizione: notifica.descrizione_documento, origine: notifica.origine_documento }] }
      : key === 'deposito'
        ? deposito
        : cliente
    const response = await postLegalWorkflow(endpoint, payload).catch(() => ({ ...emptyResult, blockers: ['Verifica non completata. Riprova tra poco.'] }))
    setResult(response)
    setWorking(false)
  }

  const changeNotifica = (key: keyof typeof notifica, value: string | boolean) => setNotifica((current) => ({ ...current, [key]: value }))
  const changeDeposito = (key: keyof typeof deposito, value: string) => setDeposito((current) => ({ ...current, [key]: value }))
  const changeCliente = (key: keyof typeof cliente, value: string) => setCliente((current) => ({ ...current, [key]: value }))

  return (
    <main className="iu-content iu-legal-notice-page">
      <section className="iu-legal-hero">
        <div>
          <span className="iu-legal-eyebrow"><Scale size={16} /> Notifiche e comunicazioni</span>
          <h1>Notifica, prova e comunicazione restano separate</h1>
          <p>La notifica ex L. 53/1994 prepara relata, controlli PEC e ricevuta completa. Il deposito raccoglie la prova. Il cliente riceve solo una comunicazione informativa.</p>
        </div>
        <div className="iu-legal-hero__actions">
          <Button href={data.azioni.pecCompose}><Send size={15} /> PEC studio</Button>
          <Button href={data.azioni.clientCompose}><Mail size={15} /> Comunica al cliente</Button>
          <Button variant="primary" href={data.azioni.depositoChecklist}><UploadCloud size={15} /> Controlli deposito</Button>
        </div>
      </section>

      <section className="iu-legal-flows" aria-label="Percorsi distinti">
        <WorkflowCard
          active={tab === 'notifica'}
          icon={<FileSignature size={21} />}
          title="Notifica ex L. 53/1994"
          text="Controparte, difensori, PA, imprese, professionisti o terzi."
          onClick={() => { setTab('notifica'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'deposito'}
          icon={<FileCheck2 size={21} />}
          title="Deposito prova notifica"
          text="Atto notificato, relata firmata, RAC e RdAC originali."
          onClick={() => { setTab('deposito'); setResult(emptyResult) }}
        />
        <WorkflowCard
          active={tab === 'cliente'}
          icon={<UserRound size={21} />}
          title="Comunica al cliente"
          text="Messaggio informativo, senza relata e senza oggetto L. 53."
          onClick={() => { setTab('cliente'); setResult(emptyResult) }}
        />
      </section>

      <section className="iu-legal-status-line">
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento dati studio...' : 'Workflow separati pronti'}</span>
        <small><LockKeyhole size={14} /> Nessun invio automatico: firma, invio e deposito restano confermati dall'avvocato.</small>
      </section>

      <section className="iu-legal-layout">
        <div className="iu-legal-form-column">
          {tab === 'notifica' ? (
            <Panel title="Relata e invio controllato" subtitle="Percorso per destinatari esterni allo studio" icon={<FileSignature size={17} />}>
              <div className="iu-legal-form-grid">
                <Field label="Oggetto PEC obbligatorio" wide hint="Il valore e' bloccato dal percorso guidato.">
                  <input value={data.mandatorySubject} readOnly />
                </Field>
                <Field label="Avvocato notificante"><input value={notifica.avvocato_nome} onChange={(event) => changeNotifica('avvocato_nome', event.currentTarget.value)} /></Field>
                <Field label="Codice fiscale avvocato"><input value={notifica.avvocato_cf} onChange={(event) => changeNotifica('avvocato_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ordine / foro"><input value={notifica.avvocato_foro} onChange={(event) => changeNotifica('avvocato_foro', event.currentTarget.value)} /></Field>
                <Field label="PEC notificante"><input type="email" value={notifica.mittente_pec} onChange={(event) => changeNotifica('mittente_pec', event.currentTarget.value)} /></Field>
                <Field label="Parte assistita"><input value={notifica.assistito_nome} onChange={(event) => changeNotifica('assistito_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA assistito"><input value={notifica.assistito_cf} onChange={(event) => changeNotifica('assistito_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ruolo destinatario">
                  <select value={notifica.ruolo_destinatario} onChange={(event) => changeNotifica('ruolo_destinatario', event.currentTarget.value)}>
                    {data.ruoliDestinatario.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    <option value="cliente">Cliente (da bloccare come notifica ordinaria)</option>
                  </select>
                </Field>
                <Field label="Destinatario"><input value={notifica.destinatario_nome} onChange={(event) => changeNotifica('destinatario_nome', event.currentTarget.value)} /></Field>
                <Field label="PEC destinatario"><input type="email" value={notifica.destinatario_pec} onChange={(event) => changeNotifica('destinatario_pec', event.currentTarget.value)} /></Field>
                <Field label="Fonte PEC destinatario">
                  <select value={notifica.fonte_pec_destinatario} onChange={(event) => changeNotifica('fonte_pec_destinatario', event.currentTarget.value)}>
                    {data.registriPec.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Data e ora verifica PEC"><input type="datetime-local" value={notifica.data_verifica_pec} onChange={(event) => changeNotifica('data_verifica_pec', event.currentTarget.value)} /></Field>
                <Field label="Nome file atto"><input value={notifica.nome_file} onChange={(event) => changeNotifica('nome_file', event.currentTarget.value)} placeholder="ricorso.pdf" /></Field>
                <Field label="Descrizione documento"><input value={notifica.descrizione_documento} onChange={(event) => changeNotifica('descrizione_documento', event.currentTarget.value)} /></Field>
                <Field label="Origine documento">
                  <select value={notifica.origine_documento} onChange={(event) => changeNotifica('origine_documento', event.currentTarget.value)}>
                    {data.originiDocumento.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                {selectedOrigin?.needsAttestazione ? (
                  <Field label="Attestazione di conformita" wide>
                    <textarea value={notifica.attestazione_conformita} rows={4} onChange={(event) => changeNotifica('attestazione_conformita', event.currentTarget.value)} />
                  </Field>
                ) : null}
                <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked={notifica.procedimento_pendente} onChange={(event) => changeNotifica('procedimento_pendente', event.currentTarget.checked)} /><span>Notifica in corso di procedimento</span></label>
                {notifica.procedimento_pendente ? (
                  <>
                    <Field label="Ufficio giudiziario"><input value={notifica.ufficio_giudiziario} onChange={(event) => changeNotifica('ufficio_giudiziario', event.currentTarget.value)} /></Field>
                    <Field label="Sezione"><input value={notifica.sezione} onChange={(event) => changeNotifica('sezione', event.currentTarget.value)} /></Field>
                    <Field label="Numero RG"><input value={notifica.numero_rg} onChange={(event) => changeNotifica('numero_rg', event.currentTarget.value)} /></Field>
                    <Field label="Anno RG"><input value={notifica.anno_rg} onChange={(event) => changeNotifica('anno_rg', event.currentTarget.value)} /></Field>
                  </>
                ) : null}
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.ricevuta_completa} onChange={(event) => changeNotifica('ricevuta_completa', event.currentTarget.checked)} /><span>Ricevuta completa</span></label>
                <label className="iu-legal-check"><input type="checkbox" checked={notifica.relata_firmata} onChange={(event) => changeNotifica('relata_firmata', event.currentTarget.checked)} /><span>Relata firmata</span></label>
                <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked={notifica.approvazione_avvocato} onChange={(event) => changeNotifica('approvazione_avvocato', event.currentTarget.checked)} /><span>Approvazione finale dell'avvocato prima dell'invio</span></label>
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('notifica')}><ShieldCheck size={16} /> {working ? 'Controllo...' : 'Controlla relata'}</button>
            </Panel>
          ) : null}

          {tab === 'deposito' ? (
            <Panel title="Prova della notifica" subtitle="Preparazione fascicolo interno e busta" icon={<FileCheck2 size={17} />}>
              <div className="iu-legal-form-grid">
                <Field label="Atto notificato"><input value={deposito.atto_notificato} onChange={(event) => changeDeposito('atto_notificato', event.currentTarget.value)} placeholder="ricorso.pdf" /></Field>
                <Field label="Relata firmata"><input value={deposito.relata_firmata} onChange={(event) => changeDeposito('relata_firmata', event.currentTarget.value)} placeholder="relata_notifica.pdf.p7m" /></Field>
                <Field label="Destinatario"><input value={deposito.destinatario_nome} onChange={(event) => changeDeposito('destinatario_nome', event.currentTarget.value)} /></Field>
                <Field label="RAC originale"><input value={deposito.rac_file} onChange={(event) => changeDeposito('rac_file', event.currentTarget.value)} placeholder="accettazione.eml" /></Field>
                <Field label="RdAC originale"><input value={deposito.rdac_file} onChange={(event) => changeDeposito('rdac_file', event.currentTarget.value)} placeholder="consegna.eml" /></Field>
                <Field label="Riferimenti ricevute in DatiAtto.xml" wide><input value={deposito.dati_atto_ricevute} onChange={(event) => changeDeposito('dati_atto_ricevute', event.currentTarget.value)} /></Field>
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('deposito')}><UploadCloud size={16} /> {working ? 'Controllo...' : 'Controlla prova deposito'}</button>
            </Panel>
          ) : null}

          {tab === 'cliente' ? (
            <Panel title="Comunicazione al cliente" subtitle="Informativa separata dalla notifica legale" icon={<UserRound size={17} />}>
              <div className="iu-legal-form-grid">
                <Field label="Cliente"><input value={cliente.cliente_nome} onChange={(event) => changeCliente('cliente_nome', event.currentTarget.value)} /></Field>
                <Field label="Ufficio"><input value={cliente.ufficio_giudiziario} onChange={(event) => changeCliente('ufficio_giudiziario', event.currentTarget.value)} /></Field>
                <Field label="Numero RG"><input value={cliente.numero_rg} onChange={(event) => changeCliente('numero_rg', event.currentTarget.value)} /></Field>
                <Field label="Anno RG"><input value={cliente.anno_rg} onChange={(event) => changeCliente('anno_rg', event.currentTarget.value)} /></Field>
                <Field label="Provvedimento o documento" wide><input value={cliente.provvedimento_descrizione} onChange={(event) => changeCliente('provvedimento_descrizione', event.currentTarget.value)} /></Field>
              </div>
              <button className="iu-legal-submit" type="button" disabled={working} onClick={() => run('cliente')}><Mail size={16} /> {working ? 'Preparazione...' : 'Prepara comunicazione'}</button>
            </Panel>
          ) : null}
        </div>

        <aside className="iu-legal-side">
          <ResultPanel result={result} />
          <Panel title="Regole di blocco" subtitle="Controlli prima di firma e invio" icon={<AlertTriangle size={17} />}>
            <div className="iu-legal-list">
              <span><ShieldCheck size={15} /> PEC mittente e destinatario da pubblico elenco.</span>
              <span><FileSignature size={15} /> Relata separata e firmata digitalmente.</span>
              <span><Inbox size={15} /> Ricevuta completa, RAC e RdAC originali.</span>
              <span><UserRound size={15} /> Il cliente resta nel percorso informativo.</span>
            </div>
          </Panel>
          <Panel title="Fonti operative" subtitle="Da verificare nei flussi reali" icon={<Scale size={17} />}>
            <div className="iu-legal-sources">
              {data.fontiOperative.map((item) => <span key={item}>{item}</span>)}
            </div>
          </Panel>
        </aside>
      </section>

      <FloatingLex
        context="notifiche-legali"
        title="Lex AI notifiche"
        body="Posso aiutarti a controllare relata, attestazione, pubblico elenco PEC e prova da depositare, distinguendo notifica e semplice comunicazione al cliente."
        primaryHref="#lex"
        primaryLabel="Controlla workflow"
        secondaryHref={data.azioni.fascicoli}
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}
