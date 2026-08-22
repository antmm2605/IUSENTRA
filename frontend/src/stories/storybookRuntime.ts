import fixtures from '../test/fixtures/app-v2-ui-fixtures.json'

type ApiPayload = Record<string, unknown>

declare global {
  interface Window {
    __IUSENTRA_STORYBOOK_FETCH__?: typeof fetch
  }
}

const storybookUser = fixtures.users.admin
const storybookTenant = fixtures.tenants.tenantA

const featureFlags = {
  ...fixtures.featureFlags.on,
  'features.legalNotificationPresidia.enabled': true,
  'features.legalNotificationPresidia.primary': true,
  'lex.legalSkills.enabled': true,
  'lex.legalSkills.trustLayer': true,
  'lex.legalSkills.customSkills': true,
  'lex.legalSkills.scheduledAgents': true,
  'lex.autonomousLearning': true,
  'lex.workflowAgents.enabled': true,
  'lex.workflowAgents.writeActions': true,
  'lex.workflowAgents.scheduledRuns': true,
  'lex.dailyPlan.enabled': true,
  'lex.dailyPlan.scheduledRuns': true,
  'lex.dailyPlan.writeProposals': true,
  'lex.procedureCompletion.enabled': true,
  'routes.appV2.dailyPlan.home': true,
  'routes.appV2.legalSkills.catalog': true,
  'routes.appV2.legalSkills.profile': true,
  'routes.appV2.legalSkills.run': true,
  'routes.appV2.legalSkills.reviewQueue': true,
  'routes.appV2.legalSkills.promptLibrary': true,
  'routes.appV2.legalSkills.pathways': true,
  'routes.appV2.workflowAgents.home': true,
  'routes.appV2.workflowAgents.reviewQueue': true,
  'routes.appV2.clientPortal.enabled': true,
  'routes.appV2.clientPortal.notifications': true,
  'routes.appV2.clientPortal.webPush': true,
  'routes.appV2.clientPortal.videoCalls': true,
  'routes.appV2.clientPortal.signatures': true,
} as const

function ensureBootstrap() {
  let bootstrap = document.getElementById('iusentra-react-bootstrap')
  if (!bootstrap) {
    bootstrap = document.createElement('script')
    bootstrap.id = 'iusentra-react-bootstrap'
    bootstrap.setAttribute('type', 'application/json')
    document.body.prepend(bootstrap)
  }
  bootstrap.textContent = JSON.stringify({
    user: {
      id: storybookUser.id,
      username: 'avvocato-operativo-mock',
      displayName: storybookUser.displayName,
      email: storybookUser.email,
      role: storybookUser.role,
      initials: 'AO',
    },
    tenant: storybookTenant,
    permissions: [
      ...storybookUser.permissions,
      'agenda.leggi', 'agenda.scrivi', 'audit.leggi', 'backup.leggi',
      'clienti.leggi', 'clienti.scrivi', 'documenti.leggi', 'fascicoli.leggi',
      'fascicoli.scrivi', 'fatturazione.leggi', 'legal_skills.leggi',
      'messaggi.leggi', 'scadenziario.leggi', 'scadenziario.scrivi',
      'telematico.leggi', 'utenti.leggi', 'utenti.scrivi', 'ai.usa',
    ],
    featureFlags,
    actions: { profile: '/profilo', logout: '/logout' },
  })
}

function sharedPayload(): ApiPayload {
  const { resources } = fixtures
  const fascicolo = resources.fascicolo
  const documento = resources.documento
  const cliente = resources.cliente
  const scadenza = resources.scadenza
  const eventoAgenda = resources.eventoAgenda
  const comunicazione = resources.comunicazione
  const deposito = resources.deposito
  const auditLog = resources.auditLog
  return {
    ok: true,
    success: true,
    message: '',
    errore: '',
    errors: [],
    data: [fascicolo],
    items: [fascicolo],
    results: [fascicolo],
    rows: [fascicolo],
    total: 1,
    total_count: 1,
    count: 1,
    pagination: { page: 1, page_size: 25, total: 1, pages: 1 },
    fascicoli: [fascicolo],
    fascicolo,
    matter: fascicolo,
    documenti: [documento],
    documents: [documento],
    documento,
    document: documento,
    clienti: [cliente],
    cliente,
    contacts: [cliente],
    scadenze: [scadenza],
    deadlines: [scadenza],
    eventi: [eventoAgenda],
    events: [eventoAgenda],
    appuntamenti: [eventoAgenda],
    appointments: [eventoAgenda],
    comunicazioni: [comunicazione],
    messages: [comunicazione],
    emails: [comunicazione],
    pec: [comunicazione],
    deposito,
    deposits: [deposito],
    audit: [auditLog],
    logs: [auditLog],
    settings: resources.settingsMascherati,
    tenant: storybookTenant,
    user: storybookUser,
  }
}

