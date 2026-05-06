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

function assertNoBootstrapClass(source, label) {
  const classRegex = /className\s*=\s*["']([^"']+)["']/g
  for (const match of source.matchAll(classRegex)) {
    const tokens = match[1].split(/\s+/).filter(Boolean)
    const forbidden = tokens.find((token) => ['btn', 'card', 'container', 'row'].includes(token) || token.startsWith('col-'))
    if (forbidden) {
      throw new Error(`${label}: contiene classe Bootstrap vietata "${forbidden}"`)
    }
  }
}

function assertNoPasswordUseState(source, label) {
  if (/useState\s*(?:<[^>]*>)?\s*\([^)]*password/i.test(source)) {
    throw new Error(`${label}: non deve salvare password nello state React`)
  }
}

function assertNoFetchPost(source, label) {
  if (/fetch\s*\([^)]*method\s*:\s*['"]POST['"]/is.test(source) || /method\s*:\s*['"]POST['"][^)]*fetch\s*\(/is.test(source)) {
    throw new Error(`${label}: non deve usare fetch POST`)
  }
}

function assertNoFetchBlob(source, label) {
  for (const snippet of ['response.blob', 'URL.createObjectURL', 'new Blob']) {
    if (source.includes(snippet)) {
      throw new Error(`${label}: non deve gestire download con blob React`)
    }
  }
}

function assertNoFiscalLogic(source, label) {
  for (const pattern of [
    /ivaRate/i,
    /aliquotaIva/i,
    /cassaRate/i,
    /aliquotaCassa/i,
    /ritenutaRate/i,
    /calculateVat/i,
    /calculateIva/i,
    /calculateTax/i,
    /calculateTotal/i,
    /imponibile\s*\*/i,
    /totale\s*=\s*imponibile/i,
    /Math\.round/i,
    /\.toFixed\s*\(/i,
  ]) {
    if (pattern.test(source)) {
      throw new Error(`${label}: contiene logica fiscale canonica vietata`)
    }
  }
}

function assertNoClientStorage(source, label) {
  for (const storage of ['localStorage', 'sessionStorage']) {
    if (source.includes(storage)) {
      throw new Error(`${label}: non deve usare ${storage}`)
    }
  }
}

function assertNoSensitivePayloadWords(source, label) {
  for (const word of ['api_key', 'apikey', 'secret', 'password', 'smtp_password', 'pec_password', 'token', 'private_key', 'access_key', 'refresh_token', 'client_secret', 'bearer']) {
    if (new RegExp(word, 'i').test(source)) {
      throw new Error(`${label}: contiene parola riservata nel payload o nella UI: ${word}`)
    }
  }
}

function pythonTupleSource(source, name) {
  const match = source.match(new RegExp(`${name}\\s*=\\s*\\(([^]*?)\\)`, 'm'))
  return match ? match[1] : ''
}

const app = read('src/App.tsx')
const packageJson = JSON.parse(read('package.json'))
const dashboardData = read('src/data.ts')
const agenda = read('src/components/AgendaPage.tsx')
const agendaData = read('src/agendaData.ts')
const appointment = read('src/components/NuovoAppuntamentoPage.tsx')
const floatingLex = read('src/components/FloatingLex.tsx')
const widgetJs = read('../web/static/js/pct-lex-assistant.js')
const search = read('src/components/RicercaStudioPage.tsx')
const searchData = read('src/searchData.ts')
const email = read('src/components/EmailPecPage.tsx')
const emailData = read('src/emailData.ts')
const messaggi = read('src/components/MessaggiPage.tsx')
const messaggiData = read('src/messaggiData.ts')
const fascicoli = read('src/components/FascicoliPage.tsx')
const documentiAiPage = read('src/components/DocumentiAIPage.tsx')
const documentiAiData = read('src/documentiAiData.ts')
const documentUploadPanel = read('src/components/DocumentUploadPanel.tsx')
const documentListPanel = read('src/components/DocumentListPanel.tsx')
const documentDetailPanel = read('src/components/DocumentDetailPanel.tsx')
const documentTextPanel = read('src/components/DocumentTextPanel.tsx')
const documentSearchPanel = read('src/components/DocumentSearchPanel.tsx')
const documentStatusBadge = read('src/components/DocumentStatusBadge.tsx')
const documentAiEmptyState = read('src/components/DocumentAIEmptyState.tsx')
const documentEditor = read('src/components/DocumentEditorPage.tsx')
const documentEditorData = read('src/documentEditorData.ts')
const documentEditorBridge = read('../web/services/react_document_editor_bridge.py')
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
const adminDatabase = read('src/components/AdminDatabasePage.tsx')
const adminDatabaseData = read('src/adminDatabaseData.ts')
const adminDatabaseCss = read('src/components/AdminDatabasePage.css')
const adminDatabaseBridge = read('../web/services/react_admin_database_bridge.py')
const apiBridge = read('../web/blueprints/api_v1_react.py')
const statistiche = read('src/components/StatistichePage.tsx')
const statisticheData = read('src/statisticheData.ts')
const statisticheBridge = read('../web/services/react_statistiche_bridge.py')
const auditPage = read('src/components/AuditPage.tsx')
const auditData = read('src/auditData.ts')
const auditBridge = read('../web/services/react_audit_bridge.py')
const utentiPage = read('src/components/UtentiPage.tsx')
const utentiData = read('src/utentiData.ts')
const utentiBridge = read('../web/services/react_utenti_bridge.py')
const profiliPage = read('src/components/ProfiliPage.tsx')
const profiliData = read('src/profiliData.ts')
const profiliBridge = read('../web/services/react_profili_bridge.py')
const backupPage = read('src/components/BackupPage.tsx')
const backupData = read('src/backupData.ts')
const backupBridge = read('../web/services/react_backup_bridge.py')
const sitoStudioPage = read('src/components/SitoStudioPage.tsx')
const sitoStudioData = read('src/sitoStudioData.ts')
const sitoStudioBridge = read('../web/services/react_sito_studio_bridge.py')
const studioPage = read('src/components/StudioPage.tsx')
const studioData = read('src/studioData.ts')
const studioBridge = read('../web/services/react_studio_bridge.py')
const amministrazionePage = read('src/components/AmministrazionePage.tsx')
const amministrazioneData = read('src/amministrazioneData.ts')
const amministrazioneBridge = read('../web/services/react_amministrazione_bridge.py')
const fatturazionePage = read('src/components/FatturazionePage.tsx')
const fatturazioneData = read('src/fatturazioneData.ts')
const fatturazioneBridge = read('../web/services/react_fatturazione_bridge.py')
const incassiPagamentiPage = read('src/components/IncassiPagamentiPage.tsx')
const incassiPagamentiData = read('src/incassiPagamentiData.ts')
const incassiPagamentiBridge = read('../web/services/react_incassi_pagamenti_bridge.py')
const preventiviPage = read('src/components/PreventiviPage.tsx')
const preventiviData = read('src/preventiviData.ts')
const preventiviBridge = read('../web/services/react_preventivi_bridge.py')
const reactRouteGate = read('../web/bootstrap/react_route_gate.py')
const reactShellBlueprint = read('../web/blueprints/react_shell.py')
const timesheet = read('src/components/TimesheetPage.tsx')
const timesheetData = read('src/timesheetData.ts')
const timesheetBridge = read('../web/services/react_timesheet_bridge.py')
const cartelleCondivise = read('src/components/CartelleCondivisePage.tsx')
const cartelleCondiviseData = read('src/cartelleCondiviseData.ts')
const cartelleCondiviseBridge = read('../web/services/react_condivisioni_bridge.py')
const wizardPro = read('src/components/WizardProPage.tsx')
const wizardProStep = read('src/components/WizardProStepPage.tsx')
const wizardProComplete = read('src/components/WizardProCompletePage.tsx')
const wizardProShared = read('src/components/WizardProShared.tsx')
const wizardProData = read('src/wizardProData.ts')
const wizardProBridge = read('../web/services/react_wizard_pro_bridge.py')
const css = read('src/index.css')
const reactShell = read('../web/templates/react_shell.html')
const topbar = read('src/components/layout/TopBar.tsx')
const topbarSearch = read('src/components/layout/TopBarSearch.tsx')
const topbarCreate = read('src/components/layout/TopBarCreateMenu.tsx')
const topbarToday = read('src/components/layout/TopBarTodayMenu.tsx')
const topbarNotifications = read('src/components/layout/TopBarNotifications.tsx')
const topbarDeadlines = read('src/components/layout/TopBarDeadlines.tsx')
const topbarRecent = read('src/components/layout/TopBarRecentItems.tsx')
const topbarTimer = read('src/components/layout/TopBarTimeTracker.tsx')
const topbarApi = read('src/services/topbarApi.ts')
const topbarTypes = read('src/types/topbar.ts')
const routeManifest = JSON.parse(read('../tools/react-migration/route-manifest.json'))
const auditMigration = read('../scripts/react-migration/audit-react-migration.mjs')
const captureLegacyContracts = read('../scripts/react-migration/capture-legacy-contracts.py')
const checkRouteGate = read('../scripts/react-migration/check-route-gate.mjs')
const checkUiConsistency = read('../scripts/react-migration/check-ui-consistency.mjs')
const runSafeReactMigration = read('../scripts/react-migration/run-safe-react-migration.mjs')
const tranche2aGate = read('../scripts/react-migration/check-tranche-2a-gate.py')
const tranche3aGate = read('../scripts/react-migration/check-tranche-3a-gate.py')
const tranche4aGate = read('../scripts/react-migration/check-tranche-4a-gate.py')
const tranche4aSecrets = read('../scripts/react-migration/check-tranche-4a-secrets.mjs')
const tranche5aGate = read('../scripts/react-migration/check-tranche-5a-gate.py')
const tranche5aSecrets = read('../scripts/react-migration/check-tranche-5a-secrets.mjs')
const tranche6aGate = read('../scripts/react-migration/check-tranche-6a-gate.py')
const tranche6aSecrets = read('../scripts/react-migration/check-tranche-6a-secrets.mjs')
const tranche6aNoFiscalLogic = read('../scripts/react-migration/check-tranche-6a-no-fiscal-logic.mjs')
const tranche7aGate = read('../scripts/react-migration/check-tranche-7a-gate.py')
const tranche7aSecrets = read('../scripts/react-migration/check-tranche-7a-secrets.mjs')
const tranche7aNoCompensiLogic = read('../scripts/react-migration/check-tranche-7a-no-compensi-logic.mjs')
const tranche7aNoDocumentGeneration = read('../scripts/react-migration/check-tranche-7a-no-document-generation.mjs')
const uiAllowedClasses = read('../tools/react-migration/ui-allowed-classes.json')
const routeRiskRules = read('../tools/react-migration/route-risk-rules.json')
const uiPage = read('src/ui/Page.tsx')
const uiPageHeader = read('src/ui/PageHeader.tsx')
const uiButton = read('src/ui/Button.tsx')
const uiBadge = read('src/ui/Badge.tsx')
const uiPanel = read('src/ui/Panel.tsx')
const uiEmptyState = read('src/ui/EmptyState.tsx')
const uiLoadingState = read('src/ui/LoadingState.tsx')
const uiKpiCard = read('src/ui/KpiCard.tsx')
const uiDataTable = read('src/ui/DataTable.tsx')
const uiFormField = read('src/ui/FormField.tsx')
const uiActionBar = read('src/ui/ActionBar.tsx')
const uiTabs = read('src/ui/Tabs.tsx')
const uiLegacyPostForm = read('src/ui/LegacyPostForm.tsx')
const uiCss = read('src/ui/ui.css')
const uiTokens = read('src/theme/tokens.css')
const uiLayout = read('src/theme/layout.css')
const lexUiSources = [
  app,
  agenda,
  search,
  email,
  emailData,
  messaggi,
  fascicoli,
  documentiAiPage,
  documentiAiData,
  documentEditor,
  scadenziario,
  nuovaScadenza,
  telematico,
  telematicoSurface,
  timesheet,
  timesheetData,
  cartelleCondivise,
  cartelleCondiviseData,
  wizardPro,
  wizardProData,
  wizardProBridge,
  apiBridge,
].join('\n')
const legacyLexContextHref = '/lex' + '?context='
const legacyLexHrefAttribute = 'href=' + '"/lex'
const legacyAgendaLexHref = 'href=' + '"/lex' + '?context=agenda"'

const legacyOperationalTuple = pythonTupleSource(reactRouteGate, '_LEGACY_OPERATIONAL_PREFIXES')
const shellLegacyFirstTuple = pythonTupleSource(reactShellBlueprint, '_LEGACY_FIRST_PREFIXES')

for (const dependency of ['@mui/material', '@mui/icons-material', '@reduxjs/toolkit', 'redux', '@tanstack/react-query', 'zustand', 'react-router', 'react-router-dom']) {
  if (packageJson.dependencies?.[dependency] || packageJson.devDependencies?.[dependency]) {
    throw new Error(`dipendenze frontend: non deve comparire ${dependency}`)
  }
}

assertContains(auditMigration, 'route-inventory.json', 'script audit produce inventario route')
assertContains(auditMigration, '_REACT_PREFIXES', 'script audit legge prefissi React')
assertContains(auditMigration, '_LEGACY_OPERATIONAL_PREFIXES', 'script audit legge prefissi legacy')
assertContains(captureLegacyContracts, 'create_app', 'contract capture usa Flask test_client')
assertContains(captureLegacyContracts, '_legacy=1', 'contract capture usa fallback legacy')
assertContains(checkRouteGate, 'unlockFromGate=true richiede status react_full', 'route gate blocca unlock non completi')
assertContains(checkRouteGate, 'Tranche 4A', 'route gate limita gli sblocchi della Tranche 4A')
assertContains(checkRouteGate, 'Tranche 5A', 'route gate include gli sblocchi della Tranche 5A')
assertContains(checkRouteGate, 'Tranche 6A', 'route gate include gli sblocchi della Tranche 6A')
assertContains(checkRouteGate, 'Tranche 7A', 'route gate include gli sblocchi della Tranche 7A')
assertContains(checkUiConsistency, 'ui-allowed-classes.json', 'UI consistency usa policy classi')
assertContains(checkUiConsistency, 'href placeholder #', 'UI consistency blocca href placeholder')
assertContains(runSafeReactMigration, 'cleanRequired()', 'runner richiede working tree pulito')
assertContains(runSafeReactMigration, '--tranche=2a', 'runner supporta Tranche 2A')
assertContains(runSafeReactMigration, '--tranche=3a', 'runner supporta Tranche 3A')
assertContains(runSafeReactMigration, '--tranche=4a', 'runner supporta Tranche 4A')
assertContains(runSafeReactMigration, '--tranche=5a', 'runner supporta Tranche 5A')
assertContains(runSafeReactMigration, '--tranche=6a', 'runner supporta Tranche 6A')
assertContains(runSafeReactMigration, '--tranche=7a', 'runner supporta Tranche 7A')
assertContains(runSafeReactMigration, 'npm run test', 'runner esegue test frontend')
assertContains(runSafeReactMigration, 'npm run typecheck', 'runner esegue typecheck frontend')
assertContains(runSafeReactMigration, 'npm run build', 'runner esegue build frontend')
assertContains(tranche2aGate, '/statistiche', 'check Tranche 2A verifica statistiche')
assertContains(tranche2aGate, '/registro-attivita', 'check Tranche 2A verifica registro attivita')
assertContains(tranche3aGate, '/utenti/nuovo', 'check Tranche 3A verifica nuovo utente')
assertContains(tranche3aGate, '/backup', 'check Tranche 3A verifica backup legacy')
assertContains(tranche4aGate, '/sito-studio/contatti', 'check Tranche 4A verifica contatti Sito Studio')
assertContains(tranche4aGate, '/impostazioni?tab=firma', 'check Tranche 4A protegge firma digitale')
assertContains(tranche4aSecrets, 'react_sito_studio_bridge.py', 'check Tranche 4A anti-segreti scansiona bridge Sito Studio')
assertContains(tranche5aGate, '/amministrazione/qualunque', 'check Tranche 5A verifica subpath amministrazione')
assertContains(tranche5aSecrets, 'react_amministrazione_bridge.py', 'check Tranche 5A anti-segreti scansiona bridge amministrazione')
assertContains(tranche6aGate, '/fatturazione/qualunque/pdf', 'check Tranche 6A verifica PDF legacy')
assertContains(tranche6aSecrets, 'react_fatturazione_bridge.py', 'check Tranche 6A anti-segreti scansiona bridge fatturazione')
assertContains(tranche6aNoFiscalLogic, 'calculateIva', 'check Tranche 6A blocca calcolo fiscale frontend')
assertContains(tranche7aGate, '/preventivi/conferimento/nuovo', 'check Tranche 7A verifica nuovo conferimento')
assertContains(tranche7aSecrets, 'react_preventivi_bridge.py', 'check Tranche 7A anti-segreti scansiona bridge preventivi')
assertContains(tranche7aNoCompensiLogic, 'calculateCompenso', 'check Tranche 7A blocca logica compensi frontend')
assertContains(tranche7aNoDocumentGeneration, 'generatePdf', 'check Tranche 7A blocca generazione documenti')
assertContains(uiAllowedClasses, '"allowedPrefix": "iu-"', 'policy classi UI prefisso iu')
assertContains(routeRiskRules, '"critical"', 'regole rischio route critical')
if (routeManifest.policy?.currentReleaseUnlocksRoutes !== true) {
  throw new Error('route manifest: currentReleaseUnlocksRoutes deve essere true nelle tranche di promozione')
}
const allowedGovernedUnlocks = new Set(['/statistiche', '/audit', '/registro-attivita', '/utenti', '/profili', '/backup', '/sito-studio', '/sito-studio/contatti', '/studio', '/amministrazione', '/fatturazione', '/fatturazione/nuova', '/incassi-pagamenti', '/preventivi', '/preventivi/nuovo', '/preventivi/conferimento/nuovo'])
for (const entry of routeManifest.routes ?? []) {
  if (entry.unlockFromGate === true && !allowedGovernedUnlocks.has(entry.route)) {
    throw new Error(`route manifest: ${entry.route} non puo essere sbloccata nelle tranche governate`)
  }
  if (!entry.route || !entry.family || !entry.status || !entry.risk || !entry.targetComponent || !entry.targetData || !entry.targetBridge || !entry.legacyContract) {
    throw new Error(`route manifest: entry incompleta per ${entry.route || 'route senza nome'}`)
  }
}
for (const route of allowedGovernedUnlocks) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    throw new Error(`route manifest: ${route} deve essere react_full con unlockFromGate=true`)
  }
}
{
  const entry = (routeManifest.routes ?? []).find((item) => item.route === '/backup')
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    throw new Error('route manifest: /backup deve essere react_full con unlockFromGate=true')
  }
}
for (const route of ['/sito-studio', '/sito-studio/contatti']) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'react_full' || entry.unlockFromGate !== true) {
    throw new Error(`route manifest: ${route} deve essere react_full con unlockFromGate=true`)
  }
}
for (const route of ['/sito-studio/builder', '/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/sincronizzazione-calendari']) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    throw new Error(`route manifest: ${route} deve restare legacy_operational con unlockFromGate=false`)
  }
}
for (const route of ['/fatturazione/*', '/preventivi/*', '/preventivi/wizard', '/compensi-forensi', '/tariffario', '/impostazioni/pagamenti']) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    throw new Error(`route manifest: ${route} deve restare legacy_operational con unlockFromGate=false`)
  }
}
for (const route of ['/utenti', '/profili', '/audit', '/registro-attivita', '/studio', '/amministrazione', '/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/sincronizzazione-calendari', '/backup', '/sito-studio', '/sito-studio/contatti', '/sito-studio/builder', '/statistiche', '/fatturazione', '/fatturazione/nuova', '/fatturazione/*', '/incassi-pagamenti', '/preventivi', '/preventivi/nuovo', '/preventivi/conferimento/nuovo', '/preventivi/*', '/preventivi/wizard', '/compensi-forensi', '/tariffario', '/template-atti', '/redazione-atti', '/giurisprudenza', '/legal-intelligence', '/deposito/checklist', '/polisWeb', '/pdp', '/pat', '/sigit', '/sigp', '/portali/*']) {
  if (!(routeManifest.routes ?? []).some((entry) => entry.route === route)) {
    throw new Error(`route manifest: manca ${route}`)
  }
}
assertContains(uiPage, 'PageHeader', 'UI kit Page usa PageHeader')
assertContains(uiPageHeader, 'iu-page-heading', 'UI kit PageHeader presente')
assertContains(uiButton, 'iu-btn--${tone}', 'UI kit Button presente')
assertContains(uiBadge, 'iu-badge--', 'UI kit Badge presente')
assertContains(uiPanel, 'iu-panel__header', 'UI kit Panel presente')
assertContains(uiEmptyState, 'iu-empty-state', 'UI kit EmptyState presente')
assertContains(uiLoadingState, 'Caricamento in corso', 'UI kit LoadingState italiano')
assertContains(uiKpiCard, 'iu-kpi-card', 'UI kit KpiCard presente')
assertContains(uiDataTable, 'iu-data-table', 'UI kit DataTable presente')
assertContains(uiFormField, 'iu-form-field', 'UI kit FormField presente')
assertContains(uiActionBar, 'iu-action-bar', 'UI kit ActionBar presente')
assertContains(uiTabs, 'role="tablist"', 'UI kit Tabs accessibile')
assertContains(uiLegacyPostForm, 'document.querySelector(\'meta[name="csrf-token"]\')', 'LegacyPostForm legge CSRF da meta')
assertContains(uiLegacyPostForm, 'method={method.toLowerCase()}', 'LegacyPostForm usa form HTML standard')
assertNotContains(uiLegacyPostForm, 'fetch(', 'LegacyPostForm non usa fetch')
assertNotContains(uiLegacyPostForm, 'dangerouslySetInnerHTML', 'LegacyPostForm non usa HTML pericoloso')
assertContains(uiCss, '--iu-border', 'UI kit CSS usa token IUSENTRA')
assertContains(uiCss, 'prefers-reduced-motion', 'UI kit rispetta motion ridotta')
assertContains(uiTokens, 'var(--iu-bg-app)', 'theme tokens usa token esistenti')
assertContains(uiLayout, '.iu-layout-stack', 'theme layout presente')

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
assertContains(app, "TimesheetPage", 'route timesheet react')
assertContains(app, "CartelleCondivisePage", 'route cartelle condivise react')
assertContains(app, "WizardProStepPage", 'route step wizard pro react')
assertContains(app, "WizardProCompletePage", 'route completo wizard pro react')
assertContains(app, "TelematicoPage", 'route telematico')
assertContains(app, "StudioModulePage", 'route blocco finale studio')
assertContains(app, "isStudioModulePage?<StudioModulePage/>", 'render blocco finale studio')
assertContains(app, "AdminDatabasePage", 'route database amministrativo')
assertContains(app, "isAdminDatabasePage?<AdminDatabasePage/>", 'render database amministrativo')
assertContains(app, "StatistichePage", 'route statistiche react')
assertContains(app, "AuditPage", 'route audit react')
assertContains(app, "UtentiPage", 'route utenti react')
assertContains(app, "ProfiliPage", 'route profili react')
assertContains(app, "BackupPage", 'route backup react')
assertContains(app, "SitoStudioPage", 'route sito studio react')
assertContains(app, "StudioPage", 'route studio react')
assertContains(app, "AmministrazionePage", 'route amministrazione react')
assertContains(app, "FatturazionePage", 'route fatturazione react')
assertContains(app, "IncassiPagamentiPage", 'route incassi pagamenti react')
assertContains(app, "PreventiviPage", 'route preventivi react')
assertContains(app, "isStatistichePage", 'detection statistiche react')
assertContains(app, "isAuditPage", 'detection audit react')
assertContains(app, "isRegistroAttivitaPage", 'detection registro attivita react')
assertContains(app, "isUtentiPage", 'detection utenti react')
assertContains(app, "isProfiliPage", 'detection profili react')
assertContains(app, "isBackupPage", 'detection backup react')
assertContains(app, "isSitoStudioPage", 'detection sito studio react')
assertContains(app, "isStudioPage", 'detection studio react')
assertContains(app, "isAmministrazionePage", 'detection amministrazione react')
assertContains(app, "isFatturazionePage", 'detection fatturazione react')
assertContains(app, "isIncassiPagamentiPage", 'detection incassi pagamenti react')
assertContains(app, "isPreventiviPage", 'detection preventivi react')
assertContains(app, "isStatistichePage?<StatistichePage/>", 'render statistiche prima dello studio module')
assertContains(app, "isAuditPage||isRegistroAttivitaPage?<AuditPage/>", 'render audit e registro attivita')
assertContains(app, "isUtentiPage?<UtentiPage/>", 'render utenti prima dello studio module')
assertContains(app, "isProfiliPage?<ProfiliPage/>", 'render profili prima dello studio module')
assertContains(app, "isBackupPage?<BackupPage/>", 'render backup prima dello studio module')
assertContains(app, "isSitoStudioPage?<SitoStudioPage/>", 'render sito studio prima dello studio module')
assertContains(app, "isStudioPage?<StudioPage/>", 'render studio prima dello studio module')
assertContains(app, "isAmministrazionePage?<AmministrazionePage/>", 'render amministrazione prima dello studio module')
assertContains(app, "isFatturazionePage?<FatturazionePage/>", 'render fatturazione prima dello studio module')
assertContains(app, "isIncassiPagamentiPage?<IncassiPagamentiPage/>", 'render incassi prima dello studio module')
assertContains(app, "isPreventiviPage?<PreventiviPage/>", 'render preventivi prima dello studio module')
assertContains(statistiche, 'getStatistichePage', 'StatistichePage usa getStatistichePage')
assertContains(auditPage, 'getAuditPage', 'AuditPage usa getAuditPage')
assertContains(utentiPage, 'getUtentiPage', 'UtentiPage usa getUtentiPage')
assertContains(profiliPage, 'getProfiliPage', 'ProfiliPage usa getProfiliPage')
assertContains(backupPage, 'getBackupPage', 'BackupPage usa getBackupPage')
assertContains(sitoStudioPage, 'getSitoStudioPage', 'SitoStudioPage usa getSitoStudioPage')
assertContains(sitoStudioPage, 'getSitoStudioContattiPage', 'SitoStudioPage usa getSitoStudioContattiPage')
assertContains(studioPage, 'getStudioPage', 'StudioPage usa getStudioPage')
assertContains(amministrazionePage, 'getAmministrazionePage', 'AmministrazionePage usa getAmministrazionePage')
assertContains(fatturazionePage, 'getFatturazionePage', 'FatturazionePage usa getFatturazionePage')
assertContains(fatturazionePage, 'getNuovaFatturaPage', 'FatturazionePage usa getNuovaFatturaPage')
assertContains(incassiPagamentiPage, 'getIncassiPagamentiPage', 'IncassiPagamentiPage usa getIncassiPagamentiPage')
assertContains(preventiviPage, 'getPreventiviPage', 'PreventiviPage usa getPreventiviPage')
assertContains(preventiviPage, 'getNuovoPreventivoPage', 'PreventiviPage usa getNuovoPreventivoPage')
assertContains(preventiviPage, 'getNuovoConferimentoPage', 'PreventiviPage usa getNuovoConferimentoPage')
assertContains(utentiPage, 'LegacyPostForm', 'UtentiPage usa LegacyPostForm')
assertContains(profiliPage, 'LegacyPostForm', 'ProfiliPage usa LegacyPostForm per scritture legacy')
assertContains(backupPage, 'LegacyPostForm', 'BackupPage usa LegacyPostForm per azioni legacy')
assertContains(sitoStudioPage, 'LegacyPostForm', 'SitoStudioPage usa LegacyPostForm per azioni legacy')
assertContains(fatturazionePage, 'LegacyPostForm', 'FatturazionePage usa LegacyPostForm')
assertContains(preventiviPage, 'LegacyPostForm', 'PreventiviPage usa LegacyPostForm')
assertContains(statisticheData, '/api/v1/ui/statistiche', 'statisticheData usa endpoint statistiche')
assertContains(auditData, '/api/v1/ui/audit', 'auditData usa endpoint audit')
assertContains(auditData, '/api/v1/ui/registro-attivita', 'auditData usa endpoint registro attivita')
assertContains(utentiData, '/api/v1/ui/utenti', 'utentiData usa endpoint utenti')
assertContains(profiliData, '/api/v1/ui/profili', 'profiliData usa endpoint profili')
assertContains(backupData, '/api/v1/ui/backup', 'backupData usa endpoint backup')
assertContains(sitoStudioData, '/api/v1/ui/sito-studio', 'sitoStudioData usa endpoint sito studio')
assertContains(sitoStudioData, '/api/v1/ui/sito-studio/contatti', 'sitoStudioData usa endpoint contatti sito studio')
assertContains(studioData, '/api/v1/ui/studio', 'studioData usa endpoint studio')
assertContains(amministrazioneData, '/api/v1/ui/amministrazione', 'amministrazioneData usa endpoint amministrazione')
assertContains(fatturazioneData, '/api/v1/ui/fatturazione', 'fatturazioneData usa endpoint fatturazione')
assertContains(fatturazioneData, '/api/v1/ui/fatturazione/nuova', 'fatturazioneData usa endpoint nuova parcella')
assertContains(incassiPagamentiData, '/api/v1/ui/incassi-pagamenti', 'incassiPagamentiData usa endpoint incassi pagamenti')
assertContains(preventiviData, '/api/v1/ui/preventivi', 'preventiviData usa endpoint preventivi')
assertContains(preventiviData, '/api/v1/ui/preventivi/nuovo', 'preventiviData usa endpoint nuovo preventivo')
assertContains(preventiviData, '/api/v1/ui/preventivi/conferimento/nuovo', 'preventiviData usa endpoint nuovo conferimento')
assertContains(statisticheBridge, '"route_owner": "react_shell"', 'bridge statistiche route_owner react_shell')
assertContains(auditBridge, '"route_owner": "react_shell"', 'bridge audit route_owner react_shell')
assertContains(utentiBridge, '"route_owner": "react_shell"', 'bridge utenti route_owner react_shell')
assertContains(profiliBridge, '"route_owner": "react_shell"', 'bridge profili route_owner react_shell')
assertContains(backupBridge, '"route_owner": "react_shell"', 'bridge backup route_owner react_shell')
assertContains(sitoStudioBridge, '"route_owner": "react_shell"', 'bridge sito studio route_owner react_shell')
assertContains(fatturazioneBridge, '"route_owner": "react_shell"', 'bridge fatturazione route_owner react_shell')
assertContains(incassiPagamentiBridge, '"route_owner": "react_shell"', 'bridge incassi pagamenti route_owner react_shell')
assertContains(preventiviBridge, '"route_owner": "react_shell"', 'bridge preventivi route_owner react_shell')
assertContains(apiBridge, '@api_v1_react.get("/statistiche")', 'endpoint UI statistiche')
assertContains(apiBridge, '@api_v1_react.get("/audit")', 'endpoint UI audit')
assertContains(apiBridge, '@api_v1_react.get("/registro-attivita")', 'endpoint UI registro attivita')
assertContains(apiBridge, '@api_v1_react.get("/utenti")', 'endpoint UI utenti')
assertContains(apiBridge, '@api_v1_react.get("/profili")', 'endpoint UI profili')
assertContains(apiBridge, '@api_v1_react.get("/backup")', 'endpoint UI backup')
assertContains(apiBridge, '@api_v1_react.get("/sito-studio")', 'endpoint UI sito studio')
assertContains(apiBridge, '@api_v1_react.get("/sito-studio/contatti")', 'endpoint UI contatti sito studio')
assertContains(apiBridge, '@api_v1_react.get("/studio")', 'endpoint UI studio')
assertContains(apiBridge, '@api_v1_react.get("/amministrazione")', 'endpoint UI amministrazione')
assertContains(apiBridge, '@api_v1_react.get("/fatturazione")', 'endpoint UI fatturazione')
assertContains(apiBridge, '@api_v1_react.get("/fatturazione/nuova")', 'endpoint UI nuova parcella')
assertContains(apiBridge, '@api_v1_react.get("/incassi-pagamenti")', 'endpoint UI incassi pagamenti')
assertContains(apiBridge, '@api_v1_react.get("/preventivi")', 'endpoint UI preventivi')
assertContains(apiBridge, '@api_v1_react.get("/preventivi/nuovo")', 'endpoint UI nuovo preventivo')
assertContains(apiBridge, '@api_v1_react.get("/preventivi/conferimento/nuovo")', 'endpoint UI nuovo conferimento')
assertNotContains(legacyOperationalTuple, '"/statistiche"', 'gate legacy senza statistiche')
assertNotContains(legacyOperationalTuple, '"/audit"', 'gate legacy senza audit')
assertNotContains(legacyOperationalTuple, '"/registro-attivita"', 'gate legacy senza registro attivita')
assertNotContains(legacyOperationalTuple, '"/utenti"', 'gate legacy senza utenti')
assertNotContains(legacyOperationalTuple, '"/profili"', 'gate legacy senza profili')
assertNotContains(legacyOperationalTuple, '"/backup"', 'gate legacy senza backup')
assertNotContains(legacyOperationalTuple, '"/sito-studio"', 'gate legacy senza sito studio')
assertNotContains(legacyOperationalTuple, '"/studio"', 'gate legacy senza studio exact')
assertNotContains(legacyOperationalTuple, '"/amministrazione"', 'gate legacy senza amministrazione exact')
assertNotContains(legacyOperationalTuple, '"/fatturazione"', 'gate legacy senza fatturazione exact')
assertNotContains(legacyOperationalTuple, '"/incassi-pagamenti"', 'gate legacy senza incassi pagamenti exact')
assertNotContains(legacyOperationalTuple, '"/preventivi"', 'gate legacy senza preventivi exact')
assertContains(legacyOperationalTuple, '"/impostazioni"', 'gate legacy mantiene impostazioni')
assertContains(legacyOperationalTuple, '"/impostazioni-studio"', 'gate legacy mantiene impostazioni studio')
assertContains(legacyOperationalTuple, '"/sincronizzazione-calendari"', 'gate legacy mantiene sincronizzazione calendari')
assertContains(legacyOperationalTuple, '"/compensi-forensi"', 'gate legacy mantiene compensi forensi')
assertContains(legacyOperationalTuple, '"/tariffario"', 'gate legacy mantiene tariffario')
assertContains(reactRouteGate, 'lower.startswith("/utenti/") and lower != "/utenti/nuovo"', 'gate protegge nested utenti non migrati')
assertContains(reactRouteGate, 'lower.startswith("/profili/")', 'gate protegge nested profili non migrati')
assertContains(reactRouteGate, 'lower.startswith("/backup/")', 'gate protegge subpath backup legacy')
assertContains(reactRouteGate, 'lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}', 'gate protegge subpath sito studio non migrati')
assertContains(reactRouteGate, 'lower.startswith("/studio/")', 'gate protegge subpath studio legacy')
assertContains(reactRouteGate, 'lower.startswith("/amministrazione/")', 'gate protegge subpath amministrazione legacy')
assertContains(reactRouteGate, 'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"', 'gate protegge subpath fatturazione legacy')
assertContains(reactRouteGate, 'lower.startswith("/incassi-pagamenti/")', 'gate protegge subpath incassi legacy')
assertContains(reactRouteGate, 'lower == "/impostazioni/pagamenti" or lower.startswith("/impostazioni/pagamenti/")', 'gate protegge impostazioni pagamenti legacy')
assertContains(reactRouteGate, 'lower == "/impostazioni" or lower.startswith("/impostazioni/")', 'gate protegge impostazioni legacy')
assertContains(reactRouteGate, 'lower == "/impostazioni-studio" or lower.startswith("/impostazioni-studio/")', 'gate protegge impostazioni studio legacy')
assertContains(reactRouteGate, 'lower == "/sincronizzazione-calendari" or lower.startswith("/sincronizzazione-calendari/")', 'gate protegge sincronizzazione calendari legacy')
assertContains(reactRouteGate, 'lower.startswith("/preventivi/") and lower not in {', 'gate protegge nested preventivi non migrati')
assertContains(reactRouteGate, '"/preventivi/nuovo"', 'gate consente nuovo preventivo')
assertContains(reactRouteGate, '"/preventivi/conferimento/nuovo"', 'gate consente nuovo conferimento')
assertContains(reactRouteGate, 'lower == "/compensi-forensi" or lower.startswith("/compensi-forensi/")', 'gate protegge compensi forensi')
assertContains(reactRouteGate, 'lower == "/tariffario" or lower.startswith("/tariffario/")', 'gate protegge tariffario')
assertNotContains(shellLegacyFirstTuple, '"/statistiche"', 'shell legacy-first senza statistiche')
assertNotContains(shellLegacyFirstTuple, '"/audit"', 'shell legacy-first senza audit')
assertNotContains(shellLegacyFirstTuple, '"/registro-attivita"', 'shell legacy-first senza registro attivita')
assertNotContains(shellLegacyFirstTuple, '"/utenti"', 'shell legacy-first senza utenti')
assertNotContains(shellLegacyFirstTuple, '"/profili"', 'shell legacy-first senza profili')
assertNotContains(shellLegacyFirstTuple, '"/backup"', 'shell legacy-first senza backup')
assertNotContains(shellLegacyFirstTuple, '"/sito-studio"', 'shell legacy-first senza sito studio')
assertNotContains(shellLegacyFirstTuple, '"/studio"', 'shell legacy-first senza studio exact')
assertNotContains(shellLegacyFirstTuple, '"/amministrazione"', 'shell legacy-first senza amministrazione exact')
assertNotContains(shellLegacyFirstTuple, '"/fatturazione"', 'shell legacy-first senza fatturazione exact')
assertNotContains(shellLegacyFirstTuple, '"/incassi-pagamenti"', 'shell legacy-first senza incassi exact')
assertNotContains(shellLegacyFirstTuple, '"/preventivi"', 'shell legacy-first senza preventivi exact')
assertContains(shellLegacyFirstTuple, '"/impostazioni"', 'shell legacy-first mantiene impostazioni')
assertContains(shellLegacyFirstTuple, '"/impostazioni-studio"', 'shell legacy-first mantiene impostazioni studio')
assertContains(shellLegacyFirstTuple, '"/sincronizzazione-calendari"', 'shell legacy-first mantiene sincronizzazione calendari')
assertContains(shellLegacyFirstTuple, '"/compensi-forensi"', 'shell legacy-first mantiene compensi')
assertContains(shellLegacyFirstTuple, '"/tariffario"', 'shell legacy-first mantiene tariffario')
assertContains(reactShellBlueprint, 'lower.startswith("/utenti/") and lower != "/utenti/nuovo"', 'shell protegge nested utenti non migrati')
assertContains(reactShellBlueprint, 'lower.startswith("/profili/")', 'shell protegge nested profili non migrati')
assertContains(reactShellBlueprint, 'lower.startswith("/backup/")', 'shell protegge subpath backup legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/sito-studio/") and lower not in {"/sito-studio/contatti"}', 'shell protegge subpath sito studio non migrati')
assertContains(reactShellBlueprint, 'lower.startswith("/studio/")', 'shell protegge subpath studio legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/amministrazione/")', 'shell protegge subpath amministrazione legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/fatturazione/") and lower != "/fatturazione/nuova"', 'shell protegge subpath fatturazione legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/incassi-pagamenti/")', 'shell protegge subpath incassi legacy')
assertContains(reactShellBlueprint, 'lower == "/impostazioni/pagamenti" or lower.startswith("/impostazioni/pagamenti/")', 'shell protegge impostazioni pagamenti legacy')
assertContains(reactShellBlueprint, 'lower == "/impostazioni" or lower.startswith("/impostazioni/")', 'shell protegge impostazioni legacy')
assertContains(reactShellBlueprint, 'lower == "/impostazioni-studio" or lower.startswith("/impostazioni-studio/")', 'shell protegge impostazioni studio legacy')
assertContains(reactShellBlueprint, 'lower == "/sincronizzazione-calendari" or lower.startswith("/sincronizzazione-calendari/")', 'shell protegge sincronizzazione calendari legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/preventivi/") and lower not in {', 'shell protegge nested preventivi non migrati')
assertContains(reactShellBlueprint, 'lower == "/compensi-forensi" or lower.startswith("/compensi-forensi/")', 'shell protegge compensi forensi')
assertContains(reactShellBlueprint, 'lower == "/tariffario" or lower.startswith("/tariffario/")', 'shell protegge tariffario')
for (const [label, source] of [
  ['StatistichePage', statistiche],
  ['AuditPage', auditPage],
  ['UtentiPage', utentiPage],
  ['ProfiliPage', profiliPage],
  ['BackupPage', backupPage],
  ['SitoStudioPage', sitoStudioPage],
  ['StudioPage', studioPage],
  ['AmministrazionePage', amministrazionePage],
  ['FatturazionePage', fatturazionePage],
  ['IncassiPagamentiPage', incassiPagamentiPage],
  ['PreventiviPage', preventiviPage],
]) {
  assertNoBootstrapClass(source, `${label} senza classi Bootstrap`)
  assertNotContains(source, 'href="#"', `${label} senza href placeholder`)
  assertNotContains(source, 'mockResults', `${label} senza mockResults`)
  assertNotContains(source, 'mock_fallback: true', `${label} senza mock fallback true`)
  assertNoFetchPost(source, `${label} senza fetch POST`)
  assertNoPasswordUseState(source, `${label} senza password in useState`)
  assertNoClientStorage(source, `${label} senza storage client per dati amministrativi`)
}
for (const [label, source] of [
  ['statisticheData', statisticheData],
  ['auditData', auditData],
  ['utentiData', utentiData],
  ['profiliData', profiliData],
  ['backupData', backupData],
  ['sitoStudioData', sitoStudioData],
  ['studioData', studioData],
  ['amministrazioneData', amministrazioneData],
  ['react_statistiche_bridge', statisticheBridge],
  ['react_audit_bridge', auditBridge],
  ['react_utenti_bridge', utentiBridge],
  ['react_profili_bridge', profiliBridge],
  ['react_backup_bridge', backupBridge],
  ['react_sito_studio_bridge', sitoStudioBridge],
  ['react_studio_bridge', studioBridge],
  ['react_amministrazione_bridge', amministrazioneBridge],
  ['react_fatturazione_bridge', fatturazioneBridge],
  ['react_incassi_pagamenti_bridge', incassiPagamentiBridge],
  ['react_preventivi_bridge', preventiviBridge],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
]) {
  assertNotContains(source, 'mockResults', `${label} senza mockResults`)
  assertNotContains(source, 'mock_fallback: true', `${label} senza mock fallback true`)
}
assertNoFetchPost(utentiData, 'utentiData senza fetch POST')
assertNoFetchPost(profiliData, 'profiliData senza fetch POST')
assertNoFetchPost(backupData, 'backupData senza fetch POST')
assertNoFetchPost(sitoStudioData, 'sitoStudioData senza fetch POST')
assertNoFetchPost(studioData, 'studioData senza fetch POST')
assertNoFetchPost(amministrazioneData, 'amministrazioneData senza fetch POST')
assertNoFetchPost(fatturazionePage, 'FatturazionePage senza fetch POST')
assertNoFetchPost(incassiPagamentiPage, 'IncassiPagamentiPage senza fetch POST')
assertNoFetchPost(preventiviPage, 'PreventiviPage senza fetch POST')
assertNoFetchPost(fatturazioneData, 'fatturazioneData senza fetch POST')
assertNoFetchPost(incassiPagamentiData, 'incassiPagamentiData senza fetch POST')
assertNoFetchPost(preventiviData, 'preventiviData senza fetch POST')
for (const [label, source] of [
  ['react_backup_bridge', backupBridge],
  ['react_sito_studio_bridge', sitoStudioBridge],
  ['react_studio_bridge', studioBridge],
  ['react_amministrazione_bridge', amministrazioneBridge],
  ['react_fatturazione_bridge', fatturazioneBridge],
  ['react_incassi_pagamenti_bridge', incassiPagamentiBridge],
  ['react_preventivi_bridge', preventiviBridge],
  ['backupData', backupData],
  ['sitoStudioData', sitoStudioData],
  ['studioData', studioData],
  ['amministrazioneData', amministrazioneData],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
  ['BackupPage', backupPage],
  ['SitoStudioPage', sitoStudioPage],
  ['StudioPage', studioPage],
  ['AmministrazionePage', amministrazionePage],
  ['FatturazionePage', fatturazionePage],
  ['IncassiPagamentiPage', incassiPagamentiPage],
  ['PreventiviPage', preventiviPage],
]) {
  assertNoSensitivePayloadWords(source, `${label} senza campi riservati`)
  assertNoClientStorage(source, `${label} senza storage client`)
}
for (const source of [backupPage, sitoStudioPage, backupData, sitoStudioData]) {
  assertNotContains(source, 'URL.createObjectURL', 'nessun download gestito con blob React')
  assertNotContains(source, 'response.blob', 'nessun download gestito con blob React')
  assertNotContains(source, 'new Blob', 'nessun download gestito con blob React')
}
for (const [label, source] of [
  ['FatturazionePage', fatturazionePage],
  ['IncassiPagamentiPage', incassiPagamentiPage],
  ['PreventiviPage', preventiviPage],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
]) {
  assertNoFetchBlob(source, `${label} senza fetch blob`)
  assertNoFiscalLogic(source, `${label} senza calcolo fiscale canonico`)
}
for (const [label, source] of [
  ['PreventiviPage', preventiviPage],
  ['preventiviData', preventiviData],
]) {
  assertNotContains(source, 'calculate', `${label} senza calculate frontend`)
  assertNotContains(source, 'DM55', `${label} senza DM55 frontend`)
  assertNotContains(source, 'dm55', `${label} senza dm55 frontend`)
  assertNotContains(source, 'Math.round', `${label} senza arrotondamenti economici`)
  assertNotContains(source, '.toFixed(', `${label} senza formattazioni economiche calcolate`)
}
assertNotContains(utentiBridge, 'password_hash', 'bridge utenti non serializza hash password')
assertNotContains(utentiBridge, 'totp_secret', 'bridge utenti non serializza segreti TOTP')
assertNotContains(utentiBridge, 'reset_token', 'bridge utenti non serializza reset token')
assertContains(app, "DocumentEditorPage", 'route editor documento react')
assertContains(app, "isDocumentEditorPage?<DocumentEditorPage/>", 'render editor documento react')
assertContains(app, "/^\\/fascicoli\\/[^/]+\\/documenti\\/[^/]+\\/editor$/.test(routeKey)", 'match route profonda editor documento')
assertNotContains(fascicoli, 'DocumentiAIPage', 'Documenti AI non visibile come archivio separato nel fascicolo')
assertNotContains(fascicoli, 'id="documenti-ai"', 'nessuna ancora Documenti AI nel dettaglio fascicolo')
assertNotContains(fascicoli, 'href="#documenti-ai"', 'nessuna CTA standard verso Documenti AI')
assertContains(fascicoli, 'Indicizzazione Lex', 'stato indicizzazione Lex integrato nei documenti fascicolo')
assertContains(fascicoli, 'Lex può leggere i documenti del fascicolo.', 'messaggio indice Lex pronto')
assertContains(fascicoli, 'refreshLexIndex', 'azione aggiorna indice Lex')
assertContains(fascicoli, 'retryLexIndexErrors', 'azione riprova errori indice Lex')
assertContains(fascicoliData, 'lexIndexing', 'payload indicizzazione Lex nel dettaglio fascicolo')
assertContains(fascicoliBridge, '"lex_indexing"', 'bridge fascicolo espone indicizzazione Lex')
assertContains(documentiAiPage, 'react_operational_partial', 'stato operativo Documenti AI')
assertContains(documentiAiPage, 'fetchDocumentAIList', 'pagina Documenti AI usa API reali')
assertContains(documentiAiData, '/api/v1/ui/fascicoli/', 'client API Documenti AI')
assertContains(documentiAiData, 'mock_fallback: false', 'contratto mock_fallback=false Documenti AI')
assertContains(documentUploadPanel, 'PDF, DOCX o DOC', 'upload formati Documenti AI')
assertContains(documentListPanel, 'SHA-256', 'lista mostra hash Documenti AI')
assertContains(documentDetailPanel, 'Versioni', 'dettaglio versioni Documenti AI')
assertContains(documentTextPanel, 'Testo estratto', 'testo estratto Documenti AI')
assertContains(documentSearchPanel, 'Nessun risultato nel documento selezionato.', 'empty state ricerca Documenti AI')
assertContains(documentStatusBadge, 'Pronto', 'badge stato Documenti AI')
assertContains(documentAiEmptyState, 'Nessun documento AI nel fascicolo', 'empty state Documenti AI')
for (const [label, source] of [
  ['DocumentiAIPage', documentiAiPage],
  ['DocumentUploadPanel', documentUploadPanel],
  ['DocumentListPanel', documentListPanel],
  ['DocumentDetailPanel', documentDetailPanel],
  ['DocumentTextPanel', documentTextPanel],
  ['DocumentSearchPanel', documentSearchPanel],
  ['DocumentAIEmptyState', documentAiEmptyState],
]) {
  assertNotContains(source, 'href="#"', `${label} senza href placeholder`)
}
assertContains(app, "readShellBootstrap", 'bootstrap profilo reale shell react')
assertContains(app, "profile.displayName", 'nome profilo reale in sidebar react')
assertContains(app, 'method="post" action={logoutAction}', 'logout react via POST reale')
assertContains(app, "findStudioModule(route)", 'contesto lex blocco finale')
assertContains(app, "const OPEN_LEX_WIDGET_HREF = '#lex'", 'cta lex usa widget flottante')
assertNotContains(app, legacyLexContextHref, 'shell react senza link funzionali /lex')
assertNotContains(app, legacyLexHrefAttribute, 'shell react senza pagina lex standalone')
assertNotContains(lexUiSources, legacyLexContextHref, 'sorgenti react/bridge senza pagina lex standalone')
assertNotContains(lexUiSources, legacyLexHrefAttribute, 'sorgenti react/bridge senza href lex standalone')
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
assertContains(app, "isTimesheetPage?<TimesheetPage/>", 'render timesheet react')
assertContains(app, "isCartelleCondivisePage?<CartelleCondivisePage/>", 'render cartelle condivise react')
assertContains(app, "isWizardProStep?<WizardProStepPage/>", 'render step wizard pro react')
assertContains(app, "isWizardProComplete?<WizardProCompletePage/>", 'render completo wizard pro react')
assertContains(app, "isWizardProDashboard?<WizardProPage/>", 'render dashboard wizard pro react')
assertContains(app, "isTelematicoPage?<TelematicoPage/>", 'route telematico')
assertContains(app, "preparazione-udienza-briefing", 'contesto lex wizard briefing')
assertContains(app, "preparazione-udienza-documenti", 'contesto lex wizard documenti')
assertContains(app, "preparazione-udienza-strategia", 'contesto lex wizard strategia')
assertContains(app, "preparazione-udienza-precheck", 'contesto lex wizard precheck')
assertContains(app, "preparazione-udienza-esito", 'contesto lex wizard esito')
assertContains(app, "preparazione-udienza-riepilogo", 'contesto lex wizard riepilogo')
assertContains(app, "route === '/admin/database'", 'contesto lex database amministrativo')
assertContains(app, 'AppErrorBoundary', 'barriera errore shell react')
assertContains(app, 'openSections[section.id] === true', 'nav sezioni chiuse')
assertContains(app, 'onCloseMobile', 'nav drawer mobile')
assertContains(app, 'mobileNavCollapsed', 'nav mobile comprimibile')
assertContains(app, 'iu-mobile__rail', 'nav mobile scorrevole')
assertContains(app, 'aria-controls="iu-mobile-links"', 'nav mobile accessibile')
assertNotContains(app, 'Lex - Assistente Legale', 'nav senza voce Lex separata')
assertNotContains(app, 'Centro operativo di oggi', 'panoramica separata')
assertNotContains(app, 'vista storica', 'copy app-v2 senza vista storica')
assertNotContains(app, 'Avv. Roberto Rossi', 'profilo shell senza dati inventati')
assertNotContains(app, '<span>8</span>', 'badge notifiche senza conteggio inventato')
assertNotContains(app, '2026/004 - N.RG', 'recenti senza fascicolo inventato')
assertContains(app, "TopBar onOpenMenu", 'top bar operativa modulare')
assertNotContains(app, 'Cerca fascicolo, cliente, pratica, scadenza...', 'top bar senza placeholder legacy')
assertContains(dashboardData, 'getDashboard(options: { refresh?: boolean } = {})', 'dashboard refresh esplicito')
assertContains(dashboardData, "query.set('refresh', '1')", 'dashboard usa refresh=1 solo esplicito')
assertContains(dashboardData, 'syncDashboardMailboxes', 'sync mailbox panoramica non bloccante')
assertContains(app, 'syncDashboardMailboxes()', 'panoramica avvia sync mailbox dopo primo payload')
assertContains(app, "getDashboard({refresh:true})", 'panoramica ricarica cache dopo sync')
assertNotContains(dashboardData, "query.set('_ts', String(Date.now()))", 'dashboard senza timestamp anti-cache')
assertNotContains(dashboardData, "cache:'no-store'", 'dashboard senza no-store fetch compatto')
assertNotContains(dashboardData, "cache: 'no-store'", 'dashboard senza no-store fetch')

