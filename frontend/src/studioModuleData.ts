export type StudioModuleTone =
  | 'primary'
  | 'success'
  | 'warning'
  | 'danger'
  | 'purple'
  | 'orange'
  | 'neutral'

export type StudioModuleKpi = {
  label: string
  value: string
  note: string
  tone: StudioModuleTone
}

export type StudioModuleCard = {
  title: string
  body: string
  href: string
  action: string
  icon: string
  tone: StudioModuleTone
  meta?: string
}

export type StudioModuleLink = {
  label: string
  href: string
}

export type StudioModuleConfig = {
  id: string
  routes: string[]
  title: string
  section: string
  subtitle: string
  lexContext: string
  lexLabel: string
  kpis: StudioModuleKpi[]
  cards: StudioModuleCard[]
  workflow: string[]
  links: StudioModuleLink[]
}

const commonStudioLinks: StudioModuleLink[] = [
  { label: 'Panoramica', href: '/' },
  { label: 'Regia operativa', href: '/workspace-intelligente' },
  { label: 'Ricerca Studio', href: '/global-search' },
]

export const studioModules: StudioModuleConfig[] = [
  {
    id: 'studio',
    routes: ['/studio'],
    title: 'Studio',
    section: 'Direzione studio',
    subtitle: 'Centro operativo per dati, assetti organizzativi, canali, controlli e moduli amministrativi dello studio.',
    lexContext: 'studio',
    lexLabel: 'Lex legge dati studio, ruoli, canali, impostazioni e moduli collegati.',
    kpis: [
      { label: 'Aree presidiate', value: '6', note: 'organizzazione, comunicazioni, pagamenti, sito, backup, compliance', tone: 'primary' },
      { label: 'Canali operativi', value: '4', note: 'PEC, SMTP, WhatsApp, calendario', tone: 'success' },
      { label: 'Controlli', value: 'Attivi', note: 'audit e permessi collegati alle funzioni sensibili', tone: 'warning' },
    ],
    cards: [
      { title: 'Dati studio', body: 'Anagrafica, titolare, recapiti, albo, coordinate e dati usati in atti, parcelle e depositi.', href: '/impostazioni-studio#dati-studio', action: 'Apri dati studio', icon: 'building', tone: 'primary', meta: 'Impostazioni' },
      { title: 'Comunicazioni', body: 'Configura PEC, posta ordinaria, SMTP e canali WhatsApp senza perdere il presidio locale.', href: '/impostazioni-studio#pec-e-smtp', action: 'Apri canali', icon: 'mail', tone: 'success', meta: 'PEC / SMTP' },
      { title: 'Sito Studio', body: 'Gestisci contenuti, richieste contatto, prenotazioni e anteprima pubblica dello studio.', href: '/sito-studio', action: 'Apri sito', icon: 'earth', tone: 'purple', meta: 'Presenza digitale' },
      { title: 'Backup e continuità', body: 'Verifica copie, integrità, ripristino tecnico e politica di conservazione dei dati.', href: '/backup', action: 'Apri backup', icon: 'backup', tone: 'warning', meta: 'Operativo' },
    ],
    workflow: ['Completa dati studio', 'Verifica canali PEC e SMTP', 'Aggiorna sito pubblico', 'Controlla backup e audit'],
    links: [...commonStudioLinks, { label: 'Impostazioni Studio', href: '/impostazioni-studio' }, { label: 'Registro GDPR', href: '/registro-gdpr' }],
  },
  {
    id: 'fatturazione',
    routes: ['/fatturazione', '/fatturazione/nuova'],
    title: 'Parcelle e Fatture',
    section: 'Economico',
    subtitle: 'Superficie operativa per parcelle, fatture, PDF, XML, scadenze di pagamento e incassi collegati.',
    lexContext: 'fatturazione',
    lexLabel: 'Lex collega parcelle, clienti, fascicoli, pagamenti e stati di incasso.',
    kpis: [
      { label: 'Archivio', value: 'Parcelle', note: 'lista, filtri, PDF e XML già collegati', tone: 'primary' },
      { label: 'Pagamenti', value: 'Link', note: 'Stripe, PayPal, Satispay, SumUp dove configurati', tone: 'success' },
      { label: 'Scadenze', value: 'Monitor', note: 'controllo incassi e parcelle scadute', tone: 'warning' },
    ],
    cards: [
      { title: 'Elenco parcelle', body: 'Apri archivio completo, filtra per anno, stato, cliente o testo e genera PDF/XML.', href: '/fatturazione/', action: 'Apri archivio', icon: 'file', tone: 'primary', meta: 'Archivio operativo' },
      { title: 'Nuova parcella', body: 'Crea una parcella da cliente, fascicolo o preventivo con voci e calcoli fiscali.', href: '/fatturazione/nuova', action: 'Crea parcella', icon: 'plus', tone: 'success', meta: 'Nuovo documento' },
      { title: 'Incassi e pagamenti', body: 'Gestisci provider, link di pagamento e stato operativo dei canali di incasso.', href: '/incassi-pagamenti', action: 'Apri pagamenti', icon: 'card', tone: 'orange', meta: 'Provider' },
      { title: 'Esporta contabilita', body: 'Scarica dati contabili e prepara controlli di studio su fatturato e incassato.', href: '/export/fatturazione.csv', action: 'Esporta CSV', icon: 'download', tone: 'neutral', meta: 'CSV' },
    ],
    workflow: ['Crea o importa parcella', 'Verifica voci e imposte', 'Invia PDF o XML', 'Collega incasso e solleciti'],
    links: [{ label: 'Statistiche', href: '/statistiche' }, { label: 'Preventivi', href: '/preventivi' }, { label: 'Clienti', href: '/clienti' }],
  },
  {
    id: 'preventivi',
    routes: ['/preventivi', '/preventivi/nuovo', '/preventivi/wizard', '/preventivi/conferimento/nuovo'],
    title: 'Preventivi e Incarichi',
    section: 'Acquisizione mandato',
    subtitle: 'Controllo operativo per preventivi, conferimenti, workflow di accettazione e conversione in parcella.',
    lexContext: 'preventivi',
    lexLabel: 'Lex legge preventivo, conferimento, cliente e fascicolo collegato.',
    kpis: [
      { label: 'Flussi', value: '2', note: 'preventivo e conferimento incarico', tone: 'primary' },
      { label: 'Wizard', value: 'DM 55', note: 'calcolo guidato e generazione preventivo', tone: 'purple' },
      { label: 'Conversione', value: 'Parcella', note: 'passaggio a fatturazione già previsto', tone: 'success' },
    ],
    cards: [
      { title: 'Archivio preventivi', body: 'Filtra bozze, inviati, accettati e pratiche senza conferimento.', href: '/preventivi/', action: 'Apri archivio', icon: 'file', tone: 'primary', meta: 'Archivio operativo' },
      { title: 'Nuovo preventivo', body: 'Crea proposta economica con cliente, fascicolo, voci e condizioni.', href: '/preventivi/nuovo', action: 'Crea preventivo', icon: 'plus', tone: 'success', meta: 'Nuovo' },
      { title: 'Conferimento incarico', body: 'Predisponi l’incarico e collega accettazione, firma e fascicolo.', href: '/preventivi/conferimento/nuovo', action: 'Crea incarico', icon: 'shield', tone: 'warning', meta: 'Mandato' },
      { title: 'Wizard compensi', body: 'Calcola e genera preventivo con parametri forensi e dati pratica.', href: '/preventivi/wizard', action: 'Apri wizard', icon: 'spark', tone: 'purple', meta: 'Guidato' },
    ],
    workflow: ['Qualifica cliente', 'Calcola compenso', 'Invia preventivo', 'Raccogli incarico e crea fascicolo'],
    links: [{ label: 'Compensi Forensi', href: '/compensi-forensi' }, { label: 'Clienti', href: '/clienti' }, { label: 'Fatturazione', href: '/fatturazione' }],
  },
  {
    id: 'compensi-forensi',
    routes: ['/compensi-forensi', '/tariffario'],
    title: 'Compensi Forensi',
    section: 'Calcolo compensi',
    subtitle: 'Accesso professionale ai parametri forensi, fasi, complessità e generazione del preventivo collegato.',
    lexContext: 'compensi-forensi',
    lexLabel: 'Lex aiuta a verificare fase, valore, complessità e coerenza del compenso.',
    kpis: [
      { label: 'Fonte calcolo', value: 'Parametri', note: 'tariffario e wizard già presenti', tone: 'primary' },
      { label: 'Output', value: 'Preventivo', note: 'riuso diretto nel workflow incarichi', tone: 'success' },
      { label: 'Controllo', value: 'Audit', note: 'traccia calcolo e log compensi', tone: 'warning' },
    ],
    cards: [
      { title: 'Tariffario', body: 'Apri il calcolo compensi con parametri, fasi e log.', href: '/tariffario', action: 'Apri tariffario', icon: 'banknote', tone: 'primary', meta: 'Calcolo' },
      { title: 'Wizard preventivo', body: 'Trasforma il calcolo in proposta al cliente e incarico.', href: '/preventivi/wizard', action: 'Genera preventivo', icon: 'spark', tone: 'success', meta: 'Workflow' },
      { title: 'Strumenti Forensi', body: 'Usa onorari, contributo unificato, interessi, rivalutazione e altri calcoli.', href: '/strumenti-legali', action: 'Apri strumenti', icon: 'wrench', tone: 'purple', meta: 'Suite' },
    ],
    workflow: ['Seleziona materia e valore', 'Verifica fasi applicabili', 'Consolida log calcolo', 'Genera preventivo o parcella'],
    links: [{ label: 'Preventivi', href: '/preventivi' }, { label: 'Parcelle', href: '/fatturazione' }],
  },
  {
    id: 'redazione-atti',
    routes: ['/redazione-atti', '/template-atti', '/template-atti/catalogo', '/template-atti/nuovo', '/checklist'],
    title: 'Redazione Atti',
    section: 'Document automation',
    subtitle: 'Punto di ingresso operativo per modelli, catalogo atti, redazione guidata e assistente redazionale.',
    lexContext: 'redazione-atti',
    lexLabel: 'Lex legge modello, fascicolo, parti, documenti e checklist di deposito.',
    kpis: [
      { label: 'Catalogo', value: 'Template', note: 'modelli e compliance deposito', tone: 'primary' },
      { label: 'Editor', value: 'Atti', note: 'compilazione guidata e PDF', tone: 'success' },
      { label: 'AI', value: 'Redazionale', note: 'supporto locale verificabile', tone: 'purple' },
    ],
    cards: [
      { title: 'Catalogo atti', body: 'Consulta modelli per materia, canale e compliance di deposito.', href: '/template-atti/catalogo', action: 'Apri catalogo', icon: 'book', tone: 'primary', meta: 'Template' },
      { title: 'Nuovo modello', body: 'Crea o modifica template con variabili di studio, cliente e fascicolo.', href: '/template-atti/nuovo', action: 'Nuovo template', icon: 'plus', tone: 'success', meta: 'Editor' },
      { title: 'Checklist deposito', body: 'Controlla atti e allegati prima del deposito telematico.', href: '/deposito/checklist', action: 'Apri checklist', icon: 'check', tone: 'warning', meta: 'Deposito' },
      { title: 'Fascicoli', body: 'Seleziona pratica, parti e documenti da usare nella redazione.', href: '/fascicoli', action: 'Apri fascicoli', icon: 'folder', tone: 'neutral', meta: 'Contesto' },
    ],
    workflow: ['Scegli modello', 'Aggancia fascicolo e parti', 'Compila e verifica', 'Produci PDF o deposito'],
    links: [{ label: 'Checklist atti', href: '/deposito/checklist' }, { label: 'Fascicoli', href: '/fascicoli' }, { label: 'Ricerca Studio', href: '/global-search' }],
  },
  {
    id: 'pst-acquisizione',
    routes: ['/portali/pst/acquisizione', '/polisweb/acquisizione'],
    title: 'Importa pratica da PST',
    section: 'PolisWeb / PST',
    subtitle: 'Superficie operativa per acquisire pratiche da PST con Local Connector, file autorizzati e wizard tecnico governato.',
    lexContext: 'pst-acquisizione',
    lexLabel: 'Lex legge canale PST, fascicolo locale, mapping documenti e stato del connettore locale.',
    kpis: [
      { label: 'Canale', value: 'PST', note: 'consultazione e import autorizzato', tone: 'primary' },
      { label: 'Locale', value: 'Connector', note: 'CNS, browser guidato e file importati dall utente', tone: 'success' },
      { label: 'Audit', value: 'Import', note: 'mapping fascicolo e documenti tracciati', tone: 'warning' },
    ],
    cards: [
      { title: 'Acquisizione PST', body: 'Apri il wizard guidato del flusso PolisWeb / PST e verifica tutti i passaggi di import.', href: '/portali/pst/acquisizione', action: 'Apri acquisizione', icon: 'upload', tone: 'primary', meta: 'Wizard operativo' },
      { title: 'Checklist import PST', body: 'Controlla prerequisiti, mapping fascicolo e documenti prima dell importazione.', href: '/portali/pst/acquisizione#checklist-operativa', action: 'Verifica flusso', icon: 'briefcase', tone: 'success', meta: 'Presidio' },
      { title: 'Fascicoli', body: 'Controlla o crea la pratica locale prima di collegare documenti e buste.', href: '/fascicoli', action: 'Apri fascicoli', icon: 'folder', tone: 'warning', meta: 'Mapping' },
      { title: 'Centro telematico', body: 'Rientra nel quadro generale di PST, PDP, PAT e PTT.', href: '/app-v2/telematico', action: 'Apri centro', icon: 'send', tone: 'purple', meta: 'Portali' },
    ],
    workflow: ['Verifica accesso locale', 'Seleziona fascicolo PST', 'Riconcilia documenti', 'Importa e controlla audit'],
    links: [{ label: 'Panoramica PST', href: '/app-v2/polisweb' }, { label: 'Centro telematico', href: '/app-v2/telematico' }, { label: 'Acquisizione guidata', href: '/portali/pst/acquisizione' }],
  },
  {
    id: 'statistiche',
    routes: ['/statistiche'],
    title: 'Statistiche',
    section: 'Analisi studio',
    subtitle: 'Cruscotto operativo per andamento economico, fascicoli, clienti, scadenze, depositi e produttività.',
    lexContext: 'statistiche',
    lexLabel: 'Lex interpreta indicatori e segnala anomalie operative.',
    kpis: [
      { label: 'Dataset', value: '7', note: 'economico, fascicoli, clienti, scadenze, agenda, depositi, produttività', tone: 'primary' },
      { label: 'API', value: 'Pronte', note: 'endpoint statistiche già disponibili', tone: 'success' },
      { label: 'Uso', value: 'Direzione', note: 'lettura gestionale e controllo studio', tone: 'purple' },
    ],
    cards: [
      { title: 'Dashboard grafici', body: 'Apri grafici, KPI e riepilogo operativo completo.', href: '/statistiche/', action: 'Apri dashboard', icon: 'chart', tone: 'primary', meta: 'Grafici' },
      { title: 'Produttività', body: 'Analizza attività, timesheet e volume operativo dello studio.', href: '/statistiche/?view=produttivita', action: 'Vedi analisi', icon: 'table', tone: 'success', meta: 'Analisi' },
      { title: 'Depositi trend', body: 'Controlla andamento depositi e canali telematici.', href: '/statistiche/?view=depositi', action: 'Trend depositi', icon: 'send', tone: 'warning', meta: 'Telematico' },
    ],
    workflow: ['Aggiorna dati', 'Leggi KPI', 'Isola anomalie', 'Apri modulo operativo collegato'],
    links: [{ label: 'Fatturazione', href: '/fatturazione' }, { label: 'Fascicoli', href: '/fascicoli' }, { label: 'Scadenziario', href: '/scadenziario' }],
  },
  {
    id: 'ricerca-legale',
    routes: ['/ricerca-legale', '/legal-intelligence', '/legal-intelligence/news', '/legal-intelligence/mediazione'],
    title: 'Ricerca Legale',
    section: 'Legal intelligence',
    subtitle: 'Monitoraggio normativo, aggiornamenti, news, mediazione e fonti da collegare al lavoro di studio.',
    lexContext: 'ricerca-legale',
    lexLabel: 'Lex distingue fonti, aggiornamenti, impatto pratico e fascicoli collegabili.',
    kpis: [
      { label: 'Fonti', value: 'Monitor', note: 'pipeline aggiornamenti e snapshot', tone: 'primary' },
      { label: 'News', value: 'Studio', note: 'archivio aggiornamenti legali', tone: 'success' },
      { label: 'Revisione', value: 'Umana', note: 'approvazione contenuti prima dell’uso', tone: 'warning' },
    ],
    cards: [
      { title: 'Dashboard ricerca', body: 'Apri monitor normativo e snapshot Legal Intelligence.', href: '/legal-intelligence/', action: 'Apri ricerca', icon: 'book', tone: 'primary', meta: 'Fonti' },
      { title: 'News legali', body: 'Consulta aggiornamenti, filtri per materia e dettaglio news.', href: '/legal-intelligence/news', action: 'Apri news', icon: 'earth', tone: 'success', meta: 'Aggiornamenti' },
      { title: 'Registro mediazione', body: 'Verifica organismi, dati e aggiornamenti collegati alla mediazione.', href: '/legal-intelligence/mediazione', action: 'Apri registro', icon: 'landmark', tone: 'purple', meta: 'Mediazione' },
    ],
    workflow: ['Sincronizza fonti', 'Valuta impatto', 'Approva contenuti', 'Collega a fascicoli e note'],
    links: [{ label: 'Archivio Giurisprudenza', href: '/giurisprudenza' }, { label: 'Ricerca Studio', href: '/global-search' }],
  },
  {
    id: 'giurisprudenza',
    routes: ['/giurisprudenza', '/giurisprudenza/nuova'],
    title: 'Archivio Giurisprudenza',
    section: 'Banca dati interna',
    subtitle: 'Archivio sentenze con fonti, tassonomia, import, classificazione e collegamento alle pratiche.',
    lexContext: 'giurisprudenza',
    lexLabel: 'Lex legge sentenze, fonti, orientamenti e collegamenti al fascicolo.',
    kpis: [
      { label: 'Archivio', value: 'Sentenze', note: 'ricerca e filtri tassonomici', tone: 'primary' },
      { label: 'Import', value: 'URL/file', note: 'materiale e fonti ufficiali', tone: 'success' },
      { label: 'Classifica', value: 'AI', note: 'suggerimento controllato', tone: 'purple' },
    ],
    cards: [
      { title: 'Ricerca sentenze', body: 'Apri archivio con filtri per fonte, area, branca, grado e orientamento.', href: '/giurisprudenza/', action: 'Apri archivio', icon: 'landmark', tone: 'primary', meta: 'Archivio' },
      { title: 'Nuova scheda', body: 'Registra manualmente una sentenza o un provvedimento rilevante.', href: '/giurisprudenza/nuova', action: 'Nuova scheda', icon: 'plus', tone: 'success', meta: 'Inserimento' },
      { title: 'Importa materiale', body: 'Collega materiale giurisprudenziale e fonti al repository interno.', href: '/giurisprudenza/', action: 'Importa', icon: 'upload', tone: 'warning', meta: 'Import' },
    ],
    workflow: ['Importa fonte', 'Classifica area e orientamento', 'Collega pratica', 'Usa in ricerca e redazione'],
    links: [{ label: 'Ricerca Legale', href: '/ricerca-legale' }, { label: 'Redazione Atti', href: '/redazione-atti' }],
  },
  {
    id: 'strumenti-forensi',
    routes: ['/strumenti-legali'],
    title: 'Strumenti Forensi',
    section: 'Calcolatori professionali',
    subtitle: 'Suite operativa di accesso a calcoli forensi, interessi, rivalutazione, CU, onorari e utility operative.',
    lexContext: 'strumenti-forensi',
    lexLabel: 'Lex aiuta a scegliere strumento, dati necessari e risultato da allegare al fascicolo.',
    kpis: [
      { label: 'Moduli', value: '18+', note: 'calcolatori già esposti via API', tone: 'primary' },
      { label: 'Prefill', value: 'Fascicolo', note: 'dati cliente e pratica riutilizzabili', tone: 'success' },
      { label: 'Output', value: 'Audit', note: 'risultati verificabili e ripetibili', tone: 'warning' },
    ],
    cards: [
      { title: 'Suite strumenti', body: 'Apri contributo unificato, interessi, onorari, TFR, usura e altri calcoli.', href: '/strumenti-legali/', action: 'Apri suite', icon: 'wrench', tone: 'primary', meta: 'Calcolo' },
      { title: 'Onorari forensi', body: 'Calcola fasi, valore controversia e parametri collegabili a preventivi.', href: '/strumenti-legali/?tool=onorari_forensi', action: 'Calcola onorari', icon: 'banknote', tone: 'success', meta: 'DM 55' },
      { title: 'Contributo unificato', body: 'Determina importi e controlli collegati al deposito.', href: '/strumenti-legali/?tool=contributo_unificato', action: 'Calcola CU', icon: 'check', tone: 'warning', meta: 'Deposito' },
    ],
    workflow: ['Scegli strumento', 'Prefill da fascicolo', 'Calcola e verifica', 'Riporta risultato in pratica'],
    links: [{ label: 'Compensi Forensi', href: '/compensi-forensi' }, { label: 'Fascicoli', href: '/fascicoli' }],
  },
  {
    id: 'timesheet',
    routes: ['/timesheet'],
    title: 'Timesheet',
    section: 'Tempo e produttività',
    subtitle: 'Superficie operativa per registrare attività, validare ore, collegare clienti e generare parcelle.',
    lexContext: 'timesheet',
    lexLabel: 'Lex legge attività, cliente, fascicolo, stato fatturabile e prossima azione economica.',
    kpis: [
      { label: 'Registrazione', value: 'Ore', note: 'attività manuali e collegate ai fascicoli', tone: 'primary' },
      { label: 'Validazione', value: 'Stati', note: 'bozza, validato, fatturato e non fatturabile', tone: 'success' },
      { label: 'Output', value: 'Parcella', note: 'generazione da voci validate', tone: 'orange' },
    ],
    cards: [
      { title: 'Cruscotto tempi', body: 'Apri riepilogo, filtri per cliente, fascicolo, stato e utente.', href: '/timesheet', action: 'Apri timesheet', icon: 'clock', tone: 'primary', meta: 'Operativo' },
      { title: 'Nuova attività', body: 'Registra una voce tempo da cliente o fascicolo con importo fatturabile.', href: '/agenda', action: 'Aggancia agenda', icon: 'calendar', tone: 'success', meta: 'Workflow' },
      { title: 'Genera parcella', body: 'Consolida le voci validate e prepara il documento economico.', href: '/fatturazione/nuova', action: 'Crea parcella', icon: 'file', tone: 'orange', meta: 'Economico' },
      { title: 'Produttività', body: 'Leggi indicatori e andamento operativo dello studio.', href: '/statistiche/?view=produttivita', action: 'Vedi KPI', icon: 'chart', tone: 'purple', meta: 'Analisi' },
    ],
    workflow: ['Registra attività', 'Valida le voci', 'Filtra per cliente o fascicolo', 'Genera parcella e controlla audit'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Parcelle', href: '/fatturazione' }, { label: 'Statistiche', href: '/statistiche/?view=produttivita' }],
  },
  {
    id: 'cartelle-condivise',
    routes: ['/cartelle-condivise'],
    title: 'Cartelle Condivise',
    section: 'Collaborazione clienti',
    subtitle: 'Superficie operativa per accessi condivisi, collaboratori, scadenze permessi e cartelle clienti.',
    lexContext: 'cartelle-condivise',
    lexLabel: 'Lex legge cliente, collaboratori, ruolo assegnato, scadenza accesso e rischi privacy.',
    kpis: [
      { label: 'Accessi', value: 'Clienti', note: 'cartelle condivise e collaboratori', tone: 'primary' },
      { label: 'Ruoli', value: 'RBAC', note: 'lettura, scrittura e gestione', tone: 'success' },
      { label: 'Privacy', value: 'Audit', note: 'scadenze e tracciamento condivisioni', tone: 'warning' },
    ],
    cards: [
      { title: 'Cartelle condivise', body: 'Apri elenco accessi gestiti e cartelle ricevute.', href: '/cartelle-condivise', action: 'Apri cartelle', icon: 'folder', tone: 'primary', meta: 'Operativo' },
      { title: 'Clienti', body: 'Seleziona cliente e gestisci collaboratori dalla cartella.', href: '/clienti', action: 'Apri clienti', icon: 'users', tone: 'success', meta: 'Anagrafiche' },
      { title: 'Registro attività', body: 'Controlla aperture, modifiche e condivisioni sensibili.', href: '/audit', action: 'Apri audit', icon: 'clipboard', tone: 'warning', meta: 'Audit' },
    ],
    workflow: ['Scegli cliente', 'Assegna collaboratore e ruolo', 'Imposta scadenza', 'Verifica audit e privacy'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Registro GDPR', href: '/registro-gdpr' }, { label: 'Registro attività', href: '/registro-attivita' }],
  },
  {
    id: 'strumenti-operativi',
    routes: ['/strumenti-operativi', '/applicazioni'],
    title: 'Strumenti Operativi',
    section: 'Operatività studio',
    subtitle: 'Raccolta operativa di strumenti trasversali per agenda, messaggi, condivisioni, export e automazioni.',
    lexContext: 'strumenti-operativi',
    lexLabel: 'Lex legge il contesto operativo e propone il modulo più utile.',
    kpis: [
      { label: 'Operazioni', value: 'Rapide', note: 'azioni frequenti dello studio', tone: 'primary' },
      { label: 'Export', value: 'CSV/ICS', note: 'dati riutilizzabili fuori piattaforma', tone: 'success' },
      { label: 'Automazioni', value: 'Presidio', note: 'scheduler e promemoria', tone: 'purple' },
    ],
    cards: [
      { title: 'Timesheet', body: 'Registra attività e genera parcelle dalle ore lavorate.', href: '/timesheet', action: 'Apri timesheet', icon: 'clock', tone: 'primary', meta: 'Tempo' },
      { title: 'Export dati', body: 'Scarica dati studio per controlli, backup esterni e analisi.', href: '/export/fatturazione.csv', action: 'Esporta', icon: 'download', tone: 'success', meta: 'CSV' },
      { title: 'Condivisioni', body: 'Gestisci cartelle condivise e accesso documentale dei clienti.', href: '/cartelle-condivise', action: 'Apri condivisioni', icon: 'folder', tone: 'warning', meta: 'Clienti' },
      { title: 'Regia operativa', body: 'Torna alla cabina con priorità e prossime azioni.', href: '/workspace-intelligente', action: 'Apri regia', icon: 'spark', tone: 'purple', meta: 'AI' },
    ],
    workflow: ['Apri strumento', 'Aggancia cliente o fascicolo', 'Completa azione', 'Traccia in audit o workflow'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Messaggi', href: '/messaggi' }, { label: 'Backup', href: '/backup' }],
  },
  {
    id: 'sito-studio',
    routes: ['/sito-studio', '/sito-studio/builder', '/sito-studio/contatti'],
    title: 'Sito Studio',
    section: 'Presenza digitale',
    subtitle: 'Pannello operativo per sito pubblico, contenuti, servizi, professionisti, sedi, richieste e prenotazioni.',
    lexContext: 'sito-studio',
    lexLabel: 'Lex legge contenuti del sito, richieste e conversione in clienti.',
    kpis: [
      { label: 'Contenuti', value: 'CMS', note: 'servizi, professionisti, sedi e blocchi', tone: 'primary' },
      { label: 'Lead', value: 'Contatti', note: 'richieste convertibili in clienti', tone: 'success' },
      { label: 'Booking', value: 'Slot', note: 'regole e disponibilità appuntamenti', tone: 'warning' },
    ],
    cards: [
      { title: 'Dashboard sito', body: 'Apri controllo contenuti, richieste, prenotazioni e stato pubblicazione.', href: '/sito-studio/', action: 'Apri dashboard', icon: 'earth', tone: 'primary', meta: 'CMS' },
      { title: 'Builder Pro', body: 'Modifica blocchi, layout e contenuti avanzati del sito.', href: '/sito-studio/builder', action: 'Apri builder', icon: 'wrench', tone: 'purple', meta: 'Design' },
      { title: 'Richieste contatto', body: 'Valuta contatti arrivati dal sito e crea anagrafiche clienti.', href: '/sito-studio/contatti', action: 'Apri contatti', icon: 'mail', tone: 'success', meta: 'Lead' },
    ],
    workflow: ['Aggiorna contenuti', 'Pubblica anteprima', 'Gestisci richieste', 'Converti lead in cliente'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Agenda', href: '/agenda' }],
  },
  {
    id: 'notifiche-whatsapp',
    routes: ['/notifiche-whatsapp', '/notifiche'],
    title: 'Notifiche WhatsApp',
    section: 'Comunicazioni automatiche',
    subtitle: 'Presidio operativo per promemoria, messaggi WhatsApp, configurazione provider e link rapidi ai clienti.',
    lexContext: 'notifiche-whatsapp',
    lexLabel: 'Lex legge destinatario, pratica, scadenza e tono del messaggio.',
    kpis: [
      { label: 'Canale', value: 'WhatsApp', note: 'Twilio o CallMeBot dove configurati', tone: 'success' },
      { label: 'Promemoria', value: 'Agenda', note: 'domani, scadenze e appuntamenti', tone: 'warning' },
      { label: 'Audit', value: 'Messaggi', note: 'invii tracciati nel modulo comunicazioni', tone: 'primary' },
    ],
    cards: [
      { title: 'Centro notifiche', body: 'Apri invio messaggi e promemoria collegati a clienti e scadenze.', href: '/notifiche/', action: 'Apri notifiche', icon: 'message', tone: 'success', meta: 'Invio' },
      { title: 'Configura WhatsApp', body: 'Gestisci credenziali e numeri provider nelle impostazioni studio.', href: '/impostazioni-studio#whatsapp', action: 'Apri configurazione', icon: 'settings', tone: 'primary', meta: 'Provider' },
      { title: 'Messaggi clienti', body: 'Controlla conversazioni e crea messaggi collegati al cliente.', href: '/messaggi', action: 'Apri messaggi', icon: 'mail', tone: 'purple', meta: 'Inbox' },
    ],
    workflow: ['Verifica configurazione', 'Scegli destinatario', 'Prepara testo', 'Invia e archivia esito'],
    links: [{ label: 'Messaggi', href: '/messaggi' }, { label: 'Agenda', href: '/agenda' }, { label: 'Impostazioni', href: '/impostazioni-studio' }],
  },
  {
    id: 'incassi-pagamenti',
    routes: ['/incassi-pagamenti', '/impostazioni/pagamenti'],
    title: 'Incassi e Pagamenti',
    section: 'Payment operations',
    subtitle: 'Controllo operativo per provider pagamento, link incasso, stato parcelle e configurazione canali.',
    lexContext: 'incassi-pagamenti',
    lexLabel: 'Lex collega pagamento, parcella, cliente e sollecito.',
    kpis: [
      { label: 'Provider', value: '4', note: 'Stripe, PayPal, Satispay, SumUp', tone: 'primary' },
      { label: 'Link', value: 'Parcelle', note: 'pagamento collegato al documento', tone: 'success' },
      { label: 'Controllo', value: 'Webhook', note: 'ricezione esiti provider', tone: 'warning' },
    ],
    cards: [
      { title: 'Impostazioni pagamenti', body: 'Configura provider, chiavi e preferenze operative per incassi digitali.', href: '/impostazioni/pagamenti', action: 'Apri impostazioni', icon: 'settings', tone: 'primary', meta: 'Provider' },
      { title: 'Parcelle aperte', body: 'Apri parcelle da incassare e genera link pagamento.', href: '/fatturazione', action: 'Apri parcelle', icon: 'file', tone: 'success', meta: 'Incasso' },
      { title: 'Statistiche economiche', body: 'Controlla fatturato, incassato e trend di periodo.', href: '/statistiche', action: 'Apri statistiche', icon: 'chart', tone: 'purple', meta: 'KPI' },
    ],
    workflow: ['Configura provider', 'Genera link parcella', 'Ricevi esito', 'Aggiorna stato incasso'],
    links: [{ label: 'Parcelle', href: '/fatturazione' }, { label: 'Clienti', href: '/clienti' }],
  },
  {
    id: 'backup',
    routes: ['/backup'],
    title: 'Backup',
    section: 'Continuita operativa',
    subtitle: 'Superficie operativa per backup, verifica integrità, download, ripristino tecnico e policy scheduler.',
    lexContext: 'backup',
    lexLabel: 'Lex legge stato copie, rischi e prossime verifiche consigliate.',
    kpis: [
      { label: 'Copie', value: 'Storico', note: 'archivio backup reale', tone: 'primary' },
      { label: 'Integrita', value: 'Verifica', note: 'controllo file e dimensioni', tone: 'success' },
      { label: 'Ripristino', value: 'Guidato', note: 'azione tecnica separata', tone: 'warning' },
    ],
    cards: [
      { title: 'Archivio backup', body: 'Apri lista backup, stato, dimensione, verifica e download.', href: '/backup', action: 'Apri archivio', icon: 'backup', tone: 'primary', meta: 'Storage' },
      { title: 'Scheduler backup', body: 'Configura orario backup e promemoria automatici dello studio.', href: '/impostazioni-studio#scheduler', action: 'Apri scheduler', icon: 'clock', tone: 'success', meta: 'Automazione' },
      { title: 'Database', body: 'Verifica storage, SQLite/PostgreSQL e snapshot tecnici.', href: '/admin/database', action: 'Apri database', icon: 'database', tone: 'purple', meta: 'Tecnico' },
    ],
    workflow: ['Verifica ultimo backup', 'Controlla integrità', 'Scarica se necessario', 'Documenta ripristino tecnico'],
    links: [{ label: 'Database', href: '/admin/database' }, { label: 'Registro Attività', href: '/registro-attivita' }],
  },
  {
    id: 'impostazioni-studio',
    routes: ['/impostazioni-studio', '/impostazioni'],
    title: 'Impostazioni Studio',
    section: 'Configurazione',
    subtitle: 'Indice operativo delle impostazioni sensibili: dati studio, PEC, firma, SMTP, WhatsApp, scheduler e AI locale.',
    lexContext: 'impostazioni-studio',
    lexLabel: 'Lex legge configurazione e guida ai controlli senza esporre credenziali.',
    kpis: [
      { label: 'Tab', value: '7', note: 'studio, PEC, firma, SMTP, WhatsApp, scheduler, AI', tone: 'primary' },
      { label: 'Locale', value: 'Signer', note: 'controlli sul PC dell’avvocato', tone: 'success' },
      { label: 'Sicurezza', value: 'No cloud', note: 'password e token governati dalle policy esistenti', tone: 'warning' },
    ],
    cards: [
      { title: 'Dati studio', body: 'Apri dati anagrafici, fiscali e recapiti usati nei documenti.', href: '/impostazioni-studio#dati-studio', action: 'Apri studio', icon: 'building', tone: 'primary', meta: 'Anagrafica' },
      { title: 'PEC e SMTP', body: 'Verifica PEC, Local Signer e invio messaggi senza salvare password nel server.', href: '/impostazioni-studio#pec-e-smtp', action: 'Apri PEC', icon: 'mail', tone: 'success', meta: 'Posta' },
      { title: 'Firma digitale', body: 'Controlla backend firma e canale Local Signer per token USB.', href: '/impostazioni-studio#firma-digitale', action: 'Apri firma', icon: 'shield', tone: 'warning', meta: 'PKCS#11' },
      { title: 'AI locale', body: 'Configura runtime AI locale e reindicizzazione documenti.', href: '/impostazioni-studio#ai-locale', action: 'Apri AI', icon: 'spark', tone: 'purple', meta: 'Lex' },
      { title: 'WhatsApp', body: 'Presidia provider, numeri e promemoria cliente collegati alle comunicazioni.', href: '/impostazioni-studio#whatsapp', action: 'Apri WhatsApp', icon: 'message', tone: 'success', meta: 'Canale' },
      { title: 'Scheduler', body: 'Controlla automazioni, backup, sync e job pianificati dello studio.', href: '/impostazioni-studio#scheduler', action: 'Apri scheduler', icon: 'clock', tone: 'neutral', meta: 'Automazioni' },
    ],
    workflow: ['Apri tab corretta', 'Verifica canale locale', 'Salva configurazione', 'Esegui test operativo'],
    links: [{ label: 'Sincronizzazione Calendari', href: '/sincronizzazione-calendari' }, { label: 'Backup', href: '/backup' }],
  },
  {
    id: 'sincronizzazione-calendari',
    routes: ['/sincronizzazione-calendari', '/impostazioni/calendario'],
    title: 'Sincronizzazione Calendari',
    section: 'Agenda esterna',
    subtitle: 'Feed ICS, profili remoti, token calendario e sincronizzazione tra agenda, scadenze e calendari esterni.',
    lexContext: 'sincronizzazione-calendari',
    lexLabel: 'Lex legge profili calendario, scadenze e conflitti da presidiare.',
    kpis: [
      { label: 'Feed', value: 'ICS', note: 'agenda, scadenze e completo', tone: 'primary' },
      { label: 'Profili', value: 'Remoti', note: 'sincronizzazione calendario esterno', tone: 'success' },
      { label: 'Token', value: 'Rigenerabile', note: 'sicurezza link calendario', tone: 'warning' },
    ],
    cards: [
      { title: 'Pannello calendario', body: 'Apri configurazione feed, token e profili di sincronizzazione.', href: '/impostazioni/calendario', action: 'Apri pannello', icon: 'calendar', tone: 'primary', meta: 'ICS' },
      { title: 'Export agenda', body: 'Scarica calendario appuntamenti in formato ICS.', href: '/agenda/export.ics', action: 'Scarica agenda', icon: 'download', tone: 'success', meta: 'ICS' },
      { title: 'Export scadenze', body: 'Scarica scadenziario in formato ICS.', href: '/scadenziario/export.ics', action: 'Scarica scadenze', icon: 'clock', tone: 'warning', meta: 'ICS' },
    ],
    workflow: ['Verifica token', 'Copia feed', 'Sincronizza profilo remoto', 'Controlla agenda e scadenziario'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Scadenziario', href: '/scadenziario' }],
  },
  {
    id: 'amministrazione',
    routes: ['/amministrazione'],
    title: 'Amministrazione',
    section: 'Governance',
    subtitle: 'Indice operativo per utenti, permessi, audit, database, GDPR e console amministrative.',
    lexContext: 'amministrazione',
    lexLabel: 'Lex legge ruoli, permessi, audit e rischi di governance.',
    kpis: [
      { label: 'Accesso', value: 'RBAC', note: 'ruoli e permessi controllati', tone: 'primary' },
      { label: 'Audit', value: 'Registro', note: 'eventi e attività tracciate', tone: 'success' },
      { label: 'Compliance', value: 'GDPR', note: 'registro trattamenti e portabilità', tone: 'warning' },
    ],
    cards: [
      { title: 'Utenti', body: 'Gestisci operatori, ruoli, stato account e accessi.', href: '/utenti', action: 'Apri utenti', icon: 'users', tone: 'primary', meta: 'RBAC' },
      { title: 'Profili e permessi', body: 'Controlla matrice ruoli e override individuali.', href: '/profili', action: 'Apri permessi', icon: 'shield', tone: 'success', meta: 'Policy' },
      { title: 'Registro attività', body: 'Consulta audit log e osservabilità operativa.', href: '/registro-attivita', action: 'Apri registro', icon: 'clipboard', tone: 'warning', meta: 'Audit' },
      { title: 'Database e GDPR', body: 'Verifica storage e registro trattamenti.', href: '/admin/database', action: 'Apri database', icon: 'database', tone: 'purple', meta: 'Governance' },
    ],
    workflow: ['Controlla utenti', 'Verifica permessi', 'Leggi audit', 'Aggiorna compliance'],
    links: [{ label: 'Database', href: '/admin/database' }, { label: 'Registro GDPR', href: '/registro-gdpr' }],
  },
  {
    id: 'utenti',
    routes: ['/utenti', '/utenti/nuovo'],
    title: 'Utenti',
    section: 'Accessi studio',
    subtitle: 'Gestione operativa per operatori, ruoli, stato, permessi e accesso alla piattaforma.',
    lexContext: 'utenti',
    lexLabel: 'Lex legge ruoli, permessi e anomalie di accesso.',
    kpis: [
      { label: 'Archivio', value: 'Operatori', note: 'utenti dello studio', tone: 'primary' },
      { label: 'Ruoli', value: 'RBAC', note: 'amministratore, avvocato, collaboratore, segreteria', tone: 'success' },
      { label: 'Sicurezza', value: 'Audit', note: 'azioni sensibili tracciate', tone: 'warning' },
    ],
    cards: [
      { title: 'Lista utenti', body: 'Apri gestione completa utenti con stato e ruoli.', href: '/utenti', action: 'Apri lista', icon: 'users', tone: 'primary', meta: 'Archivio' },
      { title: 'Nuovo utente', body: 'Crea un operatore con ruolo e credenziali iniziali.', href: '/utenti/nuovo', action: 'Crea utente', icon: 'plus', tone: 'success', meta: 'Nuovo' },
      { title: 'Profili e permessi', body: 'Verifica matrice ruoli e policy operative.', href: '/profili', action: 'Apri profili', icon: 'shield', tone: 'warning', meta: 'RBAC' },
    ],
    workflow: ['Crea utente', 'Assegna ruolo', 'Verifica permessi', 'Controlla audit accessi'],
    links: [{ label: 'Amministrazione', href: '/amministrazione' }, { label: 'Registro Attività', href: '/registro-attivita' }],
  },
  {
    id: 'profili',
    routes: ['/profili'],
    title: 'Profili e Permessi',
    section: 'RBAC',
    subtitle: 'Matrice operativa per ruoli, permessi, override utente e controlli di autorizzazione.',
    lexContext: 'profili-permessi',
    lexLabel: 'Lex legge profili e segnala permessi critici da verificare.',
    kpis: [
      { label: 'Ruoli', value: 'Matrice', note: 'permessi per area', tone: 'primary' },
      { label: 'Override', value: 'Utente', note: 'extra e negati individuali', tone: 'warning' },
      { label: 'Policy', value: 'Audit', note: 'modifiche tracciate', tone: 'success' },
    ],
    cards: [
      { title: 'Matrice ruoli', body: 'Apri tabella profili e permessi per ruolo.', href: '/profili', action: 'Apri matrice', icon: 'table', tone: 'primary', meta: 'RBAC' },
      { title: 'Utenti', body: 'Seleziona utente e gestisci override autorizzativi.', href: '/utenti', action: 'Apri utenti', icon: 'users', tone: 'success', meta: 'Operatori' },
      { title: 'Audit permessi', body: 'Controlla cambi ruoli e modifiche autorizzative.', href: '/registro-attivita', action: 'Apri audit', icon: 'clipboard', tone: 'warning', meta: 'Traccia' },
    ],
    workflow: ['Leggi matrice', 'Verifica ruolo utente', 'Applica override motivato', 'Controlla audit'],
    links: [{ label: 'Utenti', href: '/utenti' }, { label: 'Amministrazione', href: '/amministrazione' }],
  },
  {
    id: 'registro-attivita',
    routes: ['/registro-attivita', '/audit', '/admin/osservabilita'],
    title: 'Registro Attività',
    section: 'Audit e osservabilità',
    subtitle: 'Registro operativo per eventi applicativi, audit utenti, esportazione e osservabilità amministrativa.',
    lexContext: 'registro-attivita',
    lexLabel: 'Lex legge eventi e aiuta a individuare anomalie operative.',
    kpis: [
      { label: 'Audit', value: 'Eventi', note: 'azioni sensibili e sicurezza', tone: 'primary' },
      { label: 'Export', value: 'CSV', note: 'estrazione registro', tone: 'success' },
      { label: 'Osservabilità', value: 'Admin', note: 'log e runtime', tone: 'purple' },
    ],
    cards: [
      { title: 'Audit utenti', body: 'Apri registro con azioni e filtri.', href: '/audit', action: 'Apri audit', icon: 'clipboard', tone: 'primary', meta: 'Registro' },
      { title: 'Esporta audit', body: 'Scarica CSV per controlli interni e compliance.', href: '/audit/esporta.csv', action: 'Esporta CSV', icon: 'download', tone: 'success', meta: 'CSV' },
      { title: 'Osservabilità', body: 'Apri superficie amministrativa runtime e telemetria.', href: '/admin/osservabilita', action: 'Apri osservabilità', icon: 'chart', tone: 'purple', meta: 'Admin' },
    ],
    workflow: ['Filtra evento', 'Verifica utente e risorsa', 'Esporta se necessario', 'Azione correttiva'],
    links: [{ label: 'Utenti', href: '/utenti' }, { label: 'Database', href: '/admin/database' }],
  },
  {
    id: 'database',
    routes: ['/admin/database', '/database'],
    title: 'Database',
    section: 'Storage e migrazioni',
    subtitle: 'Controllo operativo per stato storage, SQLite/PostgreSQL, snapshot, migrazione e consistenza dati.',
    lexContext: 'database',
    lexLabel: 'Lex legge stato storage, migrazioni e rischi di coerenza.',
    kpis: [
      { label: 'Storage', value: 'Governato', note: 'JSON, SQLite e SQL runtime', tone: 'primary' },
      { label: 'Migrazioni', value: 'Controllo', note: 'azioni tecniche esplicite', tone: 'warning' },
      { label: 'Export', value: 'DB', note: 'snapshot e download tecnico', tone: 'success' },
    ],
    cards: [
      { title: 'Stato database', body: 'Apri verifica storage, statistiche e snapshot SQLite.', href: '/admin/database', action: 'Apri stato', icon: 'database', tone: 'primary', meta: 'Storage' },
      { title: 'Backup', body: 'Controlla copie prima di ogni migrazione o ripristino.', href: '/backup', action: 'Apri backup', icon: 'backup', tone: 'warning', meta: 'Protezione' },
      { title: 'Registro attività', body: 'Verifica audit delle operazioni tecniche.', href: '/registro-attivita', action: 'Apri registro', icon: 'clipboard', tone: 'purple', meta: 'Audit' },
    ],
    workflow: ['Verifica stato', 'Crea backup', 'Esegui migrazione se richiesta', 'Controlla audit e salute'],
    links: [{ label: 'Backup', href: '/backup' }, { label: 'Amministrazione', href: '/amministrazione' }],
  },
  {
    id: 'gdpr',
    routes: ['/registro-gdpr', '/privacy/registro', '/privacy/registro/nuovo'],
    title: 'Registro GDPR',
    section: 'Privacy e compliance',
    subtitle: 'Registro operativo per trattamenti, basi giuridiche, misure, portabilità e audit privacy.',
    lexContext: 'gdpr',
    lexLabel: 'Lex legge trattamenti, dati personali e punti di verifica GDPR.',
    kpis: [
      { label: 'Trattamenti', value: 'Registro', note: 'attività privacy dello studio', tone: 'primary' },
      { label: 'Diritti', value: 'Portabilita', note: 'export dati cliente', tone: 'success' },
      { label: 'Audit', value: 'Privacy', note: 'eventi e prove di conformità', tone: 'warning' },
    ],
    cards: [
      { title: 'Registro trattamenti', body: 'Apri registro privacy e trattamenti gestiti.', href: '/privacy/registro', action: 'Apri registro', icon: 'shield', tone: 'primary', meta: 'GDPR' },
      { title: 'Nuovo trattamento', body: 'Registra finalità, base giuridica, dati e misure.', href: '/privacy/registro/nuovo', action: 'Nuovo trattamento', icon: 'plus', tone: 'success', meta: 'Compliance' },
      { title: 'Audit privacy', body: 'Esporta e verifica attività collegate a dati personali.', href: '/audit/esporta.csv', action: 'Esporta audit', icon: 'download', tone: 'warning', meta: 'CSV' },
    ],
    workflow: ['Censisci trattamento', 'Verifica base giuridica', 'Collega misure', 'Mantieni prova audit'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Registro Attività', href: '/registro-attivita' }],
  },
]

function normalize(path: string): string {
  const clean = (path || '/').split('?')[0].replace(/\/+$/, '') || '/'
  if (clean === '/app-v2') return '/'
  return clean.startsWith('/app-v2/') ? clean.slice('/app-v2'.length) || '/' : clean
}

export function findStudioModule(path: string): StudioModuleConfig | undefined {
  const route = normalize(path).toLowerCase()
  let best: { module: StudioModuleConfig; length: number } | undefined
  studioModules.forEach((module) => {
    module.routes.forEach((candidate) => {
      const clean = candidate.toLowerCase()
      if (route === clean || route.startsWith(`${clean}/`)) {
        if (!best || clean.length > best.length) best = { module, length: clean.length }
      }
    })
  })
  return best?.module
}

export function isStudioModuleRoute(path: string): boolean {
  return Boolean(findStudioModule(path))
}