function strumentiLegaliPayload(): ApiPayload {
  return {
    ...sharedPayload(),
    strumenti: [{
      id: 'interessi-legali',
      title: 'Interessi legali',
      subtitle: 'Calcola gli interessi maturati su un capitale.',
      categoria: 'Calcoli',
      icon: 'percent',
      reso_in_react: true,
      azione: 'calcola_interessi_legali',
      campi: [
        { name: 'capitale', label: 'Capitale', type: 'number', value: '1000', min: 0, step: '0.01' },
        { name: 'data_inizio', label: 'Data iniziale', type: 'date', value: '01/01/2026' },
        { name: 'data_fine', label: 'Data finale', type: 'date', value: '22/08/2026' },
      ],
    }],
    categorie: ['Calcoli'],
    tool_attivo: 'interessi-legali',
    totale: 1,
    totale_in_react: 1,
    endpoint_calcolo: '/api/v1/ui/strumenti-legali/calcola',
  }
}

function importQuickOrganizerPayload(): ApiPayload {
  return {
    ok: true,
    generatedAt: '22/08/2026 10:00',
    page: {
      title: 'Importa pratiche',
      subtitle: 'Acquisizione guidata delle pratiche dal precedente gestionale dello studio.',
      path: '/importa-pratiche',
    },
    permissions: { canImport: true, message: '' },
    steps: [
      { id: 'seleziona', label: 'Seleziona archivio', description: 'Scegli il pacchetto da analizzare.' },
      { id: 'verifica', label: 'Verifica contenuti', description: 'Controlla pratiche, documenti e anagrafiche.' },
      { id: 'importa', label: 'Importa', description: 'Conferma l’acquisizione nel tenant corrente.' },
    ],
    acceptedFiles: '.zip,.json,.mdb',
    localPathEnabled: true,
    actions: {
      refresh: '/api/v1/ui/import/quickorganizer',
      preview: '/api/v1/ui/import/quickorganizer/anteprima',
      uploadStart: '/api/v1/ui/import/quickorganizer/upload-session',
      uploadChunk: '/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/chunk',
      uploadComplete: '/api/v1/ui/import/quickorganizer/upload-session/{uploadId}/completa',
      prepareStart: '/api/v1/ui/import/quickorganizer/preparazione',
      run: '/api/v1/ui/import/quickorganizer/esegui',
      helper: '/static/tools/PreparaPacchettoPratiche.exe',
      fascicoli: '/fascicoli',
      clienti: '/clienti',
    },
    upload: {
      directLimitBytes: 157286400,
      chunkSizeBytes: 67108864,
      maxUploadBytes: 32212254720,
    },
    notes: ['La preview non scrive dati.', 'Ogni importazione resta tracciata nel tenant selezionato.'],
    contracts: { mock_fallback: false, writes: 'operational_routes', route_owner: 'react_shell' },
  }
}