assertContains(topbar, 'TopBarSearch', 'top bar ricerca modulare')
assertContains(topbar, 'TopBarCreateMenu', 'top bar menu nuovo')
assertContains(topbar, 'TopBarTodayMenu', 'top bar oggi')
assertContains(topbar, 'TopBarNotifications', 'top bar notifiche')
assertContains(topbar, 'TopBarDeadlines', 'top bar scadenze')
assertContains(topbar, 'TopBarRecentItems', 'top bar recenti')
assertContains(topbar, 'TopBarTimeTracker', 'top bar timer')
assertContains(topbarSearch, 'isCommandK', 'shortcut Ctrl K / Cmd K')
assertContains(topbarSearch, 'role="dialog"', 'palette ricerca accessibile')
assertContains(topbarSearch, 'role="listbox"', 'risultati ricerca tastiera')
assertContains(topbarSearch, "event.key === 'ArrowDown'", 'navigazione frecce ricerca')
assertContains(topbarSearch, "event.key === 'Enter'", 'enter apre risultato')
assertContains(topbarCreate, "Nuovo fascicolo", 'azione nuovo fascicolo')
assertContains(topbarCreate, "Nuovo cliente", 'azione nuovo cliente')
assertContains(topbarCreate, "Nuova scadenza", 'azione nuova scadenza')
assertContains(topbarCreate, "Nuova udienza", 'azione nuova udienza')
assertContains(topbarCreate, "Nuova attivita", 'azione nuova attivita')
assertContains(topbarCreate, "Nuovo documento", 'azione nuovo documento')
assertContains(topbarCreate, "Nuova fattura", 'azione nuova fattura')
assertContains(topbarToday, 'useTodaySummary', 'hook oggi')
assertContains(topbarApi, 'markNotificationRead', 'mark notification read')
assertContains(topbarNotifications, 'markAllRead', 'mark all notifications read')
assertContains(topbarDeadlines, 'useQuickDeadlines', 'hook scadenze rapide')
assertContains(topbarRecent, 'useRecentItems', 'hook recenti')
assertContains(topbarTimer, 'useTimeTracker', 'hook timer top bar')
assertContains(topbarTimer, 'Avvia attivita', 'timer start UI')
assertContains(topbarTimer, 'Pausa', 'timer pausa UI')
assertContains(topbarTimer, 'Riprendi', 'timer resume UI')
assertContains(topbarTimer, 'Stop', 'timer stop UI')
assertContains(topbarApi, '/api/search/global', 'api ricerca top bar')
assertContains(topbarApi, '/api/dashboard/today', 'api oggi top bar')
assertContains(topbarApi, '/api/notifications', 'api notifiche top bar')
assertContains(topbarApi, '/api/deadlines/quick-summary', 'api scadenze top bar')
assertContains(topbarApi, '/api/recent', 'api recenti top bar')
assertContains(topbarApi, '/api/time-tracking/active', 'api timer top bar')
assertContains(topbarTypes, 'GlobalSearchResult', 'tipi ricerca top bar')
assertContains(topbarTypes, 'TimeTrackingTimer', 'tipi timer top bar')

