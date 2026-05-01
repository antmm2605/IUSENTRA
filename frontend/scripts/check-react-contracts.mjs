import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')

function read(path) {
  return readFileSync(resolve(root, path), 'utf8')
}

function assertContains(source, expected, label) {
  if (!source.includes(expected)) {
    throw new Error(`${label}: manca "${expected}"`)
  }
}

function assertNotContains(source, unexpected, label) {
  if (source.includes(unexpected)) {
    throw new Error(`${label}: contiene ancora "${unexpected}"`)
  }
}

const app = read('src/App.tsx')
const agenda = read('src/components/AgendaPage.tsx')
const agendaData = read('src/agendaData.ts')
const appointment = read('src/components/NuovoAppuntamentoPage.tsx')
const floatingLex = read('src/components/FloatingLex.tsx')
const search = read('src/components/RicercaStudioPage.tsx')
const searchData = read('src/searchData.ts')
const email = read('src/components/EmailPecPage.tsx')
const emailData = read('src/emailData.ts')
const messaggi = read('src/components/MessaggiPage.tsx')
const messaggiData = read('src/messaggiData.ts')
const fascicoli = read('src/components/FascicoliPage.tsx')
const fascicoliData = read('src/fascicoliData.ts')
const fascicoliBridge = read('../web/services/react_fascicoli_bridge.py')
const scadenziario = read('src/components/ScadenziarioPage.tsx')
const scadenziarioData = read('src/scadenziarioData.ts')
const nuovaScadenza = read('src/components/NuovaScadenzaPage.tsx')
const cartellaCliente = read('src/components/CartellaClientePage.tsx')
const cartellaClienteData = read('src/clientiCartellaData.ts')
const telematico = read('src/components/TelematicoPage.tsx')
const telematicoData = read('src/telematicoData.ts')
const telematicoSurface = read('src/components/TelematicoSurfacePage.tsx')
const telematicoSurfaceCss = read('src/components/TelematicoSurfacePage.css')
const studioModules = read('src/studioModuleData.ts')
const studioModulePage = read('src/components/StudioModulePage.tsx')
const studioModuleCss = read('src/components/StudioModulePage.css')
const css = read('src/index.css')
const reactShell = read('../web/templates/react_shell.html')

assertContains(app, '/global-search', 'nav ricerca studio')
assertContains(app, '/agenda', 'nav agenda')
assertContains(app, '/agenda/nuovo', 'nav nuovo appuntamento')
assertContains(app, '/workspace-intelligente', 'nav regia operativa')
assertContains(app, "/email/", 'nav email pec')
assertContains(app, "/messaggi", 'nav messaggi')
assertContains(app, "/messaggi/nuovo", 'nav nuovo messaggio')
assertContains(app, "/scadenziario", 'nav scadenziario')
assertContains(app, "/scadenziario/nuova", 'nav nuova scadenza')
assertContains(app, "/telematico", 'nav telematico')
assertContains(app, "CartellaClientePage", 'route cartella cliente')
assertContains(app, "ScadenziarioPage", 'route scadenziario')
assertContains(app, "NuovaScadenzaPage", 'route nuova scadenza')
assertContains(app, "TelematicoPage", 'route telematico')
assertContains(app, "StudioModulePage", 'route blocco finale studio')
assertContains(app, "isStudioModulePage?<StudioModulePage/>", 'render blocco finale studio')
assertContains(app, "findStudioModule(route)", 'contesto lex blocco finale')
assertContains(app, "isSearchPage?<RicercaStudioPage", 'route ricerca studio')
assertContains(app, "isNewAppointmentPage||isAppointmentEditPage?<NuovoAppuntamentoPage", 'route nuovo/modifica appuntamento')
assertContains(app, "isAgendaPage?<AgendaPage/>", 'route agenda')
assertContains(app, "isRegiaPage?<RegiaOperativaPage", 'route regia operativa')
assertContains(app, "isEmailPage?<EmailPecPage/>", 'route email pec')
assertContains(app, "isMessagesPage?<MessaggiPage/>", 'route messaggi')
assertContains(app, "isNewMessagePage?<NuovoMessaggioPage/>", 'route nuovo messaggio')
assertContains(app, "isClientFolderPage?<CartellaClientePage/>", 'route cartella cliente')
assertContains(app, "isNewDeadlinePage||isDeadlineEditPage?<NuovaScadenzaPage/>", 'route nuova/modifica scadenza')
assertContains(app, "isScadenziarioPage?<ScadenziarioPage/>", 'route scadenziario')
assertContains(app, "isTelematicoPage?<TelematicoPage/>", 'route telematico')
assertContains(app, 'AppErrorBoundary', 'barriera errore shell react')
assertContains(app, 'openSections[section.id] === true', 'nav sezioni chiuse')
assertContains(app, 'onCloseMobile', 'nav drawer mobile')
assertContains(app, 'mobileNavCollapsed', 'nav mobile comprimibile')
assertContains(app, 'iu-mobile__rail', 'nav mobile scorrevole')
assertContains(app, 'aria-controls="iu-mobile-links"', 'nav mobile accessibile')
assertNotContains(app, 'Lex - Assistente Legale', 'nav senza voce Lex separata')
assertNotContains(app, 'Centro operativo di oggi', 'panoramica separata')
assertNotContains(app, 'vista storica', 'copy app-v2 senza vista storica')