function pianoGiornoPayload(): ApiPayload {
  const activity = {
    id: 'DP-MOCK-001',
    titolo: 'Verificare la scadenza del fascicolo',
    priorita: 'P1',
    ordine: 1,
    stato: 'needs_review',
    settore: 'scadenziario',
    tipo_azione: 'deadline_fulfill',
    motivo: 'Termine in avvicinamento',
    scadenza: '2026-08-22',
    scadenza_label: 'Oggi, 22/08/2026',
    fascicolo_id: 'FASC-MOCK-001',
    fascicolo: 'Rossi c. Bianchi',
    cliente: 'Mario Rossi',
    assegnato_a: storybookUser.id,
    assegnato_label: storybookUser.displayName,
    bloccante: false,
    perentorio: true,
    affidabilita: 0.96,
    da_rivedere: true,
    fascia_proposta: '10:00–10:30',
    minuti_stimati: 30,
    in_backlog: false,
    evidenze: 1,
    apri: '/fascicoli/FASC-MOCK-001',
    azioni: ['accept', 'delegate'],
  }
  return {
    ok: true,
    stato: 'pronto',
    data: '2026-08-22',
    data_label: '22/08/2026',
    utente: storybookUser.id,
    versione_piano: 'storybook-fixture',
    generato_il: '2026-08-22T08:00:00+02:00',
    generato_il_label: '22/08/2026 08:00',
    copertura: [],
    copertura_completa: true,
    riepilogo: { totale: 1, per_priorita: { P1: 1 }, backlog: 0, da_rivedere: 1, da_assegnare_studio: 0 },
    sezioni: { da_fare_ora: [activity], pec: [], fascicoli: [], economico: [], da_assegnare: [] },
    agenda_oggi: [{
      id: 'AGENDA-MOCK-001',
      titolo: 'Udienza di comparizione',
      tipo: 'udienza',
      data_ora: '22/08/2026 11:00',
      durata_minuti: 60,
      avvocato: storybookUser.displayName,
      luogo: 'Tribunale di Milano',
      procedimento: 'Rossi c. Bianchi',
      id_cliente: 'CLIENTE-MOCK-001',
      stato: 'confermato',
    }],
    avvisi: [],
    sintesi: 'Una priorità da confermare per oggi.',
    sintesi_da_lex: false,
  }
}

function impostazioniPayload(): ApiPayload {
  const sectionNames = [
    'studio', 'fatturazione', 'pec', 'firma', 'smtp', 'whatsapp', 'scheduler', 'ai', 'sdi', 'pagamenti', 'notifiche', 'backup', 'calendari',
  ]
  return {
    ok: true,
    source: 'storybook-fixture',
    generated_at: '22/08/2026 10:00',
    contracts: {
      mock_fallback: false,
      writes: 'json_api',
      route_owner: 'react_shell',
      operational: true,
      secrets_exposed: false,
      sensitive_settings: 'redacted_secret_values',
      can_update: true,
    },
    permissions: {
      can_read: true,
      can_update: true,
      can_test_connections: true,
      can_configure_ai: true,
      can_send_notifications: true,
      can_manage_backup: true,
      can_manage_calendar: true,
    },
    sections: sectionNames.map((id) => ({ label: id, status: 'configured', tone: 'success', note: 'Configurazione disponibile.' })),
    local_signer: {
      version: '2.0.0',
      base_url: 'http://127.0.0.1:27272',
      restart_protocol: 'iusentra-local-signer://restart',
      download_page: '/impostazioni?tab=firma',
      downloads: { windows: '/polisWeb/local-signer/setup/windows', macos: '/polisWeb/local-signer/setup/macos', linux: '/polisWeb/local-signer/setup/linux' },
      windows_filename: 'IUSENTRA-Local-Signer.exe',
      windows_tipo: 'Installer Windows',
      macos_filename: 'IUSENTRA-Local-Signer.dmg',
      linux_filename: 'iusentra-local-signer.AppImage',
    },
    studio: { nome: storybookTenant.name, avvocato: storybookUser.displayName, email: storybookUser.email, city: 'Milano' },
    fatturazione: { regime_fiscale: 'RF01', percentuale_spese_generali: 15, metodo_pagamento: 'Bonifico', giorni_scadenza: 30 },
    fatturazione_stats: { totali: 3, aggiornabili: 2, escluse: 1 },
    pec: { indirizzo: 'studio@pec.example.it', smtp_host: 'smtp.pec.example.it', imap_host: 'imap.pec.example.it', password: { present: true, label: 'Password configurata', placeholder: 'Lascia vuoto per non modificare' } },
    firma: { backend_preferito: 'pkcs11', cf_avvocato: 'RSSMRA80A01H501Z' },
    smtp: { host: 'smtp.example.it', from_address: storybookUser.email },
    whatsapp: {},
    scheduler: { enabled: true },
    ai: { provider: 'locale', enabled: true },
    sdi: {},
    pagamenti: {},
    notifiche: {},
    backup: {},
    calendari: {},
    warnings: [],
  }
}