assertNotContains(search, 'mockResults', 'ricerca studio')
assertContains(searchData, '/api/global-search', 'api ricerca studio')
assertContains(searchData, '/api/global-search/stats', 'stats ricerca studio endpoint leggero')
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
assertNotContains(agenda, legacyAgendaLexHref, 'agenda senza link lex legacy')
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
assertContains(widgetJs, 'function buildChatRequestPayload(text)', 'payload chat lex centralizzato')
assertContains(widgetJs, "fetch(widget.dataset.chatUrl || '/api/assistente/chat'", 'widget invia alla rotta chat canonica')
assertContains(widgetJs, 'mode: mode', 'widget conserva mode lex')
assertContains(widgetJs, 'page_section: payload.page_context || mode', 'widget conserva page_section compatibile')
assertContains(widgetJs, "document.addEventListener('click', openFloatingLexFromLegacyLink)", 'intercettazione link legacy lex')
assertContains(widgetJs, "url.origin !== window.location.origin || url.pathname !== '/lex'", 'link lex legacy solo same-origin')
assertContains(widgetJs, "applyLexPageContext(detail, { open: true })", 'click legacy apre widget lex')
assertNotContains(widgetJs, 'sendVia' + 'Companion(text);', 'send non usa companion come risposta finale')

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
assertContains(fascicoliData, 'FascicoliPagination', 'paginazione fascicoli tipizzata')
assertContains(fascicoliData, "query.set('page_size'", 'query page_size fascicoli')
assertContains(fascicoliData, 'getFascicoloDetailSection', 'caricamento lazy sezioni fascicolo')
assertContains(fascicoli, "loadLazySection('regia')", 'regia fascicolo lazy')
assertContains(fascicoliBridge, 'include_sections', 'payload dettaglio fascicolo con sezioni lazy')
assertContains(fascicoliBridge, '_item_light', 'lista fascicoli item light')
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
assertContains(documentEditor, 'Editor professionale', 'pagina editor documento react')
assertContains(documentEditor, 'contentEditable', 'editor documento modificabile')
assertContains(documentEditor, 'saveDocument', 'salvataggio editor documento')
assertContains(documentEditor, 'exportFile(data.endpoints.exportPdf', 'export pdf editor documento')
assertContains(documentEditor, 'FloatingLex', 'lex editor documento')
assertNotContains(documentEditor, 'https://esm.sh', 'editor documento senza CDN esm.sh')
assertContains(documentEditorData, '/api/v1/ui/fascicoli/${encodeURIComponent(idFascicolo)}/documenti/${encodeURIComponent(idDocumento)}/editor', 'api payload editor documento')
assertContains(documentEditorBridge, 'build_react_document_editor_payload', 'bridge editor documento')
assertContains(documentEditorBridge, '"mock_fallback": False', 'contratto editor documento senza mock')
assertContains(documentEditorBridge, "\"loadHtml\": f\"/api/editor/{fid}/{document['id']}/html\"", 'endpoint contenuto editor documento')

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
assertContains(studioModules, "href: '/impostazioni#dati-studio'", 'impostazioni studio operative ancorate')
assertContains(studioModules, "href: '/impostazioni?tab=pec'", 'impostazioni PEC operative')
assertContains(studioModules, "href: '/impostazioni?tab=firma'", 'impostazioni firma operative')
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

