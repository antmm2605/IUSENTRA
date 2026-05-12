import { useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  FileCheck2,
  FileSignature,
  FileText,
  FolderOpen,
  Inbox,
  LockKeyhole,
  Mail,
  Scale,
  Send,
  ShieldCheck,
  UploadCloud,
  UserRound,
  WandSparkles,
} from 'lucide-react'
import { Button, Panel } from './dashboard'
import { FloatingLex } from './FloatingLex'
import {
  emptyNotificheLegaliData,
  getNotificheLegaliData,
  postLegalWorkflow,
  type LegalDocumentSuggestion,
  type LegalPracticeSuggestion,
  type LegalRecipientSuggestion,
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
  templateId: '',
  templateLabel: '',
  templateVersion: '',
  selectedBlocks: [],
  checklistText: '',
  logJson: {},
  outputPlan: {},
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
      {result.templateLabel ? <div className="iu-legal-output"><span>Modello scelto</span><strong>{result.templateLabel}{result.templateVersion ? ` - ${result.templateVersion}` : ''}</strong></div> : null}
      {result.subject ? <div className="iu-legal-output"><span>Oggetto</span><strong>{result.subject}</strong></div> : null}
      {result.body ? <pre className="iu-legal-preview">{result.body}</pre> : null}
      {result.relataText ? <pre className="iu-legal-preview iu-legal-preview--relata">{result.relataText}</pre> : null}
      {result.checklistText ? <pre className="iu-legal-preview">{result.checklistText}</pre> : null}
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
    template_id: 'relata_pec_base_l53',
    pratica_codice: '',
    avvocato_nome: '',
    avvocato_cf: '',
    avvocato_foro: '',
    studio_indirizzo: '',
    studio_citta: '',
    luogo: '',
    data_relata: new Date().toISOString().slice(0, 10),
    mittente_pec: '',
    fonte_pec_mittente: 'ReGIndE',
    mittente_pec_pubblico_elenco: true,
    assistito_nome: '',
    assistito_cf: '',
    ruolo_destinatario: 'controparte',
    destinatario_nome: '',
    destinatario_cf: '',
    destinatario_pec: '',
    destinatario_parte_rappresentata: '',
    fonte_pec_destinatario: 'reginde',
    data_verifica_pec: '',
    nome_file: '',
    descrizione_documento: '',
    origine_documento: 'originale_informatico',
    hash_sha256: '',
    data_comunicazione_cancelleria: '',
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
  const [modelFields, setModelFields] = useState<Record<string, string>>({})
  const [selectedPracticeId, setSelectedPracticeId] = useState('')
  const [selectedRecipientId, setSelectedRecipientId] = useState('')
  const [selectedDocumentId, setSelectedDocumentId] = useState('')

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
          luogo: payload.defaults.studioCitta,
          mittente_pec: payload.defaults.mittentePec,
          fonte_pec_mittente: payload.defaults.fontePecMittente || 'ReGIndE',
        }))
      })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const selectedOrigin = useMemo(() => data.originiDocumento.find((item) => item.value === notifica.origine_documento), [data.originiDocumento, notifica.origine_documento])
  const selectedTemplate = useMemo(() => data.modelliRelata.find((item) => item.value === notifica.template_id), [data.modelliRelata, notifica.template_id])
  const selectedPractice = useMemo(
    () => data.precompilazione.pratiche.find((item) => item.id === selectedPracticeId),
    [data.precompilazione.pratiche, selectedPracticeId],
  )
  const recipientSuggestions = selectedPractice?.destinatari.length ? selectedPractice.destinatari : data.precompilazione.destinatari
  const documentSuggestions = selectedPractice?.documenti || []
  const automaticValuesCount = [
    notifica.avvocato_nome,
    notifica.mittente_pec,
    notifica.assistito_nome,
    notifica.destinatario_nome,
    notifica.destinatario_pec,
    notifica.nome_file,
    notifica.ufficio_giudiziario,
  ].filter(Boolean).length

  const localDateTime = () => {
    const now = new Date()
    now.setMinutes(now.getMinutes() - now.getTimezoneOffset())
    return now.toISOString().slice(0, 16)
  }

  const applyRecipient = (recipient: LegalRecipientSuggestion) => {
    setSelectedRecipientId(recipient.id)
    setNotifica((current) => ({
      ...current,
      ruolo_destinatario: recipient.ruolo || current.ruolo_destinatario,
      destinatario_nome: recipient.nome || current.destinatario_nome,
      destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf,
      destinatario_pec: recipient.pec || current.destinatario_pec,
      destinatario_parte_rappresentata: recipient.parteRappresentata || current.destinatario_parte_rappresentata,
      fonte_pec_destinatario: recipient.fontePecSuggerita || current.fonte_pec_destinatario,
      template_id: recipient.ruolo === 'difensore' ? 'relata_pec_a_difensore_costituito' : current.template_id,
    }))
    if (recipient.parteRappresentata) {
      setModelFields((current) => ({
        ...current,
        destinatario_parte_rappresentata: recipient.parteRappresentata,
        parte_rappresentata: recipient.parteRappresentata,
      }))
    }
  }

  const applyDocument = (documento: LegalDocumentSuggestion) => {
    setSelectedDocumentId(documento.id)
    setNotifica((current) => ({
      ...current,
      nome_file: documento.nomeFile || current.nome_file,
      descrizione_documento: documento.descrizione || current.descrizione_documento,
      origine_documento: documento.origine || current.origine_documento,
      hash_sha256: documento.hashSha256 || current.hash_sha256,
      template_id: documento.origine === 'copia_fascicolo_informatico'
        ? 'relata_pec_con_attestazione_fascicolo'
        : documento.origine === 'scansione_analogico'
          ? 'relata_pec_con_attestazione_scansione_analogica'
          : current.template_id,
      procedimento_pendente: documento.origine === 'copia_fascicolo_informatico' ? true : current.procedimento_pendente,
    }))
  }

  const applyPractice = (practice: LegalPracticeSuggestion) => {
    setSelectedPracticeId(practice.id)
    const unicoDestinatario = practice.destinatari.length === 1 ? practice.destinatari[0] : null
    const unicoDocumento = practice.documenti.length === 1 ? practice.documenti[0] : null
    setSelectedRecipientId(unicoDestinatario?.id || '')
    setSelectedDocumentId(unicoDocumento?.id || '')
    setNotifica((current) => ({
      ...current,
      pratica_codice: practice.numero || current.pratica_codice,
      template_id: practice.modelloSuggerito || current.template_id,
      assistito_nome: practice.assistitoNome || current.assistito_nome,
      assistito_cf: practice.assistitoCf || current.assistito_cf,
      procedimento_pendente: practice.procedimento.presente || current.procedimento_pendente,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      sezione: practice.procedimento.sezione || current.sezione,
      numero_rg: practice.procedimento.numeroRg || current.numero_rg,
      anno_rg: practice.procedimento.annoRg || current.anno_rg,
      destinatario_nome: unicoDestinatario?.nome || current.destinatario_nome || practice.controparte,
      destinatario_cf: unicoDestinatario?.codiceFiscalePiva || current.destinatario_cf || practice.controparteCf,
      destinatario_pec: unicoDestinatario?.pec || current.destinatario_pec,
      destinatario_parte_rappresentata: unicoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata,
      ruolo_destinatario: unicoDestinatario?.ruolo || current.ruolo_destinatario,
      fonte_pec_destinatario: unicoDestinatario?.fontePecSuggerita || current.fonte_pec_destinatario,
      nome_file: unicoDocumento?.nomeFile || current.nome_file,
      descrizione_documento: unicoDocumento?.descrizione || current.descrizione_documento,
      origine_documento: unicoDocumento?.origine || current.origine_documento,
      hash_sha256: unicoDocumento?.hashSha256 || current.hash_sha256,
    }))
    setModelFields((current) => ({
      ...current,
      procedimento_giudice: practice.procedimento.giudice || current.procedimento_giudice || '',
      tipo_procedimento: practice.procedimento.tipoProcedimento || current.tipo_procedimento || '',
      destinatario_parte_rappresentata: unicoDestinatario?.parteRappresentata || current.destinatario_parte_rappresentata || '',
    }))
    setCliente((current) => ({
      ...current,
      cliente_nome: practice.assistitoNome || current.cliente_nome,
      ufficio_giudiziario: practice.procedimento.ufficio || current.ufficio_giudiziario,
      numero_rg: practice.procedimento.numeroRg || current.numero_rg,
      anno_rg: practice.procedimento.annoRg || current.anno_rg,
      provvedimento_descrizione: unicoDocumento?.descrizione || current.provvedimento_descrizione,
    }))
    setDeposito((current) => ({
      ...current,
      atto_notificato: unicoDocumento?.nomeFile || current.atto_notificato,
      destinatario_nome: unicoDestinatario?.nome || current.destinatario_nome,
    }))
  }

  const run = async (key: TabKey) => {
    setWorking(true)
    setResult({ ...emptyResult, message: 'Controllo in corso...' })
    const endpoint = key === 'notifica' ? data.azioni.notifica : key === 'deposito' ? data.azioni.provaDeposito : data.azioni.comunicazioneCliente
    const payload = key === 'notifica'
      ? {
          ...notifica,
          template_fields: modelFields,
          oggetto_pec: data.mandatorySubject,
          documenti: [{
            nome_file: notifica.nome_file,
            descrizione: notifica.descrizione_documento,
            origine: notifica.origine_documento,
            hash_sha256: notifica.hash_sha256,
            data_comunicazione_cancelleria: notifica.data_comunicazione_cancelleria,
          }],
        }
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
  const changeModelField = (key: string, value: string) => setModelFields((current) => ({ ...current, [key]: value }))

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
        <span className={loading ? '' : 'is-ok'}>{loading ? 'Caricamento dati studio...' : 'Percorsi separati pronti'}</span>
        <small><LockKeyhole size={14} /> Nessun invio automatico: firma, invio e deposito restano confermati dall'avvocato.</small>
      </section>

      <section className="iu-legal-layout">
        <div className="iu-legal-form-column">
          {tab === 'notifica' ? (
            <Panel title="Relata e invio controllato" subtitle="Percorso per destinatari esterni allo studio" icon={<FileSignature size={17} />}>
              <div className="iu-legal-auto-box">
                <div className="iu-legal-auto-box__title">
                  <WandSparkles size={17} />
                  <div>
                    <strong>Compilazione assistita da IUSENTRA</strong>
                    <span>{automaticValuesCount} dati gia' proposti da studio, fascicoli, soggetti e documenti.</span>
                  </div>
                </div>
                <div className="iu-legal-form-grid">
                  <Field label="Pratica IUSENTRA" wide hint="Scegli una pratica per compilare assistito, procedimento, destinatari e documenti gia' presenti nel gestionale.">
                    <select
                      value={selectedPracticeId}
                      onChange={(event) => {
                        const practice = data.precompilazione.pratiche.find((item) => item.id === event.currentTarget.value)
                        if (practice) applyPractice(practice)
                        else {
                          setSelectedPracticeId('')
                          setSelectedRecipientId('')
                          setSelectedDocumentId('')
                        }
                      }}
                    >
                      <option value="">Seleziona pratica</option>
                      {data.precompilazione.pratiche.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
                    </select>
                  </Field>
                  <Field label="Destinatario suggerito" hint={recipientSuggestions.length ? 'PEC e fonte vengono proposte dai soggetti collegati.' : 'Aggiungi soggetti con PEC alla pratica per compilare anche questo campo.'}>
                    <select
                      value={selectedRecipientId}
                      onChange={(event) => {
                        const recipient = recipientSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (recipient) applyRecipient(recipient)
                        else setSelectedRecipientId('')
                      }}
                    >
                      <option value="">Seleziona destinatario</option>
                      {recipientSuggestions.map((item) => <option value={item.id} key={`${item.id}-${item.ruolo}`}>{item.label}{item.pec ? ` - ${item.pec}` : ''}</option>)}
                    </select>
                  </Field>
                  <Field label="Documento dal fascicolo" hint={documentSuggestions.length ? 'Origine e attestazione vengono dedotte dai metadati disponibili.' : "Seleziona una pratica con documenti per compilare l'atto."}>
                    <select
                      value={selectedDocumentId}
                      disabled={!documentSuggestions.length}
                      onChange={(event) => {
                        const document = documentSuggestions.find((item) => item.id === event.currentTarget.value)
                        if (document) applyDocument(document)
                        else setSelectedDocumentId('')
                      }}
                    >
                      <option value="">Seleziona documento</option>
                      {documentSuggestions.map((item) => <option value={item.id} key={item.id}>{item.label}</option>)}
                    </select>
                  </Field>
                </div>
                <div className="iu-legal-auto-notes">
                  <span><FolderOpen size={15} /> {data.precompilazione.pratiche.length} pratiche disponibili per la compilazione assistita.</span>
                  <span><UserRound size={15} /> {recipientSuggestions.length} destinatari con PEC suggeribili.</span>
                  <span><FileText size={15} /> {documentSuggestions.length} documenti selezionabili dalla pratica corrente.</span>
                </div>
              </div>
              <div className="iu-legal-form-grid">
                <Field label="Modello relata" wide hint={selectedTemplate?.description || 'Il sistema puo selezionare automaticamente il modello in base ai dati inseriti.'}>
                  <select value={notifica.template_id} onChange={(event) => changeNotifica('template_id', event.currentTarget.value)}>
                    {data.modelliRelata.map((item) => <option value={item.value} key={item.value}>{item.code ? `${item.code} - ${item.label}` : item.label}</option>)}
                  </select>
                </Field>
                <Field label="Codice pratica"><input value={notifica.pratica_codice} onChange={(event) => changeNotifica('pratica_codice', event.currentTarget.value)} /></Field>
                <Field label="Oggetto PEC obbligatorio" wide hint="Il valore e' bloccato dal percorso guidato.">
                  <input value={data.mandatorySubject} readOnly />
                </Field>
                <Field label="Avvocato notificante"><input value={notifica.avvocato_nome} onChange={(event) => changeNotifica('avvocato_nome', event.currentTarget.value)} /></Field>
                <Field label="Codice fiscale avvocato"><input value={notifica.avvocato_cf} onChange={(event) => changeNotifica('avvocato_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ordine / foro"><input value={notifica.avvocato_foro} onChange={(event) => changeNotifica('avvocato_foro', event.currentTarget.value)} /></Field>
                <Field label="PEC notificante"><input type="email" value={notifica.mittente_pec} onChange={(event) => changeNotifica('mittente_pec', event.currentTarget.value)} /></Field>
                <Field label="Luogo relata"><input value={notifica.luogo} onChange={(event) => changeNotifica('luogo', event.currentTarget.value)} /></Field>
                <Field label="Data relata"><input type="date" value={notifica.data_relata} onChange={(event) => changeNotifica('data_relata', event.currentTarget.value)} /></Field>
                <Field label="Parte assistita"><input value={notifica.assistito_nome} onChange={(event) => changeNotifica('assistito_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA assistito"><input value={notifica.assistito_cf} onChange={(event) => changeNotifica('assistito_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="Ruolo destinatario">
                  <select value={notifica.ruolo_destinatario} onChange={(event) => changeNotifica('ruolo_destinatario', event.currentTarget.value)}>
                    {data.ruoliDestinatario.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                    <option value="cliente">Cliente (da bloccare come notifica ordinaria)</option>
                  </select>
                </Field>
                <Field label="Destinatario"><input value={notifica.destinatario_nome} onChange={(event) => changeNotifica('destinatario_nome', event.currentTarget.value)} /></Field>
                <Field label="C.F. / P. IVA destinatario"><input value={notifica.destinatario_cf} onChange={(event) => changeNotifica('destinatario_cf', event.currentTarget.value.toUpperCase())} /></Field>
                <Field label="PEC destinatario"><input type="email" value={notifica.destinatario_pec} onChange={(event) => changeNotifica('destinatario_pec', event.currentTarget.value)} /></Field>
                <Field label="Fonte PEC destinatario">
                  <select value={notifica.fonte_pec_destinatario} onChange={(event) => changeNotifica('fonte_pec_destinatario', event.currentTarget.value)}>
                    {data.registriPec.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                <Field label="Parte rappresentata"><input value={notifica.destinatario_parte_rappresentata} onChange={(event) => changeNotifica('destinatario_parte_rappresentata', event.currentTarget.value)} /></Field>
                <Field label="Data e ora verifica PEC" hint="Da compilare solo dopo il controllo effettivo del pubblico elenco.">
                  <div className="iu-legal-inline-action">
                    <input type="datetime-local" value={notifica.data_verifica_pec} onChange={(event) => changeNotifica('data_verifica_pec', event.currentTarget.value)} />
                    <button type="button" onClick={() => changeNotifica('data_verifica_pec', localDateTime())}>Ora</button>
                  </div>
                </Field>
                <Field label="Nome file atto"><input value={notifica.nome_file} onChange={(event) => changeNotifica('nome_file', event.currentTarget.value)} placeholder="ricorso.pdf" /></Field>
                <Field label="Descrizione documento"><input value={notifica.descrizione_documento} onChange={(event) => changeNotifica('descrizione_documento', event.currentTarget.value)} /></Field>
                <Field label="Origine documento">
                  <select value={notifica.origine_documento} onChange={(event) => changeNotifica('origine_documento', event.currentTarget.value)}>
                    {data.originiDocumento.map((item) => <option value={item.value} key={item.value}>{item.label}</option>)}
                  </select>
                </Field>
                {notifica.origine_documento === 'comunicazione_cancelleria' ? (
                  <Field label="Data comunicazione cancelleria"><input type="date" value={notifica.data_comunicazione_cancelleria} onChange={(event) => changeNotifica('data_comunicazione_cancelleria', event.currentTarget.value)} /></Field>
                ) : null}
                {selectedOrigin?.needsAttestazione ? (
                  <Field label="Nota integrativa attestazione" wide hint="Il blocco base viene scelto automaticamente dall'origine del documento. Usa questo campo solo per precisazioni necessarie.">
                    <textarea value={notifica.attestazione_conformita} rows={4} onChange={(event) => changeNotifica('attestazione_conformita', event.currentTarget.value)} />
                  </Field>
                ) : null}
                {selectedTemplate?.requiresProceeding ? (
                  <label className="iu-legal-check iu-legal-field--wide"><input type="checkbox" checked readOnly /><span>Questo modello richiede i dati del procedimento.</span></label>
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
                {selectedTemplate?.fields.length ? (
                  <div className="iu-legal-model-fields iu-legal-field--wide">
                    <strong>Dati del modello scelto</strong>
                    <div className="iu-legal-form-grid">
                      {selectedTemplate.fields.map((field) => (
                        <Field label={field.label} key={field.name}>
                          <input value={modelFields[field.name] || ''} onChange={(event) => changeModelField(field.name, event.currentTarget.value)} />
                        </Field>
                      ))}
                    </div>
                  </div>
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
          <Panel title="Catalogo modelli" subtitle={data.templateCatalogVersion ? `Versione ${data.templateCatalogVersion}` : 'Modelli caricati'} icon={<FileSignature size={17} />}>
            <div className="iu-legal-list">
              <span><FileCheck2 size={15} /> {data.modelliRelata.length} modelli relata disponibili.</span>
              <span><ShieldCheck size={15} /> Attestazioni scelte in base all'origine del documento.</span>
              <span><LockKeyhole size={15} /> Nessun invio automatico senza firma e conferma finale.</span>
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
        primaryLabel="Controlla percorso"
        secondaryHref={data.azioni.fascicoli}
        secondaryLabel="Vai ai fascicoli"
      />
    </main>
  )
}