function portaleClientiStudioPayload(): ApiPayload {
  const client = { id: 'CLIENTE-MOCK-001', label: 'Mario Rossi', email: 'mario.rossi@example.it', phone: '+39 333 000 0000', fiscalCode: 'RSSMRA80A01H501Z' }
  const matter = { id: 'FASC-MOCK-001', label: 'Rossi c. Bianchi', clientId: client.id, clientName: client.label, number: 'RG 1234/2026', status: 'attivo' }
  return {
    ok: true,
    surface: 'studio',
    title: 'Portale Clienti',
    canWrite: true,
    featureFlags,
    summary: { clients: 1, matters: 1, activeInvites: 1, pendingDocuments: 1, pendingSignatures: 0 },
    clientOptions: [client],
    matterOptions: [matter],
    clients: [client],
    matters: [{ ...matter, client_id: client.id, title: matter.label, opened_at_label: '01/08/2026' }],
    invites: [{ id: 'INVITO-MOCK-001', matter_id: matter.id, client_id: client.id, status: 'attivo', expires_at_label: '05/09/2026' }],
    documentRequests: [{ id: 'RICHIESTA-MOCK-001', matter_id: matter.id, title: 'Documento di identità', status: 'in attesa' }],
    documents: [],
    signatures: [],
    messages: [{ id: 'MESSAGGIO-MOCK-001', matter_id: matter.id, body: 'Messaggio dimostrativo per il cliente.', created_at_label: '22/08/2026 09:30' }],
    appointments: [],
    notifications: [],
    questionnaires: [],
    surveys: [],
    evidencePacks: [],
    settings: { inviteExpiresDays: 14 },
  }
}

function documentiAiPayload(): ApiPayload {
  const document = {
    id: 'DOC-AI-MOCK-001',
    original_filename: 'memoria_difensiva.pdf',
    safe_filename: 'memoria_difensiva.pdf',
    file_type: 'pdf',
    mime_type: 'application/pdf',
    size_bytes: 124000,
    sha256: 'fixture-storybook-documento-ai',
    status: 'ready',
    current_version_id: 'VERSIONE-MOCK-001',
    page_count: 3,
    created_by: storybookUser.displayName,
    created_at: '22/08/2026 09:00',
    updated_at: '22/08/2026 09:15',
  }
  return {
    mock_fallback: false,
    fascicolo_id: 'FASC-MOCK-001',
    documents: [document],
    capabilities: { upload: true, read: true, search: true, lex_tools: true, generate_docx: true, propose_edits: true, compare: true },
  }
}