assertContains(adminDatabaseData, '/api/v1/ui/admin/database', 'api database amministrativo')
assertContains(adminDatabaseData, 'mock_fallback: false', 'contratto database senza mock')
assertContains(adminDatabase, 'runIntegrity', 'verifica integrita database')
assertContains(adminDatabase, 'data.actions.verify', 'endpoint verifica database')
assertContains(adminDatabase, 'data.actions.repair', 'endpoint riparazione database')
assertContains(adminDatabase, 'data.actions.optimize', 'endpoint ottimizzazione database')
assertContains(adminDatabase, 'data.actions.migrate', 'endpoint migrazione database')
assertContains(adminDatabase, 'data.actions.activateSqlite', 'endpoint attivazione sqlite database')
assertContains(adminDatabase, 'data.actions.exportZip', 'export zip database')
assertContains(adminDatabase, "'X-CSRF-Token': csrfToken()", 'csrf database post amministrativi')
assertContains(adminDatabase, 'window.confirm', 'conferma attivazione sqlite')
assertContains(adminDatabase, 'FloatingLex', 'lex database contestuale')
assertContains(adminDatabaseCss, '.iu-db-page', 'stili database amministrativo')
assertContains(adminDatabaseCss, '@media(max-width:900px)', 'responsive database amministrativo')
assertContains(adminDatabaseBridge, 'build_react_admin_database_payload', 'bridge database amministrativo')
assertContains(adminDatabaseBridge, '/admin/database/verifica-ripara', 'endpoint verifica e ripara database')
assertContains(adminDatabaseBridge, '"writes": "operational_routes"', 'scritture database su route operative')
assertNotContains(adminDatabaseBridge, 'governance', 'governance piattaforma non esposta nel contratto admin database')
assertNotContains(adminDatabaseBridge, 'systemHealth', 'salute sistema non esposta nel contratto admin database')
assertNotContains(adminDatabase, 'Governance', 'governance resta fuori dagli accessi tenant admin')
assertNotContains(adminDatabase, 'Salute sistema', 'salute sistema resta fuori dagli accessi tenant admin')
assertNotContains(adminDatabase, '_legacy=1', 'database amministrativo senza fallback visibile')

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
assertContains(reactShell, 'iusentra-react-bootstrap', 'bootstrap JSON profilo reale')
assertContains(css, '@media(max-width:760px)', 'responsive agenda')
assertContains(css, 'prefers-reduced-motion', 'motion agenda')