assertNotContains(search, 'mockResults', 'ricerca studio')
assertContains(searchData, '/api/global-search', 'api ricerca studio')
assertContains(searchData, 'reindexStudioSearch', 'reindicizzazione ricerca studio')

assertContains(agenda, 'AgendaPage', 'pagina agenda')
assertContains(agenda, 'FloatingLex', 'lex agenda')
assertContains(agenda, 'createAppointmentHref', 'slot agenda cliccabili')
assertContains(agenda, 'onCreateSlot', 'creazione da slot')
assertContains(agenda, 'iu-ag-slot', 'slot orari agenda')
assertContains(agenda, 'iu-ag-week--month', 'vista mese agenda')
assertContains(agenda, '/api/agenda/${encodeURIComponent(event.id)}/sposta', 'drag drop agenda persistente')
assertContains(agenda, 'messageReminderHref', 'automazioni agenda promemoria react')
assertContains(agenda, 'linkedDeadlineHref', 'automazioni agenda scadenza react')
assertContains(agenda, 'action="/timesheet/nuovo"', 'automazione timesheet operativa')
assertContains(agenda, 'iusentra:open-floating-lex', 'automazione lex in pagina')
assertNotContains(agenda, 'href="/timesheet"', 'agenda senza link timesheet legacy')
assertNotContains(agenda, 'href="/lex?context=agenda"', 'agenda senza link lex legacy')
assertContains(agendaData, '/api/v1/ui/agenda', 'api agenda react')
assertContains(agendaData, '/api/v1/agenda', 'api agenda operativo')
assertContains(agendaData, 'moveEventToDay', 'spostamento agenda')
assertContains(agendaData, 'moveEventToDateTime', 'spostamento agenda con orario')
assertContains(agendaData, 'agendaRange', 'range agenda per vista')

assertContains(appointment, 'formAction = isEditMode ? `/agenda/${encodeURIComponent(editId)}/modifica` : \'/agenda/nuovo\'', 'salvataggio appuntamento operativo')
assertContains(appointment, "params.get('ora')", 'precompilazione ora appuntamento')
assertContains(appointment, '/api/clienti', 'autocomplete clienti appuntamento')
assertContains(appointment, "autocomplete: '1'", 'autocomplete clienti payload minimale')
assertContains(appointment, 'safeJson', 'autocomplete clienti robusto su payload non JSON')
assertContains(appointment, 'normaliseClientSuggestion', 'normalizzazione risultati clienti')
assertContains(appointment, 'clientSuggestionsFromPayload', 'supporto wrapper api clienti')
assertContains(appointment, 'firstText', 'estrazione testo difensiva clienti')
assertContains(appointment, 'safeClientMatches', 'render autocomplete clienti sanitizzato')
assertContains(appointment, "Array.isArray(payload)", 'supporto array api clienti')
assertContains(appointment, "Array.isArray(payload.data)", 'supporto payload data api clienti')
assertContains(appointment, 'agendaItemsFromPayload', 'normalizzazione agenda per sovrapposizioni')
assertContains(appointment, 'const itemDataOra = asText(item.data_ora)', 'data agenda difensiva')
assertContains(appointment, 'Cliente senza nome', 'render cliente difensivo')
assertContains(appointment, '/api/agenda?da=', 'controllo sovrapposizioni appuntamento')
assertContains(appointment, 'toUpperCase', 'codice fiscale normalizzato')
assertContains(appointment, 'Contesto appuntamento pronto per Lex', 'contesto appuntamento per lex unico')
assertContains(floatingLex, 'IUSENTRA_LEX_CONTEXT', 'bridge contesto lex globale')
assertContains(floatingLex, 'iusentra:lex-context', 'evento contesto lex globale')
assertContains(floatingLex, 'return null', 'bridge react senza secondo widget lex')