function presidiPayload(): ApiPayload {
  const presidio = {
    id: 'PRESIDIO-MOCK-001',
    practice: { id: 'FASC-MOCK-001', label: 'Rossi c. Bianchi', client: 'Mario Rossi', href: '/fascicoli/FASC-MOCK-001' },
    document: { id: 'DOC-MOCK-001', name: 'Provvedimento.pdf', role_label: 'Provvedimento' },
    source_effective_at: '22/08/2026 09:00',
    explicit_due_at: '29/08/2026 23:59',
    notification_case: 'pec',
    notification_case_label: 'Notifica PEC',
    channel: 'pec',
    channel_label: 'PEC',
    recipients: [{ id: 'DEST-MOCK-001', name: 'Controparte', role: 'Destinatario', status_label: 'Da verificare', pec_address: 'destinatario@pec.example.it' }],
    status: 'NEEDS_REVIEW',
    status_label: 'Da riesaminare',
    priority: 'P1',
    confidence: 0.95,
    detection_reason: 'Ricevuta PEC collegata al fascicolo.',
    rule_label: 'Presidio notifica',
    legal_sources: ['L. 53/1994'],
    next_action: 'Verificare dati del destinatario',
    human_review_required: true,
    legacy_assumed_handled: false,
    assigned_user: { value: storybookUser.id, label: storybookUser.displayName },
    updated_at: '22/08/2026 10:00',
  }
  return {
    ok: true,
    items: [presidio],
    pagination: { cursor: '', next_cursor: null, has_more: false, total: 1, limit: 30 },
    filter_options: { assignees: [{ value: storybookUser.id, label: storybookUser.displayName }], channels: [{ value: 'pec', label: 'PEC' }] },
    permissions: { can_read: true, can_write: true, can_link_document: true, can_view_evidence: true },
    partial: false,
    warnings: [],
  }
}
function payloadFor(url: URL): ApiPayload {
  if (url.pathname.startsWith('/api/v1/ui/notifiche-legali/presidi')) return presidiPayload()
  if (url.pathname === '/api/v1/ui/strumenti-legali') return strumentiLegaliPayload()
  if (url.pathname.startsWith('/api/v1/ui/import/quickorganizer')) return importQuickOrganizerPayload()
  if (url.pathname.startsWith('/api/v1/ui/daily-plan/backlog')) return { ok: true, items: [], next_cursor: '', total_matching: 0, truncated: false }
  if (url.pathname.startsWith('/api/v1/ui/daily-plan')) return pianoGiornoPayload()
  if (url.pathname === '/api/v1/ui/profilo') {
    return {
      ok: true,
      user: { id: storybookUser.id, username: 'avvocato-operativo-mock', email: storybookUser.email, nome_completo: storybookUser.displayName, ruolo: storybookUser.role, ultimo_accesso: '22/08/2026 09:30' },
      security: { twoFactorEnabled: true, setupSecret: '', setupUri: '' },
      passwordRequired: false,
    }
  }
  if (url.pathname.startsWith('/api/v1/ui/impostazioni')) return impostazioniPayload()
  if (url.pathname === '/api/v1/ui/client-portal/dashboard') return portaleClientiStudioPayload()
  if (url.pathname.includes('/documenti-ai')) return documentiAiPayload()
  if (url.pathname.includes('feature-flags')) {
    return { ok: true, flags: featureFlags }
  }
  if (url.pathname.includes('legal-skills')) {
    return {
      ...sharedPayload(),
      packs: [{
        pack_id: 'PACK-MOCK-001',
        name: 'Pack processuale fittizio',
        description: 'Fixture sicura per controllare struttura, stati e azioni.',
        jurisdiction: 'Italia',
        source_mode: 'strict',
        skills_count: 2,
        skills: [],
      }],
      profile: { status: 'ready', firm_name: storybookTenant.name, practice_areas: ['Civile'] },
      agents: [],
    }
  }
  if (url.pathname.includes('procedure-completion')) {
    return {
      ...sharedPayload(),
      cards: [],
      dashboard: { ok: true, cards: [], stats: {}, errore: '' },
    }
  }
  return sharedPayload()
}

function isLocalApplicationRequest(url: URL): boolean {
  return url.origin === window.location.origin && (
    url.pathname.startsWith('/api/')
    || url.pathname.startsWith('/agenda/')
    || url.pathname.startsWith('/fascicoli/')
    || url.pathname.startsWith('/scadenziario/')
    || url.pathname.startsWith('/wizard-pro/')
    || url.pathname.startsWith('/prima-nota/')
    || url.pathname.startsWith('/crm/')
  )
}

function installBrowserShims() {
  if (!window.matchMedia) {
    window.matchMedia = (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })
  }
  if (!window.ResizeObserver) {
    window.ResizeObserver = class ResizeObserver {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
}

export function installStorybookRuntime() {
  ensureBootstrap()
  installBrowserShims()
  if (window.__IUSENTRA_STORYBOOK_FETCH__) return

  window.__IUSENTRA_STORYBOOK_FETCH__ = window.fetch.bind(window)
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const requestUrl = new URL(typeof input === 'string' ? input : input instanceof URL ? input.href : input.url, window.location.origin)
    if (!isLocalApplicationRequest(requestUrl)) {
      return window.__IUSENTRA_STORYBOOK_FETCH__!(input, init)
    }
    return new Response(JSON.stringify(payloadFor(requestUrl)), {
      status: 200,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }
}