const wizardBundle = [wizardPro, wizardProStep, wizardProComplete, wizardProShared, wizardProData].join('\n')
const newReactBundle = [timesheet, timesheetData, cartelleCondivise, cartelleCondiviseData, wizardBundle].join('\n')

assertContains(timesheet, 'TimesheetPage', 'TimesheetPage presente')
assertContains(timesheetData, 'TimesheetData', 'timesheetData tipizzato')
assertContains(timesheetBridge, 'build_react_timesheet_payload', 'bridge backend timesheet')
assertContains(apiBridge, '@api_v1_react.get("/timesheet")', 'endpoint /api/v1/ui/timesheet')
assertContains(timesheetBridge, '"mock_fallback": False', 'timesheet mock_fallback false')
assertContains(timesheetBridge, '"writes": "operational_routes"', 'timesheet writes operational_routes')
assertContains(timesheetBridge, '"route_owner": "react_shell"', 'timesheet route_owner react_shell')
assertContains(timesheet, 'method="post" action={data.actions.create}', 'form POST timesheet nuovo')
assertContains(timesheetData, "create: '/timesheet/nuovo'", 'azione /timesheet/nuovo')
assertContains(timesheet, 'method="post" action={entry.stateAction}', 'form POST stato timesheet')
assertContains(timesheetBridge, 'f"/timesheet/{entry_id}/stato"', 'azione /timesheet/<id>/stato')
assertContains(timesheet, 'method="post" action={data.billing.action}', 'form POST genera parcella')
assertContains(timesheetData, "action: '/timesheet/genera-parcella'", 'azione /timesheet/genera-parcella')
assertNotContains(timesheet, 'href="#"', 'timesheet senza href vuoto')
assertNotContains(timesheetData, '_legacy=1', 'timesheet data senza route tecnica')