assertContains(email, 'Casella PEC dello studio', 'pagina email pec')
assertContains(email, 'Cartelle PEC', 'tab cartelle pec')
assertContains(email, 'Apri casella', 'azione casella operativa')
assertContains(emailData, '/api/v1/ui/email', 'api email pec')
assertContains(emailData, 'operationalInbox', 'azione inbox operativa')
assertContains(messaggi, 'Nuovo messaggio', 'pagina messaggi')
assertContains(messaggi, 'Alternativa Web', 'canale WhatsApp alternativo')
assertContains(messaggiData, '/api/v1/ui/messaggi', 'api messaggi')
assertContains(messaggiData, 'sendEndpoint', 'endpoint invio operativo')
assertNotContains(email, 'Vista storica', 'email senza copy storico')
assertNotContains(messaggi, 'Vista storica', 'messaggi senza copy storico')
assertNotContains(messaggi, 'Fallback Web', 'messaggi senza fallback visibile')
assertContains(fascicoli, "rawPath.startsWith('/app-v2/fascicoli')", 'routing difensivo dettaglio fascicolo app-v2')
assertContains(fascicoli, "return { kind: 'detail', id: decodeURIComponent(parts[0] || '') }", 'routing dettaglio fascicolo')
assertContains(fascicoli, 'Quadro intelligente', 'quadro intelligente dettaglio fascicolo')
assertContains(fascicoli, 'FascicoloGuardrailsPanel', 'guardrail deposito form fascicolo')
assertContains(fascicoli, 'data.guardrails', 'payload guardrail form fascicolo')
assertContains(fascicoliData, 'FascicoloFormGuardrails', 'tipo guardrail form fascicolo')
assertContains(fascicoliData, 'guardrails: guardrails ?', 'normalizzazione guardrail form fascicolo')
assertContains(fascicoliData, 'statusLabel: string', 'stato documento fascicolo normalizzato')
assertContains(fascicoliData, 'statusTone: Tone', 'tono documento fascicolo normalizzato')
assertContains(fascicoli, 'doc.statusLabel', 'badge documento da payload backend')
assertNotContains(fascicoli, 'className="iu-fas-detail-section" open', 'sezioni dettaglio chiuse di default')
assertContains(fascicoliBridge, '"href": f"/fascicoli/{fid}"', 'link ufficiale dettaglio fascicolo')
assertContains(fascicoliBridge, '"editHref": f"/fascicoli/{fid}/modifica"', 'link ufficiale modifica fascicolo')
assertContains(fascicoliBridge, '_lead_lawyer_label', 'referente studio normalizzato')
assertContains(fascicoliBridge, '_next_hearing_value', 'udienza dettaglio normalizzata')
assertContains(fascicoliBridge, '_closure_date_value', 'chiusura dettaglio normalizzata')
assertContains(fascicoliBridge, '_italian_dates_in_text', 'normalizzazione date italiane nei testi fascicolo')
assertContains(fascicoliBridge, 'statusLabel": "Da acquisire"', 'documenti portale non scaricati marcati da acquisire')
assertContains(fascicoliBridge, '_new_fascicolo_guardrails', 'guardrail backend form fascicolo')
assertContains(fascicoliBridge, '_deposit_channel_for_type', 'mappatura canali deposito form fascicolo')
assertNotContains(fascicoliBridge, '/app-v2/fascicoli', 'bridge fascicoli senza URL tecnici app-v2')

