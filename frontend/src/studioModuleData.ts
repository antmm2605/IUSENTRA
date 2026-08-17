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
  { label: 'Controllo Studio', href: '/workspace-intelligente' },
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
      { label: 'Controlli', value: 'Attivi', note: 'registro e permessi collegati alle funzioni sensibili', tone: 'warning' },
    ],
    cards: [
      { title: 'Dati studio', body: 'Anagrafica, titolare, recapiti, albo, coordinate e dati usati in atti, parcelle e depositi.', href: '/impostazioni#dati-studio', action: 'Apri dati studio', icon: 'building', tone: 'primary', meta: 'Impostazioni' },
      { title: 'Comunicazioni', body: 'Configura PEC, posta ordinaria, SMTP e canali WhatsApp senza perdere il presidio locale.', href: '/impostazioni?tab=pec', action: 'Apri canali', icon: 'mail', tone: 'success', meta: 'PEC / SMTP' },
      { title: 'Sito Studio', body: 'Gestisci contenuti, richieste contatto, prenotazioni e anteprima pubblica dello studio.', href: '/sito-studio', action: 'Apri sito', icon: 'earth', tone: 'purple', meta: 'Presenza digitale' },
      { title: 'Backup e continuità', body: 'Verifica copie, integrità e conservazione dei dati dello studio.', href: '/impostazioni?tab=backup', action: 'Apri backup', icon: 'backup', tone: 'warning', meta: 'Impostazioni' },
    ],
    workflow: ['Completa dati studio', 'Verifica canali PEC e SMTP', 'Aggiorna sito pubblico', 'Controlla backup e registro'],
    links: [...commonStudioLinks, { label: 'Impostazioni Studio', href: '/impostazioni' }, { label: 'Registro GDPR', href: '/privacy/registro' }],
  },
  {
    id: 'fatturazione',
    routes: ['/fatturazione', '/fatturazione/nuova'],
    title: 'Parcelle e Fatture',
    section: 'Economico',
    subtitle: 'Pagina operativa per parcelle, fatture, PDF, XML, scadenze di pagamento e incassi collegati.',
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
      { title: 'Incassi e pagamenti', body: 'Gestisci canali, link di pagamento e stato operativo degli incassi.', href: '/impostazioni?tab=pagamenti', action: 'Apri pagamenti', icon: 'card', tone: 'orange', meta: 'Canali' },
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
    subtitle: 'Controllo operativo per preventivi, conferimenti, percorso di accettazione e conversione in parcella.',
    lexContext: 'preventivi',
    lexLabel: 'Lex legge preventivo, conferimento, cliente e fascicolo collegato.',
    kpis: [
      { label: 'Flussi', value: '2', note: 'preventivo e conferimento incarico', tone: 'primary' },
      { label: 'Percorso guidato', value: 'DM 55', note: 'calcolo guidato e generazione preventivo', tone: 'purple' },
      { label: 'Conversione', value: 'Parcella', note: 'passaggio a fatturazione già previsto', tone: 'success' },
    ],
    cards: [
      { title: 'Archivio preventivi', body: 'Filtra bozze, inviati, accettati e pratiche senza conferimento.', href: '/preventivi/', action: 'Apri archivio', icon: 'file', tone: 'primary', meta: 'Archivio operativo' },
      { title: 'Nuovo preventivo', body: 'Crea proposta economica con cliente, fascicolo, voci e condizioni.', href: '/preventivi/nuovo', action: 'Crea preventivo', icon: 'plus', tone: 'success', meta: 'Nuovo' },
      { title: 'Conferimento incarico', body: 'Predisponi l’incarico e collega accettazione, firma e fascicolo.', href: '/preventivi/conferimento/nuovo', action: 'Crea incarico', icon: 'shield', tone: 'warning', meta: 'Mandato' },
      { title: 'Percorso compensi', body: 'Calcola e genera preventivo con parametri forensi e dati pratica.', href: '/preventivi/wizard', action: 'Apri percorso', icon: 'spark', tone: 'purple', meta: 'Guidato' },
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
      { label: 'Fonte calcolo', value: 'Parametri', note: 'tariffario e percorso guidato gia presenti', tone: 'primary' },
      { label: 'Risultato', value: 'Preventivo', note: 'riuso diretto nel percorso incarichi', tone: 'success' },
      { label: 'Controllo', value: 'Registro', note: 'traccia calcolo e log compensi', tone: 'warning' },
    ],
    cards: [
      { title: 'Tariffario', body: 'Apri il calcolo compensi con parametri, fasi e log.', href: '/tariffario', action: 'Apri tariffario', icon: 'banknote', tone: 'primary', meta: 'Calcolo' },
      { title: 'Percorso preventivo', body: 'Trasforma il calcolo in proposta al cliente e incarico.', href: '/preventivi/wizard', action: 'Genera preventivo', icon: 'spark', tone: 'success', meta: 'Guidato' },
      { title: 'Strumenti Forensi', body: 'Usa onorari, contributo unificato, interessi, rivalutazione e altri calcoli.', href: '/strumenti-legali', action: 'Apri strumenti', icon: 'wrench', tone: 'purple', meta: 'Suite' },
    ],
    workflow: ['Seleziona materia e valore', 'Verifica fasi applicabili', 'Consolida log calcolo', 'Genera preventivo o parcella'],
    links: [{ label: 'Preventivi', href: '/preventivi' }, { label: 'Parcelle', href: '/fatturazione' }],
  },
  {
    id: 'documenti',
    routes: ['/documenti'],
    title: 'Documenti',
    section: 'Documenti e atti',
    subtitle: 'Punto di ingresso operativo per documenti fascicolo, modelli, redazione atti e ricerca documentale dello studio.',
    lexContext: 'documenti',
    lexLabel: 'Lex legge fascicoli, documenti, modelli e fonti interne collegate alla lavorazione aperta.',
    kpis: [
      { label: 'Archivio', value: 'Fascicoli', note: 'documenti conservati nelle pratiche dello studio', tone: 'primary' },
      { label: 'Modelli', value: 'Template', note: 'catalogo atti e redazione collegati', tone: 'purple' },
      { label: 'Ricerca', value: 'Studio', note: 'trova documenti, PEC, clienti e fascicoli', tone: 'success' },
    ],
    cards: [
      { title: 'Documenti fascicolo', body: 'Apri i fascicoli e lavora sui documenti della pratica, con upload, firma e controlli collegati.', href: '/fascicoli', action: 'Apri fascicoli', icon: 'folder', tone: 'primary', meta: 'Pratiche' },
      { title: 'Catalogo atti', body: 'Consulta modelli, filtri e schede operative per predisporre atti coerenti con la pratica.', href: '/template-atti/catalogo', action: 'Apri catalogo', icon: 'book', tone: 'purple', meta: 'Template' },
      { title: 'Redazione atti', body: 'Rientra nel workspace di redazione per preparare bozze, template e produzione atti.', href: '/redazione-atti', action: 'Apri redazione', icon: 'file', tone: 'success', meta: 'Atti' },
      { title: 'Ricerca documenti', body: 'Cerca rapidamente documenti, comunicazioni e riferimenti collegati ai fascicoli.', href: '/global-search?tipo=documenti', action: 'Cerca documenti', icon: 'book', tone: 'neutral', meta: 'Ricerca' },
    ],
    workflow: ['Scegli fascicolo o modello', 'Verifica documenti e allegati', 'Prepara o aggiorna atto', 'Cerca e collega al lavoro di studio'],
    links: [{ label: 'Fascicoli', href: '/fascicoli' }, { label: 'Catalogo Atti', href: '/template-atti/catalogo' }, { label: 'Redazione Atti', href: '/redazione-atti' }, { label: 'Ricerca Studio', href: '/global-search?tipo=documenti' }],
  },
  {
    id: 'editor-professionale',
    routes: ['/editor-professionale'],
    title: 'Editor professionale',
    section: 'Documenti e atti',
    subtitle: 'Centro operativo per scrivere, controllare, leggere documenti firmati e richiamare Lex senza sostituire Redazione Atti.',
    lexContext: 'editor-professionale',
    lexLabel: 'Lex legge documento, fascicolo, PEC, email, allegati firmati e contesto redazionale aperto.',
    kpis: [
      { label: 'Scrittura', value: 'Atti', note: 'redazione e controllo testi collegati allo studio', tone: 'primary' },
      { label: 'Lettura', value: 'Firmati', note: 'PDF, PDF.P7M, XML, EML e TXT dove visualizzabili', tone: 'success' },
      { label: 'Ricerca', value: 'Studio', note: 'documenti, fascicoli, PEC ed email indicizzati', tone: 'purple' },
    ],
    cards: [
      { title: 'Redazione atti', body: 'Apre il modulo specifico per bozze, modelli e produzione degli atti.', href: '/redazione-atti', action: 'Apri redazione', icon: 'file', tone: 'primary', meta: 'Atti' },
      { title: 'Documenti fascicolo', body: 'Consulta documenti, firmati e allegati collegati alle pratiche.', href: '/fascicoli', action: 'Apri fascicoli', icon: 'folder', tone: 'success', meta: 'Pratiche' },
      { title: 'Ricerca documenti', body: 'Cerca rapidamente documenti, PEC, email e contenuti testuali.', href: '/global-search?tipo=documenti', action: 'Cerca', icon: 'book', tone: 'purple', meta: 'Ricerca' },
      { title: 'Modelli atti', body: 'Usa catalogo e percorsi di compilazione senza confonderli con il centro editor.', href: '/template-atti/catalogo', action: 'Apri modelli', icon: 'book', tone: 'neutral', meta: 'Template' },
    ],
    workflow: ['Apri documento o fascicolo', 'Controlla contenuto e formato', 'Redigi o richiama Lex', 'Salva, firma o collega alla pratica'],
    links: [{ label: 'Redazione Atti', href: '/redazione-atti' }, { label: 'Fascicoli', href: '/fascicoli' }, { label: 'PEC', href: '/email/' }, { label: 'Email ordinaria', href: '/email-ordinaria/' }],
  },
  {
    id: 'redazione-atti',
    routes: ['/redazione-atti', '/template-atti', '/template-atti/catalogo', '/template-atti/nuovo', '/checklist'],
    title: 'Redazione Atti',
    section: 'Redazione documenti',
    subtitle: 'Punto di ingresso operativo per modelli, catalogo atti, redazione guidata e assistente redazionale.',
    lexContext: 'redazione-atti',
    lexLabel: 'Lex legge modello, fascicolo, parti, documenti e checklist di deposito.',
    kpis: [
      { label: 'Catalogo', value: 'Template', note: 'modelli e compliance deposito', tone: 'primary' },
      { label: 'Editor', value: 'Atti', note: 'compilazione guidata e PDF', tone: 'success' },
      { label: 'Assistente', value: 'Redazionale', note: 'supporto locale verificabile', tone: 'purple' },
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
    routes: [
      '/portali/pst/acquisizione',
      '/polisweb/acquisizione',
      '/importa-pratiche',
      '/importa-pratiche-studio-telematico',
      '/import/quickorganizer',
    ],
    title: 'Importa pratica da PST',
    section: 'PolisWeb / PST',
    subtitle: 'Pagina operativa per acquisire pratiche da PST con collegamento locale, file autorizzati e percorso guidato governato.',
    lexContext: 'pst-acquisizione',
    lexLabel: 'Lex legge canale PST, fascicolo locale, mapping documenti e stato del connettore locale.',
    kpis: [
      { label: 'Canale', value: 'PST', note: 'consultazione e import autorizzato', tone: 'primary' },
      { label: 'Locale', value: 'Connector', note: 'CNS, browser guidato e file importati dall utente', tone: 'success' },
      { label: 'Registro', value: 'Import', note: 'collegamento fascicolo e documenti tracciati', tone: 'warning' },
    ],
    cards: [
      { title: 'Acquisizione PST', body: 'Apri il percorso guidato PolisWeb / PST e verifica tutti i passaggi di importazione.', href: '/portali/pst/acquisizione', action: 'Apri acquisizione', icon: 'upload', tone: 'primary', meta: 'Guidato' },
      { title: 'Importa pratiche', body: 'Carica il pacchetto esportato e collega fascicoli, soggetti, atti ed email alla pratica locale.', href: '/importa-pratiche', action: 'Apri import', icon: 'upload', tone: 'purple', meta: 'Pacchetto' },
      { title: 'Checklist import PST', body: 'Controlla prerequisiti, mapping fascicolo e documenti prima dell importazione.', href: '/portali/pst/acquisizione#checklist-operativa', action: 'Verifica flusso', icon: 'briefcase', tone: 'success', meta: 'Presidio' },
      { title: 'Fascicoli', body: 'Controlla o crea la pratica locale prima di collegare documenti e buste.', href: '/fascicoli', action: 'Apri fascicoli', icon: 'folder', tone: 'warning', meta: 'Mapping' },
      { title: 'Centro telematico', body: 'Rientra nel quadro generale di PST, PDP, PAT e PTT.', href: '/telematico', action: 'Apri centro', icon: 'send', tone: 'purple', meta: 'Portali' },
    ],
    workflow: ['Verifica accesso locale', 'Seleziona fascicolo PST', 'Riconcilia documenti', 'Importa e controlla registro'],
    links: [{ label: 'PolisWeb / PST', href: '/polisWeb' }, { label: 'Centro telematico', href: '/telematico' }, { label: 'Acquisizione guidata', href: '/portali/pst/acquisizione' }, { label: 'Importa pratiche', href: '/importa-pratiche' }],
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
      { label: 'Servizi', value: 'Pronti', note: 'statistiche già disponibili', tone: 'success' },
      { label: 'Uso', value: 'Direzione', note: 'lettura gestionale e controllo studio', tone: 'purple' },
    ],
    cards: [
      { title: 'Cruscotto grafici', body: 'Apri grafici, indicatori e riepilogo operativo completo.', href: '/statistiche/', action: 'Apri cruscotto', icon: 'chart', tone: 'primary', meta: 'Grafici' },
      { title: 'Produttività', body: 'Analizza attività, timesheet e volume operativo dello studio.', href: '/statistiche/?view=produttivita', action: 'Vedi analisi', icon: 'table', tone: 'success', meta: 'Analisi' },
      { title: 'Depositi trend', body: 'Controlla andamento depositi e canali telematici.', href: '/statistiche/?view=depositi', action: 'Trend depositi', icon: 'send', tone: 'warning', meta: 'Telematico' },
    ],
    workflow: ['Aggiorna dati', 'Leggi indicatori', 'Isola anomalie', 'Apri modulo operativo collegato'],
    links: [{ label: 'Fatturazione', href: '/fatturazione' }, { label: 'Fascicoli', href: '/fascicoli' }, { label: 'Scadenziario', href: '/scadenziario' }],
  },
  {
    id: 'ricerca-legale',
    routes: [
      '/ricerca-legale',
      '/ricerca-legale/news',
      '/ricerca-legale/mediazione',
      '/ricerca-legale/ricerca',
      '/legal-intelligence/news',
      '/legal-intelligence/mediazione',
    ],
    title: 'Ricerca Legale',
    section: 'Ricerca legale',
    subtitle: 'Monitoraggio normativo, aggiornamenti, news, mediazione e fonti da collegare al lavoro di studio.',
    lexContext: 'ricerca-legale',
    lexLabel: 'Lex distingue fonti, aggiornamenti, impatto pratico e fascicoli collegabili.',
    kpis: [
      { label: 'Fonti', value: 'Monitor', note: 'aggiornamenti e quadro fonti', tone: 'primary' },
      { label: 'News', value: 'Studio', note: 'archivio aggiornamenti legali', tone: 'success' },
      { label: 'Revisione', value: 'Umana', note: 'approvazione contenuti prima dell’uso', tone: 'warning' },
    ],
    cards: [
      { title: 'Cruscotto ricerca', body: 'Apri monitor normativo e quadro Ricerca legale.', href: '/ricerca-legale', action: 'Apri ricerca', icon: 'book', tone: 'primary', meta: 'Fonti' },
      { title: 'News legali', body: 'Consulta aggiornamenti, filtri per materia e dettaglio news.', href: '/ricerca-legale/news', action: 'Apri news', icon: 'earth', tone: 'success', meta: 'Aggiornamenti' },
      { title: 'Registro mediazione', body: 'Verifica organismi, dati e aggiornamenti collegati alla mediazione.', href: '/ricerca-legale/mediazione', action: 'Apri registro', icon: 'landmark', tone: 'purple', meta: 'Mediazione' },
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
      { label: 'Classifica', value: 'Assistita', note: 'suggerimento controllato', tone: 'purple' },
    ],
    cards: [
      { title: 'Ricerca sentenze', body: 'Apri archivio con filtri per fonte, area, branca, grado e orientamento.', href: '/giurisprudenza/', action: 'Apri archivio', icon: 'landmark', tone: 'primary', meta: 'Archivio' },
      { title: 'Nuova scheda', body: 'Registra manualmente una sentenza o un provvedimento rilevante.', href: '/giurisprudenza/nuova', action: 'Nuova scheda', icon: 'plus', tone: 'success', meta: 'Inserimento' },
      { title: 'Importa materiale', body: 'Collega materiale giurisprudenziale e fonti all archivio interno.', href: '/giurisprudenza/', action: 'Importa', icon: 'upload', tone: 'warning', meta: 'Import' },
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
      { label: 'Funzioni', value: '71', note: 'voci operative collegate', tone: 'primary' },
      { label: 'Prefill', value: 'Fascicolo', note: 'dati cliente e pratica riutilizzabili', tone: 'success' },
      { label: 'Esiti', value: 'Tracciati', note: 'risultati verificabili e ripetibili', tone: 'warning' },
    ],
    cards: [
      { title: 'Uffici competenti', body: "Cerca il Comune e apri Tribunale, Giudice di Pace, Procura, UNEP e Corte d'Appello con recapiti e assistenza.", href: '/strumenti-legali/?tool=uffici_competenti#funzione-operativa', action: 'Cerca Comune', icon: 'map-pin', tone: 'success', meta: 'Competenza' },
      { title: 'Suite strumenti', body: 'Apri contributo unificato, interessi, onorari, TFR, usura e altri calcoli.', href: '/strumenti-legali/', action: 'Apri suite', icon: 'wrench', tone: 'primary', meta: 'Calcolo' },
      { title: 'Onorari forensi', body: 'Calcola fasi, valore controversia e parametri collegabili a preventivi.', href: '/strumenti-legali/?tool=onorari_forensi', action: 'Calcola onorari', icon: 'banknote', tone: 'success', meta: 'DM 55' },
      { title: 'Contributo unificato', body: 'Determina importi e controlli collegati al deposito.', href: '/strumenti-legali/?tool=contributo_unificato', action: 'Calcola CU', icon: 'check', tone: 'warning', meta: 'Deposito' },
      { title: 'Interessi legali e mora', body: 'Calcola interessi per capitale, periodo e tasso applicabile.', href: '/strumenti-legali/?tool=interessi', action: 'Calcola interessi', icon: 'chart', tone: 'primary', meta: 'Crediti' },
      { title: 'Nota credito', body: 'Prepara capitale, interessi, spese e residuo in una bozza controllabile.', href: '/strumenti-legali/?tool=nota_credito', action: 'Genera nota', icon: 'file', tone: 'success', meta: 'Credito' },
      { title: 'Pignoramento', body: 'Simula quota pignorabile su stipendio o pensione con regime corretto.', href: '/strumenti-legali/?tool=pignoramento', action: 'Simula quota', icon: 'banknote', tone: 'warning', meta: 'Esecuzione' },
      { title: 'Rivalutazione ISTAT', body: 'Aggiorna importi e indici per conteggi documentabili.', href: '/strumenti-legali/?tool=rivalutazione_istat', action: 'Rivaluta importo', icon: 'table', tone: 'success', meta: 'Indici' },
      { title: 'Adeguamento canone', body: 'Aggiorna il canone annuo con indice e percentuale applicabile.', href: '/strumenti-legali/?tool=canone_locazione', action: 'Aggiorna canone', icon: 'building', tone: 'primary', meta: 'Locazioni' },
      { title: 'Verifica usura', body: 'Controlla soglie e dati del finanziamento prima del deposito in fascicolo.', href: '/strumenti-legali/?tool=usura', action: 'Verifica usura', icon: 'shield', tone: 'danger', meta: 'Banche' },
      { title: 'Cassa Forense', body: 'Calcola contributi soggettivo, integrativo e maternita per anno.', href: '/strumenti-legali/?tool=contributi_cassa_forense', action: 'Calcola contributi', icon: 'users', tone: 'purple', meta: 'Previdenza' },
      { title: 'Piano ammortamento', body: 'Prepara rate, interessi e residuo per mutui e finanziamenti.', href: '/strumenti-legali/?tool=piano_ammortamento', action: 'Crea piano', icon: 'file', tone: 'orange', meta: 'Mutui' },
      { title: 'Danno biologico', body: 'Stima il danno con eta, invalidita e personalizzazione.', href: '/strumenti-legali/?tool=danno_biologico', action: 'Calcola danno', icon: 'clipboard', tone: 'purple', meta: 'Risarcimento' },
      { title: 'Prescrizione civile', body: 'Calcola termine, interruzione e giorni residui per diritti e azioni.', href: '/strumenti-legali/?tool=prescrizione', action: 'Calcola scadenza', icon: 'clock', tone: 'warning', meta: 'Termini' },
      { title: 'Imposta registro', body: 'Stima imposta, aliquota e quota per parte su atti giudiziari.', href: '/strumenti-legali/?tool=imposta_registro', action: 'Calcola imposta', icon: 'file', tone: 'orange', meta: 'Fiscale' },
      { title: 'Prescrizione reati', body: 'Valuta termini e sospensioni con una scheda riepilogativa.', href: '/strumenti-legali/?tool=prescrizione_penale', action: 'Calcola termine', icon: 'clock', tone: 'warning', meta: 'Penale' },
      { title: 'Custodia cautelare', body: 'Controlla interrogatorio, riesame e deposito motivazione.', href: '/strumenti-legali/?tool=custodia_cautelare', action: 'Calcola termini', icon: 'shield', tone: 'danger', meta: 'Penale' },
      { title: 'Successione legittima', body: 'Ripartisci quote ereditarie in base ai soggetti indicati.', href: '/strumenti-legali/?tool=successione_legittima', action: 'Calcola quote', icon: 'users', tone: 'success', meta: 'Famiglia' },
      { title: 'Cedolare secca', body: 'Confronta canoni e imposta dovuta per locazioni.', href: '/strumenti-legali/?tool=cedolare_secca', action: 'Calcola imposta', icon: 'building', tone: 'primary', meta: 'Locazioni' },
      { title: 'Trattamento di fine rapporto', body: 'Calcola quote, rivalutazione e riepilogo del rapporto.', href: '/strumenti-legali/?tool=tfr', action: 'Calcola TFR', icon: 'banknote', tone: 'orange', meta: 'Lavoro' },
      { title: 'Indennita licenziamento', body: 'Stima mensilita e importo in base ad anzianita e regime.', href: '/strumenti-legali/?tool=indennita_licenziamento', action: 'Calcola indennita', icon: 'users', tone: 'warning', meta: 'Lavoro' },
      { title: 'Compenso CTU', body: 'Predisponi compenso e spese per consulenze tecniche.', href: '/strumenti-legali/?tool=ctu', action: 'Calcola CTU', icon: 'landmark', tone: 'purple', meta: 'Consulenze' },
      { title: 'Mediazione', body: 'Apri registro e riferimenti utili per costi e organismi.', href: '/ricerca-legale/mediazione', action: 'Apri mediazione', icon: 'landmark', tone: 'success', meta: 'ADR' },
      { title: 'Preventivo da calcolo', body: 'Porta il risultato nel flusso guidato per preventivi e incarichi.', href: '/preventivi/wizard', action: 'Crea preventivo', icon: 'send', tone: 'primary', meta: 'Incarichi' },
    ],
    workflow: ['Cerca Comune o strumento', 'Collega fascicolo se utile', 'Calcola e verifica', 'Riporta risultato in pratica'],
    links: [{ label: 'Compensi Forensi', href: '/compensi-forensi' }, { label: 'Fascicoli', href: '/fascicoli' }, { label: 'Notifiche legali', href: '/notifiche-legali' }],
  },
  {
    id: 'timesheet',
    routes: ['/timesheet'],
    title: 'Timesheet',
    section: 'Tempo e produttività',
    subtitle: 'Pagina operativa per registrare attività, validare ore, collegare clienti e generare parcelle.',
    lexContext: 'timesheet',
    lexLabel: 'Lex legge attività, cliente, fascicolo, stato fatturabile e prossima azione economica.',
    kpis: [
      { label: 'Registrazione', value: 'Ore', note: 'attività manuali e collegate ai fascicoli', tone: 'primary' },
      { label: 'Validazione', value: 'Stati', note: 'bozza, validato, fatturato e non fatturabile', tone: 'success' },
      { label: 'Output', value: 'Parcella', note: 'generazione da voci validate', tone: 'orange' },
    ],
    cards: [
      { title: 'Cruscotto tempi', body: 'Apri riepilogo, filtri per cliente, fascicolo, stato e utente.', href: '/timesheet', action: 'Apri timesheet', icon: 'clock', tone: 'primary', meta: 'Operativo' },
      { title: 'Nuova attività', body: 'Registra una voce tempo da cliente o fascicolo con importo fatturabile.', href: '/agenda', action: 'Aggancia agenda', icon: 'calendar', tone: 'success', meta: 'Percorso' },
      { title: 'Genera parcella', body: 'Consolida le voci validate e prepara il documento economico.', href: '/fatturazione/nuova', action: 'Crea parcella', icon: 'file', tone: 'orange', meta: 'Economico' },
      { title: 'Produttività', body: 'Leggi indicatori e andamento operativo dello studio.', href: '/statistiche/?view=produttivita', action: 'Vedi indicatori', icon: 'chart', tone: 'purple', meta: 'Analisi' },
    ],
    workflow: ['Registra attività', 'Valida le voci', 'Filtra per cliente o fascicolo', 'Genera parcella e controlla registro'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Parcelle', href: '/fatturazione' }, { label: 'Statistiche', href: '/statistiche/?view=produttivita' }],
  },
  {
    id: 'cartelle-condivise',
    routes: ['/cartelle-condivise'],
    title: 'Cartelle Condivise',
    section: 'Collaborazione clienti',
    subtitle: 'Pagina operativa per accessi condivisi, collaboratori, scadenze permessi e cartelle clienti.',
    lexContext: 'cartelle-condivise',
    lexLabel: 'Lex legge cliente, collaboratori, ruolo assegnato, scadenza accesso e rischi privacy.',
    kpis: [
      { label: 'Accessi', value: 'Clienti', note: 'cartelle condivise e collaboratori', tone: 'primary' },
      { label: 'Ruoli', value: 'Permessi', note: 'lettura, scrittura e gestione', tone: 'success' },
      { label: 'Privacy', value: 'Registro', note: 'scadenze e tracciamento condivisioni', tone: 'warning' },
    ],
    cards: [
      { title: 'Cartelle condivise', body: 'Apri elenco accessi gestiti e cartelle ricevute.', href: '/cartelle-condivise', action: 'Apri cartelle', icon: 'folder', tone: 'primary', meta: 'Operativo' },
      { title: 'Clienti', body: 'Seleziona cliente e gestisci collaboratori dalla cartella.', href: '/clienti', action: 'Apri clienti', icon: 'users', tone: 'success', meta: 'Anagrafiche' },
      { title: 'Registro attività', body: 'Controlla aperture, modifiche e condivisioni sensibili.', href: '/audit', action: 'Apri registro', icon: 'clipboard', tone: 'warning', meta: 'Tracciamento' },
    ],
    workflow: ['Scegli cliente', 'Assegna collaboratore e ruolo', 'Imposta scadenza', 'Verifica registro e privacy'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Registro GDPR', href: '/privacy/registro' }, { label: 'Registro attività', href: '/audit' }],
  },
  {
    id: 'strumenti-operativi',
    routes: ['/strumenti-operativi', '/applicazioni'],
    title: 'Strumenti Operativi',
    section: 'Operatività studio',
    subtitle: 'Catalogo completo delle funzioni dello studio, ricercabile per nome e area di lavoro.',
    lexContext: 'strumenti-operativi',
    lexLabel: 'Lex legge il contesto operativo e propone il modulo più utile.',
    kpis: [
      { label: 'Catalogo', value: 'Completo', note: 'tutte le funzioni in un solo punto', tone: 'primary' },
      { label: 'Ricerca', value: 'Per area', note: 'nome, argomento e ambito di lavoro', tone: 'success' },
      { label: 'Percorsi', value: 'Collegati', note: 'accesso alla funzione necessaria', tone: 'purple' },
    ],
    cards: [
      { title: 'Catalogo funzioni', body: 'Cerca nel catalogo completo per nome, argomento o area di lavoro.', href: '/strumenti-operativi#catalogo-funzioni', action: 'Apri catalogo', icon: 'search', tone: 'primary', meta: 'Tutte le funzioni' },
      { title: 'Timesheet', body: 'Registra attività e genera parcelle dalle ore lavorate.', href: '/timesheet', action: 'Apri timesheet', icon: 'clock', tone: 'primary', meta: 'Tempo' },
      { title: 'Esporta dati', body: 'Scarica i dati economici dello studio per controlli e analisi.', href: '/export/fatturazione.csv', action: 'Esporta', icon: 'download', tone: 'success', meta: 'Dati economici' },
      { title: 'Condivisioni', body: 'Gestisci cartelle condivise e accesso documentale dei clienti.', href: '/cartelle-condivise', action: 'Apri condivisioni', icon: 'folder', tone: 'warning', meta: 'Clienti' },
      { title: 'Controllo Studio', body: 'Torna al quadro con priorità e prossime azioni.', href: '/workspace-intelligente', action: 'Apri controllo', icon: 'spark', tone: 'purple', meta: 'Priorità' },
      { title: 'Agenda', body: 'Apri appuntamenti, udienze e calendario dello studio.', href: '/agenda', action: 'Apri agenda', icon: 'calendar', tone: 'primary', meta: 'Calendario' },
      { title: 'Nuovo appuntamento', body: 'Inserisci un impegno collegato a cliente o fascicolo.', href: '/agenda/nuovo', action: 'Crea appuntamento', icon: 'plus', tone: 'success', meta: 'Agenda' },
      { title: 'Ricerca studio', body: 'Trova rapidamente fascicoli, clienti, scadenze, comunicazioni e documenti.', href: '/global-search', action: 'Cerca', icon: 'book', tone: 'purple', meta: 'Ricerca' },
      { title: 'Scadenziario', body: 'Controlla termini, stati e prossime azioni da completare.', href: '/scadenziario', action: 'Apri scadenze', icon: 'check', tone: 'warning', meta: 'Termini' },
      { title: 'Messaggi clienti', body: 'Gestisci conversazioni, SMS e WhatsApp collegati allo studio.', href: '/messaggi', action: 'Apri messaggi', icon: 'message', tone: 'success', meta: 'Comunicazioni' },
      { title: 'Posta ordinaria', body: 'Apri email inviate e ricevute dal canale ordinario dello studio.', href: '/email-ordinaria/', action: 'Apri posta', icon: 'mail', tone: 'primary', meta: 'Email' },
      { title: 'PEC', body: 'Controlla casella, allegati e messaggi rilevanti per le pratiche.', href: '/email/', action: 'Apri PEC', icon: 'mail', tone: 'warning', meta: 'PEC' },
      { title: 'Archivi dello studio', body: 'Verifica integrità e manutenzione degli archivi.', href: '/admin/database', action: 'Apri archivi', icon: 'database', tone: 'purple', meta: 'Dati' },
      { title: 'Copie di sicurezza', body: 'Controlla copie, verifica e pianificazione nelle impostazioni.', href: '/impostazioni?tab=backup', action: 'Apri copie', icon: 'backup', tone: 'orange', meta: 'Continuità' },
      { title: 'Calendari', body: 'Gestisci link riservati e sincronizzazione agenda.', href: '/impostazioni/calendario', action: 'Apri calendari', icon: 'calendar', tone: 'success', meta: 'Sincronizzazione' },
      { title: 'Contatti sito', body: 'Apri richieste e prenotazioni arrivate dal sito dello studio.', href: '/sito-studio/contatti', action: 'Apri contatti', icon: 'earth', tone: 'primary', meta: 'Sito' },
      { title: 'Registro attività', body: 'Consulta eventi importanti e controlli amministrativi.', href: '/registro-attivita', action: 'Apri registro', icon: 'clipboard', tone: 'neutral', meta: 'Tracciamento' },
    ],
    workflow: ['Cerca la funzione', 'Filtra per area se necessario', 'Apri il percorso collegato', 'Completa il lavoro nel modulo dedicato'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Messaggi', href: '/messaggi' }, { label: 'Copie di sicurezza', href: '/impostazioni?tab=backup' }],
  },
  {
    id: 'sito-studio',
    routes: ['/sito-studio', '/sito-studio/builder', '/sito-studio/redazione-ai', '/sito-studio/articoli/:id/modifica', '/sito-studio/contatti'],
    title: 'Sito Studio',
    section: 'Presenza digitale',
    subtitle: 'Pannello operativo per sito pubblico, contenuti, servizi, professionisti, sedi, richieste e prenotazioni.',
    lexContext: 'sito-studio',
    lexLabel: 'Lex legge contenuti del sito, richieste e conversione in clienti.',
    kpis: [
      { label: 'Contenuti', value: 'Sito', note: 'servizi, professionisti, sedi e blocchi', tone: 'primary' },
      { label: 'Lead', value: 'Contatti', note: 'richieste convertibili in clienti', tone: 'success' },
      { label: 'Booking', value: 'Slot', note: 'regole e disponibilità appuntamenti', tone: 'warning' },
    ],
    cards: [
      { title: 'Cruscotto sito', body: 'Apri controllo contenuti, richieste, prenotazioni e stato pubblicazione.', href: '/sito-studio/', action: 'Apri cruscotto', icon: 'earth', tone: 'primary', meta: 'Contenuti' },
      { title: 'Editor sito', body: 'Modifica blocchi, struttura e contenuti avanzati del sito.', href: '/sito-studio/builder', action: 'Apri editor', icon: 'wrench', tone: 'purple', meta: 'Impaginazione' },
      { title: 'Assistente contenuti', body: 'Prepara bozze, immagini e pubblicazione degli articoli con controlli redazionali.', href: '/sito-studio/redazione-ai', action: 'Apri assistente', icon: 'spark', tone: 'warning', meta: 'Articoli' },
      { title: 'Richieste contatto', body: 'Valuta contatti arrivati dal sito e crea anagrafiche clienti.', href: '/sito-studio/contatti', action: 'Apri contatti', icon: 'mail', tone: 'success', meta: 'Lead' },
    ],
    workflow: ['Aggiorna contenuti', 'Pubblica anteprima', 'Gestisci richieste', 'Converti lead in cliente'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Agenda', href: '/agenda' }],
  },
  {
    id: 'notifiche-whatsapp',
    routes: ['/notifiche-whatsapp', '/notifiche'],
    title: 'Notifiche',
    section: 'Comunicazioni automatiche',
    subtitle: 'Promemoria, messaggi WhatsApp e registro comunicazioni in Impostazioni.',
    lexContext: 'notifiche-whatsapp',
    lexLabel: 'Lex legge destinatario, pratica, scadenza e tono del messaggio.',
    kpis: [
      { label: 'Canale', value: 'WhatsApp', note: 'automatico o manuale', tone: 'success' },
      { label: 'Promemoria', value: 'Agenda', note: 'domani, scadenze e appuntamenti', tone: 'warning' },
      { label: 'Registro', value: 'Messaggi', note: 'invii tracciati nello studio', tone: 'primary' },
    ],
    cards: [
      { title: 'Notifiche', body: 'Apri invio messaggi e promemoria collegati a clienti e scadenze.', href: '/impostazioni?tab=notifiche', action: 'Apri notifiche', icon: 'message', tone: 'success', meta: 'Invio' },
      { title: 'Configura WhatsApp', body: 'Gestisci canale e numeri nelle impostazioni studio.', href: '/impostazioni?tab=whatsapp', action: 'Apri configurazione', icon: 'settings', tone: 'primary', meta: 'WhatsApp' },
      { title: 'Messaggi clienti', body: 'Controlla conversazioni e crea messaggi collegati al cliente.', href: '/messaggi', action: 'Apri messaggi', icon: 'mail', tone: 'purple', meta: 'Inbox' },
    ],
    workflow: ['Verifica configurazione', 'Scegli destinatario', 'Prepara testo', 'Invia e archivia esito'],
    links: [{ label: 'Messaggi', href: '/messaggi' }, { label: 'Agenda', href: '/agenda' }, { label: 'Impostazioni', href: '/impostazioni' }],
  },
  {
    id: 'incassi-pagamenti',
    routes: ['/incassi-pagamenti', '/impostazioni/pagamenti'],
    title: 'Incassi e Pagamenti',
    section: 'Incassi studio',
    subtitle: 'Controllo operativo per pagamenti, link parcella, stato incassi e bonifico.',
    lexContext: 'incassi-pagamenti',
    lexLabel: 'Lex collega pagamento, parcella, cliente e sollecito.',
    kpis: [
      { label: 'Canali', value: '4', note: 'Stripe, PayPal, Satispay, SumUp', tone: 'primary' },
      { label: 'Link', value: 'Parcelle', note: 'pagamento collegato al documento', tone: 'success' },
      { label: 'Controllo', value: 'Esiti', note: 'ricezione conferme pagamento', tone: 'warning' },
    ],
    cards: [
      { title: 'Impostazioni pagamenti', body: 'Configura canali, chiavi e preferenze operative per incassi digitali.', href: '/impostazioni?tab=pagamenti', action: 'Apri impostazioni', icon: 'settings', tone: 'primary', meta: 'Canali' },
      { title: 'Parcelle aperte', body: 'Apri parcelle da incassare e genera link pagamento.', href: '/fatturazione', action: 'Apri parcelle', icon: 'file', tone: 'success', meta: 'Incasso' },
      { title: 'Statistiche economiche', body: 'Controlla fatturato, incassato e andamento di periodo.', href: '/statistiche', action: 'Apri statistiche', icon: 'chart', tone: 'purple', meta: 'Indicatori' },
    ],
    workflow: ['Configura canali', 'Genera link parcella', 'Ricevi esito', 'Aggiorna stato incasso'],
    links: [{ label: 'Parcelle', href: '/fatturazione' }, { label: 'Clienti', href: '/clienti' }],
  },
  {
    id: 'backup',
    routes: ['/backup', '/impostazioni?tab=backup'],
    title: 'Backup',
    section: 'Continuita operativa',
    subtitle: 'Scheda operativa per copie, verifica, download protetto e pianificazione delle copie.',
    lexContext: 'backup',
    lexLabel: 'Lex legge stato copie, rischi e prossime verifiche consigliate.',
    kpis: [
      { label: 'Copie', value: 'Storico', note: 'archivio backup reale', tone: 'primary' },
      { label: 'Integrita', value: 'Verifica', note: 'controllo file e dimensioni', tone: 'success' },
      { label: 'Ripristino', value: 'Guidato', note: 'procedura assistita separata', tone: 'warning' },
    ],
    cards: [
      { title: 'Archivio backup', body: 'Apri lista copie, stato, dimensione, verifica e download.', href: '/impostazioni?tab=backup', action: 'Apri backup', icon: 'backup', tone: 'primary', meta: 'Impostazioni' },
      { title: 'Scheduler backup', body: 'Configura orario backup e promemoria automatici dello studio.', href: '/impostazioni#scheduler', action: 'Apri scheduler', icon: 'clock', tone: 'success', meta: 'Automazione' },
      { title: 'Database', body: 'Verifica archivi, copie e controlli sui dati.', href: '/admin/database', action: 'Apri database', icon: 'database', tone: 'purple', meta: 'Archivi' },
    ],
    workflow: ['Verifica ultimo backup', 'Controlla integrità', 'Scarica se necessario', 'Registra esito'],
    links: [{ label: 'Database', href: '/admin/database' }, { label: 'Registro Attività', href: '/audit' }],
  },
  {
    id: 'impostazioni-studio',
    routes: ['/impostazioni-studio', '/impostazioni'],
    title: 'Impostazioni Studio',
    section: 'Configurazione',
    subtitle: 'Indice operativo delle impostazioni sensibili: dati studio, comunicazioni, pagamenti, backup, calendari e assistente locale.',
    lexContext: 'impostazioni-studio',
    lexLabel: 'Lex legge configurazione e guida ai controlli senza esporre credenziali.',
    kpis: [
      { label: 'Schede', value: '11', note: 'studio, comunicazioni, pagamenti, backup, calendari e assistente', tone: 'primary' },
      { label: 'Locale', value: 'Signer', note: 'controlli sul PC dell’avvocato', tone: 'success' },
      { label: 'Sicurezza', value: 'Protetta', note: 'password e chiavi governate dalle policy esistenti', tone: 'warning' },
    ],
    cards: [
      { title: 'Dati studio', body: 'Apri dati anagrafici, fiscali e recapiti usati nei documenti.', href: '/impostazioni#dati-studio', action: 'Apri studio', icon: 'building', tone: 'primary', meta: 'Anagrafica' },
      { title: 'PEC e SMTP', body: 'Verifica PEC, Local Signer e invio messaggi senza mostrare password salvate.', href: '/impostazioni?tab=pec', action: 'Apri PEC', icon: 'mail', tone: 'success', meta: 'Posta' },
      { title: 'Firma digitale', body: 'Controlla canale firma e Local Signer per la firma dal PC dello studio.', href: '/impostazioni?tab=firma', action: 'Apri firma', icon: 'shield', tone: 'warning', meta: 'Locale' },
      { title: 'Assistente locale', body: "Configura Lex sul PC dello studio e aggiorna l'indice documenti.", href: '/impostazioni?tab=ai', action: 'Apri assistente', icon: 'spark', tone: 'purple', meta: 'Lex' },
      { title: 'WhatsApp', body: 'Gestisci canale, numeri e promemoria cliente collegati alle comunicazioni.', href: '/impostazioni?tab=whatsapp', action: 'Apri WhatsApp', icon: 'message', tone: 'success', meta: 'Canale' },
      { title: 'Scheduler', body: 'Controlla automazioni, backup e sincronizzazioni pianificate dello studio.', href: '/impostazioni?tab=scheduler', action: 'Apri scheduler', icon: 'clock', tone: 'neutral', meta: 'Automazioni' },
    ],
    workflow: ['Apri scheda corretta', 'Verifica canale locale', 'Salva configurazione', 'Esegui test operativo'],
    links: [{ label: 'Sincronizzazione Calendari', href: '/impostazioni/calendario' }, { label: 'Backup', href: '/impostazioni?tab=backup' }],
  },
  {
    id: 'sincronizzazione-calendari',
    routes: ['/sincronizzazione-calendari', '/impostazioni/calendario'],
    title: 'Sincronizzazione Calendari',
    section: 'Agenda esterna',
    subtitle: 'Agenda, scadenze e calendari esterni collegati nello stesso pannello Impostazioni.',
    lexContext: 'sincronizzazione-calendari',
    lexLabel: 'Lex legge profili calendario, scadenze e conflitti da presidiare.',
    kpis: [
      { label: 'Link', value: 'Agenda', note: 'agenda, scadenze e completo', tone: 'primary' },
      { label: 'Calendari', value: 'Esterni', note: 'agenda collegata allo studio', tone: 'success' },
      { label: 'Link', value: 'Protetti', note: 'rigenerabili quando serve', tone: 'warning' },
    ],
    cards: [
      { title: 'Calendari collegati', body: 'Apri link riservati, calendari esterni e sincronizzazione manuale.', href: '/impostazioni/calendario', action: 'Apri calendari', icon: 'calendar', tone: 'primary', meta: 'Impostazioni' },
      { title: 'Export agenda', body: 'Scarica il file calendario degli appuntamenti.', href: '/agenda/export.ics', action: 'Scarica agenda', icon: 'download', tone: 'success', meta: 'Calendario' },
      { title: 'Export scadenze', body: 'Scarica il file calendario delle scadenze.', href: '/scadenziario/export.ics', action: 'Scarica scadenze', icon: 'clock', tone: 'warning', meta: 'Calendario' },
    ],
    workflow: ['Verifica link', 'Copia nel calendario', 'Sincronizza calendario esterno', 'Controlla agenda e scadenziario'],
    links: [{ label: 'Agenda', href: '/agenda' }, { label: 'Scadenziario', href: '/scadenziario' }],
  },
  {
    id: 'amministrazione',
    routes: ['/amministrazione'],
    title: 'Amministrazione',
    section: 'Governance',
    subtitle: 'Indice operativo per utenti, permessi, registro, database, GDPR e controlli amministrativi.',
    lexContext: 'amministrazione',
    lexLabel: 'Lex legge ruoli, permessi, registro e rischi di governance.',
    kpis: [
      { label: 'Accesso', value: 'Permessi', note: 'ruoli e permessi controllati', tone: 'primary' },
      { label: 'Registro', value: 'Attivita', note: 'eventi e attività tracciate', tone: 'success' },
      { label: 'Compliance', value: 'GDPR', note: 'registro trattamenti e portabilità', tone: 'warning' },
    ],
    cards: [
      { title: 'Utenti', body: 'Gestisci operatori, ruoli, stato account e accessi.', href: '/utenti', action: 'Apri utenti', icon: 'users', tone: 'primary', meta: 'Permessi' },
      { title: 'Profili e permessi', body: 'Controlla matrice ruoli e override individuali.', href: '/profili', action: 'Apri permessi', icon: 'shield', tone: 'success', meta: 'Policy' },
      { title: 'Registro attività', body: 'Consulta eventi e controllo operativo.', href: '/audit', action: 'Apri registro', icon: 'clipboard', tone: 'warning', meta: 'Registro' },
      { title: 'Database e GDPR', body: 'Verifica storage e registro trattamenti.', href: '/admin/database', action: 'Apri database', icon: 'database', tone: 'purple', meta: 'Governance' },
    ],
    workflow: ['Controlla utenti', 'Verifica permessi', 'Leggi registro', 'Aggiorna conformità'],
    links: [{ label: 'Database', href: '/admin/database' }, { label: 'Registro GDPR', href: '/privacy/registro' }],
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
      { label: 'Ruoli', value: 'Permessi', note: 'amministratore, avvocato, collaboratore, segreteria', tone: 'success' },
      { label: 'Sicurezza', value: 'Registro', note: 'azioni sensibili tracciate', tone: 'warning' },
    ],
    cards: [
      { title: 'Lista utenti', body: 'Apri gestione completa utenti con stato e ruoli.', href: '/utenti', action: 'Apri lista', icon: 'users', tone: 'primary', meta: 'Archivio' },
      { title: 'Nuovo utente', body: 'Crea un operatore con ruolo e credenziali iniziali.', href: '/utenti/nuovo', action: 'Crea utente', icon: 'plus', tone: 'success', meta: 'Nuovo' },
      { title: 'Profili e permessi', body: 'Verifica matrice ruoli e regole operative.', href: '/profili', action: 'Apri profili', icon: 'shield', tone: 'warning', meta: 'Permessi' },
    ],
    workflow: ['Crea utente', 'Assegna ruolo', 'Verifica permessi', 'Controlla registro accessi'],
    links: [{ label: 'Amministrazione', href: '/utenti' }, { label: 'Registro Attività', href: '/audit' }],
  },
  {
    id: 'profili',
    routes: ['/profili'],
    title: 'Profili e Permessi',
    section: 'Permessi',
    subtitle: 'Matrice operativa per ruoli, permessi, override utente e controlli di autorizzazione.',
    lexContext: 'profili-permessi',
    lexLabel: 'Lex legge profili e segnala permessi critici da verificare.',
    kpis: [
      { label: 'Ruoli', value: 'Matrice', note: 'permessi per area', tone: 'primary' },
      { label: 'Override', value: 'Utente', note: 'extra e negati individuali', tone: 'warning' },
      { label: 'Regole', value: 'Registro', note: 'modifiche tracciate', tone: 'success' },
    ],
    cards: [
      { title: 'Matrice ruoli', body: 'Apri tabella profili e permessi per ruolo.', href: '/profili', action: 'Apri matrice', icon: 'table', tone: 'primary', meta: 'Permessi' },
      { title: 'Utenti', body: 'Seleziona utente e gestisci override autorizzativi.', href: '/utenti', action: 'Apri utenti', icon: 'users', tone: 'success', meta: 'Operatori' },
      { title: 'Registro permessi', body: 'Controlla cambi ruoli e modifiche autorizzative.', href: '/audit', action: 'Apri registro', icon: 'clipboard', tone: 'warning', meta: 'Traccia' },
    ],
    workflow: ['Leggi matrice', 'Verifica ruolo utente', 'Applica deroga motivata', 'Controlla registro'],
    links: [{ label: 'Utenti', href: '/utenti' }, { label: 'Amministrazione', href: '/utenti' }],
  },
  {
    id: 'registro-attivita',
    routes: ['/registro-attivita', '/audit', '/admin/osservabilita'],
    title: 'Registro Attività',
    section: 'Registro e osservabilità',
    subtitle: 'Registro operativo per eventi applicativi, utenti, esportazione e osservabilità amministrativa.',
    lexContext: 'registro-attivita',
    lexLabel: 'Lex legge eventi e aiuta a individuare anomalie operative.',
    kpis: [
      { label: 'Registro', value: 'Eventi', note: 'azioni sensibili e sicurezza', tone: 'primary' },
      { label: 'Export', value: 'CSV', note: 'estrazione registro', tone: 'success' },
      { label: 'Controlli', value: 'Admin', note: 'registro e stato servizi', tone: 'purple' },
    ],
    cards: [
      { title: 'Registro utenti', body: 'Apri registro con azioni e filtri.', href: '/audit', action: 'Apri registro', icon: 'clipboard', tone: 'primary', meta: 'Registro' },
      { title: 'Esporta registro', body: 'Scarica CSV per controlli interni e conformità.', href: '/audit/esporta.csv', action: 'Esporta CSV', icon: 'download', tone: 'success', meta: 'CSV' },
      { title: 'Controlli amministrativi', body: 'Apri stato servizi e registro amministrativo.', href: '/admin/osservabilita', action: 'Apri controlli', icon: 'chart', tone: 'purple', meta: 'Admin' },
    ],
    workflow: ['Filtra evento', 'Verifica utente e risorsa', 'Esporta se necessario', 'Azione correttiva'],
    links: [{ label: 'Utenti', href: '/utenti' }, { label: 'Database', href: '/admin/database' }],
  },
  {
    id: 'database',
    routes: ['/admin/database', '/database'],
    title: 'Database',
    section: 'Archivi e migrazioni',
    subtitle: 'Controllo operativo per stato archivi, copie, migrazione e consistenza dati.',
    lexContext: 'database',
    lexLabel: 'Lex legge stato storage, migrazioni e rischi di coerenza.',
    kpis: [
      { label: 'Archivi', value: 'Governati', note: 'dati e copie controllati', tone: 'primary' },
      { label: 'Migrazioni', value: 'Controllo', note: 'azioni tecniche esplicite', tone: 'warning' },
      { label: 'Export', value: 'Dati', note: 'copie e download protetto', tone: 'success' },
    ],
    cards: [
      { title: 'Stato database', body: 'Apri verifica archivi, statistiche e copie.', href: '/admin/database', action: 'Apri stato', icon: 'database', tone: 'primary', meta: 'Archivi' },
      { title: 'Backup', body: 'Controlla copie prima di ogni migrazione o ripristino.', href: '/impostazioni?tab=backup', action: 'Apri backup', icon: 'backup', tone: 'warning', meta: 'Protezione' },
      { title: 'Registro attività', body: 'Verifica registro delle operazioni delicate.', href: '/audit', action: 'Apri registro', icon: 'clipboard', tone: 'purple', meta: 'Registro' },
    ],
    workflow: ['Verifica stato', 'Crea backup', 'Esegui migrazione se richiesta', 'Controlla registro e salute'],
    links: [{ label: 'Backup', href: '/impostazioni?tab=backup' }, { label: 'Amministrazione', href: '/utenti' }],
  },
  {
    id: 'gdpr',
    routes: ['/registro-gdpr', '/privacy/registro', '/privacy/registro/nuovo'],
    title: 'Registro GDPR',
    section: 'Privacy e conformità',
    subtitle: 'Registro operativo per trattamenti, basi giuridiche, misure, portabilità e controlli privacy.',
    lexContext: 'gdpr',
    lexLabel: 'Lex legge trattamenti, dati personali e punti di verifica GDPR.',
    kpis: [
      { label: 'Trattamenti', value: 'Registro', note: 'attività privacy dello studio', tone: 'primary' },
      { label: 'Diritti', value: 'Portabilita', note: 'export dati cliente', tone: 'success' },
      { label: 'Registro', value: 'Privacy', note: 'eventi e prove di conformità', tone: 'warning' },
    ],
    cards: [
      { title: 'Registro trattamenti', body: 'Apri registro privacy e trattamenti gestiti.', href: '/privacy/registro', action: 'Apri registro', icon: 'shield', tone: 'primary', meta: 'GDPR' },
      { title: 'Nuovo trattamento', body: 'Registra finalità, base giuridica, dati e misure.', href: '/privacy/registro/nuovo', action: 'Nuovo trattamento', icon: 'plus', tone: 'success', meta: 'Compliance' },
      { title: 'Registro privacy', body: 'Esporta e verifica attività collegate a dati personali.', href: '/audit/esporta.csv', action: 'Esporta registro', icon: 'download', tone: 'warning', meta: 'CSV' },
    ],
    workflow: ['Censisci trattamento', 'Verifica base giuridica', 'Collega misure', 'Mantieni prova registrata'],
    links: [{ label: 'Clienti', href: '/clienti' }, { label: 'Registro Attività', href: '/audit' }],
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