assertContains(cartelleCondivise, 'CartelleCondivisePage', 'CartelleCondivisePage presente')
assertContains(cartelleCondiviseData, 'CartelleCondiviseData', 'cartelleCondiviseData tipizzato')
assertContains(cartelleCondiviseBridge, 'build_react_condivisioni_payload', 'bridge backend cartelle condivise')
assertContains(apiBridge, '@api_v1_react.get("/cartelle-condivise")', 'endpoint /api/v1/ui/cartelle-condivise')
assertContains(cartelleCondiviseBridge, '"mock_fallback": False', 'cartelle condivise mock_fallback false')
assertContains(cartelleCondiviseBridge, '"writes": "operational_routes"', 'cartelle condivise writes operational_routes')
assertContains(cartelleCondiviseBridge, '"route_owner": "react_shell"', 'cartelle condivise route_owner react_shell')
assertContains(cartelleCondivise, 'data.actions.cleanupExpired', 'pulizia scaduti via endpoint reale')
assertContains(cartelleCondiviseData, "'/api/v1/condivisioni/pulizia-scaduti'", 'endpoint pulizia scaduti')
assertContains(cartelleCondiviseData, "'/api/v1/condivisioni/statistiche'", 'endpoint statistiche condivisioni')
assertNotContains(cartelleCondivise, 'href="#"', 'cartelle condivise senza href vuoto')
assertNotContains(cartelleCondiviseData, '_legacy=1', 'cartelle condivise data senza route tecnica')