assertContains(scadenziario, 'OperativeCards', 'card operative scadenziario')
assertContains(scadenziario, 'runBulkComplete', 'bulk completa scadenziario')
assertContains(scadenziario, 'routeDeadlineId', 'dettaglio scadenza react')
assertContains(scadenziario, 'iu-scad-focus-card', 'focus scadenza profonda')
assertContains(scadenziarioData, '/api/v1/ui/scadenziario', 'api scadenziario react')
assertContains(scadenziario, 'postDeadlineAction', 'azioni post scadenziario')
assertContains(nuovaScadenza, 'writeEndpoint = context.actions?.write_endpoint', 'salvataggio nuova/modifica scadenza operativo')
assertContains(nuovaScadenza, '/scadenziario/calcola-termine', 'calcolo termine operativo')
assertContains(cartellaCliente, 'CartellaClientePage', 'cartella cliente react')
assertContains(cartellaCliente, 'iu-cart-actions', 'card operative cartella cliente')
assertContains(cartellaCliente, 'data.actions.newDeadline', 'azione nuova scadenza cartella')
assertContains(cartellaCliente, 'data.actions.newMatter', 'azione nuovo fascicolo cartella')
assertContains(cartellaClienteData, '/api/v1/ui/clienti/${encodeURIComponent(idCliente)}/cartella', 'api cartella cliente')
assertContains(cartellaClienteData, 'operational_routes', 'scritture operative cartella cliente')
assertContains(telematico, 'Centro Servizi Telematici', 'pagina telematico react')
assertContains(telematico, 'FloatingLex', 'lex telematico')
assertContains(telematico, 'context="telematico"', 'contesto lex telematico')
assertContains(telematicoData, '/api/v1/ui/telematico', 'api telematico react')
assertContains(telematicoData, 'mock_fallback: false', 'contratto telematico senza mock')
assertContains(telematicoSurface, 'id="acquisizione-portale"', 'ancora acquisizione superfici telematiche')
assertContains(telematicoSurface, 'id="operazione-attiva"', 'pannello operativo superfici telematiche')
assertContains(telematicoSurface, 'navigateAction', 'click card superfici telematiche')
assertContains(telematicoSurface, 'isSameSurfaceAction', 'intercetto card stessa superficie telematica')
assertContains(telematicoSurface, 'window.history.pushState', 'URL coerente superfici telematiche')
assertContains(telematicoSurfaceCss, '.iu-tel-op-card.is-selected', 'card selezionata superfici telematiche')
assertContains(telematicoSurfaceCss, '.iu-tel-active-op', 'pannello operativo superfici telematiche')