assertContains(wizardPro, 'WizardProPage', 'WizardProPage presente')
assertContains(wizardProStep, 'WizardProStepPage', 'WizardProStepPage presente')
assertContains(wizardProComplete, 'WizardProCompletePage', 'WizardProCompletePage presente')
assertContains(wizardProData, 'WizardProStepData', 'wizardProData step tipizzato')
assertContains(wizardProData, 'WizardProCompleteData', 'wizardProData completo tipizzato')
assertContains(apiBridge, '@api_v1_react.get("/wizard-pro")', 'endpoint /api/v1/ui/wizard-pro')
assertContains(apiBridge, '@api_v1_react.get("/wizard-pro/session/<id_sessione>/step/<int:n>")', 'endpoint step wizard pro')
assertContains(apiBridge, '@api_v1_react.get("/wizard-pro/session/<id_sessione>/completo")', 'endpoint completo wizard pro')
assertContains(wizardProBridge, '"mock_fallback": False', 'wizard pro mock_fallback false')
assertContains(wizardProBridge, '"writes": "operational_routes"', 'wizard pro writes operational_routes')
assertContains(wizardProBridge, '"route_owner": "react_shell"', 'wizard pro route_owner react_shell')
assertNotContains(wizardBundle, 'actions.legacy', 'wizard pro senza actions.legacy')
assertNotContains(wizardBundle, 'Vista classica', 'wizard pro senza vista classica')
assertNotContains(wizardBundle, '_legacy=1', 'wizard pro senza link tecnico')
assertNotContains(wizardBundle, 'legacy', 'wizard pro componenti/data senza stringa legacy')
assertNotContains(wizardBundle, 'href="#"', 'wizard pro senza href vuoto')
assertContains(wizardPro, 'method="post" action={item.startHref}', 'form POST wizard pro nuovo')
assertContains(wizardProData, "start: '/wizard-pro/nuovo'", 'azione /wizard-pro/nuovo')
assertContains(wizardProBridge, 'f"/wizard-pro/{id_sessione}/step/{n}"', 'form /wizard-pro/<id>/step/<n>')
assertContains(wizardProComplete, 'method="post" action={data.actions.archive}', 'form POST wizard pro archivia')
assertContains(wizardProComplete, 'method="post" action={data.actions.delete}', 'form POST wizard pro elimina')
for (const field of [
  'step1_note',
  'doc_stato_',
  'doc_note_',
  'doc_extra_label',
  'note_preparazione',
  'argomenti_principali',
  'richieste_giudice',
  'eccezioni_da_sollevare',
  'precheck_firma_ok',
  'precheck_docs_pronti',
  'precheck_cliente_notificato',
  'precheck_trasporto_ok',
  'precheck_note',
  'esito',
  'esito_rinvio_data',
  'esito_note_verbale',
  'esito_azioni',
  'esito_aggiorna_fascicolo',
]) {
  assertContains(wizardBundle, field, `campo wizard pro ${field}`)
}
assertNotContains(newReactBundle, 'href="#"', 'nuove superfici senza href vuoto')
assertNotContains(newReactBundle, '_legacy=1', 'nuove superfici senza route tecnica visibile')
assertNotContains(newReactBundle, 'Vista classica', 'nuove superfici senza vista classica')

console.log('Contratti React verificati.')