for (const label of [
  'Studio',
  'Parcelle e Fatture',
  'Preventivi e Incarichi',
  'Compensi Forensi',
  'Redazione Atti',
  'Importa pratica da PST',
  'Statistiche',
  'Ricerca Legale',
  'Archivio Giurisprudenza',
  'Strumenti Forensi',
  'Strumenti Operativi',
  'Timesheet',
  'Cartelle Condivise',
  'Sito Studio',
  'Notifiche WhatsApp',
  'Incassi e Pagamenti',
  'Backup',
  'Impostazioni Studio',
  'Sincronizzazione Calendari',
  'Amministrazione',
  'Utenti',
  'Profili e Permessi',
  'Registro Attività',
  'Database',
  'Registro GDPR',
]) {
  assertContains(studioModules, label, `blocco finale ${label}`)
}
for (const route of [
  '/studio',
  '/fatturazione',
  '/fatturazione/nuova',
  '/preventivi',
  '/preventivi/nuovo',
  '/preventivi/wizard',
  '/preventivi/conferimento/nuovo',
  '/compensi-forensi',
  '/redazione-atti',
  '/template-atti/catalogo',
  '/template-atti/nuovo',
  '/portali/pst/acquisizione',
  '/statistiche',
  '/ricerca-legale',
  '/legal-intelligence/news',
  '/legal-intelligence/mediazione',
  '/giurisprudenza',
  '/giurisprudenza/nuova',
  '/strumenti-legali',
  '/strumenti-operativi',
  '/timesheet',
  '/cartelle-condivise',
  '/sito-studio',
  '/sito-studio/builder',
  '/sito-studio/contatti',
  '/notifiche-whatsapp',
  '/incassi-pagamenti',
  '/backup',
  '/impostazioni-studio',
  '/sincronizzazione-calendari',
  '/amministrazione',
  '/utenti',
  '/utenti/nuovo',
  '/profili',
  '/registro-attivita',
  '/audit',
  '/admin/osservabilita',
  '/admin/database',
  '/registro-gdpr',
  '/privacy/registro/nuovo',
]) {
  assertContains(studioModules, route, `route blocco finale ${route}`)
}
assertNotContains(studioModules, '_legacy=1', 'nessun rollback legacy visibile nel blocco React')
assertContains(studioModules, 'clean.length > best.length', 'matching moduli operativi annidati con rotta piu specifica')
assertNotContains(studioModules, "href: legacy('/fatturazione", 'nav reale fatturazione senza legacy')
assertNotContains(studioModules, "href: legacy('/preventivi", 'nav reale preventivi senza legacy')
assertNotContains(studioModules, "href: legacy('/utenti", 'nav reale utenti senza legacy')
assertNotContains(studioModules, "legacy(", 'nessun helper legacy nelle card React')
assertNotContains(studioModules, "/lex-operativo", 'nessun link a Lex operativo non migrato')
assertContains(studioModules, "href: '/portali/pst/acquisizione'", 'acquisizione PST guidata esplicita')
assertContains(studioModules, "href: '/portali/pst/acquisizione#checklist-operativa'", 'checklist PST guidata esplicita')
assertContains(studioModules, "href: '/impostazioni-studio#dati-studio'", 'impostazioni studio React ancorate')
assertContains(studioModules, "href: '/impostazioni-studio#pec-e-smtp'", 'impostazioni PEC React ancorate')
assertContains(studioModules, "href: '/impostazioni-studio#firma-digitale'", 'impostazioni firma React ancorate')
assertContains(studioModulePage, 'anchorForCard', 'ancore card operative blocco finale')
assertContains(studioModulePage, 'handleActivateCard', 'click card operative blocco finale')
assertContains(studioModulePage, 'isSameModuleHref', 'intercetto card stessa pagina blocco finale')
assertContains(studioModulePage, 'id="funzione-operativa"', 'pannello operativo blocco finale')
assertContains(studioModulePage, 'window.history.pushState', 'URL coerente dopo click blocco finale')
assertContains(studioModulePage, 'iusentra:open-floating-lex', 'lex contestuale blocco finale')
assertContains(studioModulePage, 'iusentra:lex-context', 'contesto lex blocco finale')
assertContains(studioModuleCss, '.iu-sm-cards', 'stili card operative blocco finale')
assertContains(studioModuleCss, '.iu-sm-card.is-selected', 'card selezionata blocco finale')
assertContains(studioModuleCss, '.iu-sm-focus', 'pannello operativo blocco finale')
assertContains(studioModuleCss, '.iu-sm-hero aside{\n    display:none;', 'lex nascosto tablet mobile blocco finale')
assertNotContains(studioModuleCss, 'clamp(', 'font blocco finale senza scala viewport')
assertNotContains(studioModuleCss, 'letter-spacing:-', 'tracking blocco finale non negativo')

assertContains(css, '.iu-search-page', 'stili ricerca studio')
assertContains(css, '.iu-agenda-page', 'stili agenda')
assertContains(css, '.iu-react-error', 'errore react')
assertContains(css, '.iu-ag-slot', 'stili slot agenda')
assertContains(css, '.iu-ag-week--month', 'stili vista mese agenda')
assertContains(css, '.iu-mobile__rail', 'stili nav mobile scorrevole')
assertContains(css, 'overflow-x:auto', 'nav mobile con scorrimento orizzontale')
assertContains(css, '.iu-mobile.is-collapsed', 'nav mobile richiudibile')
assertContains(css, '.iu-mobile__toggle', 'pulsante nav mobile apri chiudi')
assertContains(css, 'order:2', 'toggle nav mobile in fondo alla barra')
assertContains(css, '.iu-lex-float{display:none!important}', 'lex react nascosto su tablet e mobile')
assertContains(reactShell, 'components/pct_ai_widget.html', 'lex unico incluso nella shell react')
assertContains(reactShell, 'pct-lex-assistant.js', 'runtime lex unico nella shell react')
assertContains(css, '@media(max-width:760px)', 'responsive agenda')
assertContains(css, 'prefers-reduced-motion', 'motion agenda')

console.log('Contratti React verificati.')
