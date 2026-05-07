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
const preventivoWizardPage = read('src/components/PreventivoWizardPage.tsx')
const preventivoWizardCss = read('src/components/PreventivoWizardPage.css')
const preventivoWizardData = read('src/preventivoWizardData.ts')
const preventivoWizardUtils = read('src/preventivoWizardUtils.ts')
const preventivoWizardBridge = read('../web/services/react_preventivo_wizard_bridge.py')
const compensiForensiPage = read('src/components/CompensiForensiPage.tsx')
const compensiForensiData = read('src/compensiForensiData.ts')
const compensiForensiBridge = read('../web/services/react_compensi_forensi_bridge.py')
const tariffarioPage = read('src/components/TariffarioPage.tsx')
const tariffarioCss = read('src/components/TariffarioPage.css')
const tariffarioData = read('src/tariffarioData.ts')
const tariffarioBridge = read('../web/services/react_tariffario_bridge.py')
const templateAttiPage = read('src/components/TemplateAttiPage.tsx')
const templateAttiData = read('src/templateAttiData.ts')
const templateAttiBridge = read('../web/services/react_template_atti_bridge.py')
const redazioneAttiPage = read('src/components/RedazioneAttiPage.tsx')
const redazioneAttiData = read('src/redazioneAttiData.ts')
const redazioneAttiBridge = read('../web/services/react_redazione_atti_bridge.py')
const impeccableOpenDesignCss = read('src/theme/impeccable-open-design.css')
const openDesign = read('src/ui/openDesign.ts')
const tranche8aOpenDesignReport = read('../artifacts/react-migration/tranche-8a-open-design.md')
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
const auditAntiMascheramento = read('../scripts/react-migration/audit-anti-mascheramento.mjs')
const captureLegacyContracts = read('../scripts/react-migration/capture-legacy-contracts.py')
const checkRouteGate = read('../scripts/react-migration/check-route-gate.mjs')
const checkNoFakeReactFull = read('../scripts/react-migration/check-no-fake-react-full.mjs')
const checkAntiMascheramentoPilot = read('../scripts/react-migration/check-anti-mascheramento-pilot.mjs')
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
const tranche8aGate = read('../scripts/react-migration/check-tranche-8a-gate.py')
const tranche8aSecrets = read('../scripts/react-migration/check-tranche-8a-secrets.mjs')
const tranche8aNoCompensiLogic = read('../scripts/react-migration/check-tranche-8a-no-compensi-logic.mjs')
const tranche8aNoDocumentGeneration = read('../scripts/react-migration/check-tranche-8a-no-document-generation.mjs')
const tranche8aOpenDesign = read('../scripts/react-migration/check-tranche-8a-open-design.mjs')
const tranche9aGate = read('../scripts/react-migration/check-tranche-9a-gate.py')
const tranche9aSecrets = read('../scripts/react-migration/check-tranche-9a-secrets.mjs')
const tranche9aNoDocumentRaw = read('../scripts/react-migration/check-tranche-9a-no-document-raw.mjs')
const tranche9aNoLegalGeneration = read('../scripts/react-migration/check-tranche-9a-no-legal-generation.mjs')
const tranche9aNoDocumentGeneration = read('../scripts/react-migration/check-tranche-9a-no-document-generation.mjs')
const tranche9aOpenDesign = read('../scripts/react-migration/check-tranche-9a-open-design.mjs')
const tranche10aGate = read('../scripts/react-migration/check-tranche-10a-gate.py')
const tranche10aSecrets = read('../scripts/react-migration/check-tranche-10a-secrets.mjs')
const tranche10aNoExternalFetch = read('../scripts/react-migration/check-tranche-10a-no-external-fetch.mjs')
const tranche10aNoAiGeneration = read('../scripts/react-migration/check-tranche-10a-no-ai-generation.mjs')
const tranche10aNoDocumentRaw = read('../scripts/react-migration/check-tranche-10a-no-document-raw.mjs')
const tranche10aOpenDesign = read('../scripts/react-migration/check-tranche-10a-open-design.mjs')
const tranche17aOperational = read('../scripts/react-migration/check-tranche-17a-fatturazione-nuova-operational.mjs')
const tranche17aApi = read('../scripts/react-migration/check-tranche-17a-fatturazione-nuova-api.py')
const tranche17aNoFiscalLogic = read('../scripts/react-migration/check-tranche-17a-no-fiscal-logic.mjs')
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
const giurisprudenzaPage = read('src/components/GiurisprudenzaPage.tsx')
const giurisprudenzaCss = read('src/components/GiurisprudenzaPage.css')
const giurisprudenzaData = read('src/giurisprudenzaData.ts')
const giurisprudenzaBridge = read('../web/services/react_giurisprudenza_bridge.py')
const legalIntelligencePage = read('src/components/LegalIntelligencePage.tsx')
const legalIntelligenceCss = read('src/components/LegalIntelligencePage.css')
const legalIntelligenceData = read('src/legalIntelligenceData.ts')
const legalIntelligenceBridge = read('../web/services/react_legal_intelligence_bridge.py')
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
assertContains(auditAntiMascheramento, 'anti-mascheramento-audit.json', 'audit anti-mascheramento produce JSON')
assertContains(auditAntiMascheramento, 'anti-mascheramento-audit.md', 'audit anti-mascheramento produce Markdown')
assertContains(auditAntiMascheramento, 'LegacyPostForm', 'audit anti-mascheramento censisce LegacyPostForm')
assertContains(auditAntiMascheramento, '?_legacy=1', 'audit anti-mascheramento censisce fallback legacy')
assertContains(checkNoFakeReactFull, 'no-fake-react-full-report.md', 'check no fake React full produce report')
assertContains(checkNoFakeReactFull, 'react_operational_full', 'check no fake React full presidia full operativi')
assertContains(checkAntiMascheramentoPilot, '@api_v1_react.post("/utenti/nuovo")', 'check pilota presidia endpoint nuovo utente')
assertContains(checkAntiMascheramentoPilot, 'localStorage', 'check pilota blocca storage browser')
assertContains(captureLegacyContracts, 'create_app', 'contract capture usa Flask test_client')
assertContains(captureLegacyContracts, '_legacy=1', 'contract capture usa fallback legacy')
assertContains(checkRouteGate, 'unlockFromGate=true richiede status react_bridge/react_operational_partial/react_operational_full', 'route gate blocca unlock non classificati')
assertContains(checkRouteGate, 'Tranche 4A', 'route gate limita gli sblocchi della Tranche 4A')
assertContains(checkRouteGate, 'Tranche 5A', 'route gate include gli sblocchi della Tranche 5A')
assertContains(checkRouteGate, 'Tranche 6A', 'route gate include gli sblocchi della Tranche 6A')
assertContains(checkRouteGate, 'Tranche 7A', 'route gate include gli sblocchi della Tranche 7A')
assertContains(checkRouteGate, 'Tranche 8A', 'route gate include gli sblocchi della Tranche 8A')
assertContains(checkRouteGate, 'Tranche 9A', 'route gate include gli sblocchi della Tranche 9A')
assertContains(checkRouteGate, 'Tranche 10A', 'route gate include gli sblocchi della Tranche 10A')
assertContains(checkUiConsistency, 'ui-allowed-classes.json', 'UI consistency usa policy classi')
assertContains(checkUiConsistency, 'href placeholder #', 'UI consistency blocca href placeholder')
assertContains(runSafeReactMigration, 'cleanRequired()', 'runner richiede working tree pulito')
assertContains(runSafeReactMigration, '--tranche=2a', 'runner supporta Tranche 2A')
assertContains(runSafeReactMigration, '--tranche=3a', 'runner supporta Tranche 3A')
assertContains(runSafeReactMigration, '--tranche=4a', 'runner supporta Tranche 4A')
assertContains(runSafeReactMigration, '--tranche=5a', 'runner supporta Tranche 5A')
assertContains(runSafeReactMigration, '--tranche=6a', 'runner supporta Tranche 6A')
assertContains(runSafeReactMigration, '--tranche=7a', 'runner supporta Tranche 7A')
assertContains(runSafeReactMigration, '--tranche=8a', 'runner supporta Tranche 8A')
assertContains(runSafeReactMigration, '--tranche=9a', 'runner supporta Tranche 9A')
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
assertContains(tranche17aOperational, '@api_v1_react.post("/fatturazione/nuova")', 'check Tranche 17A presidia POST JSON nuova fatturazione')
assertContains(tranche17aOperational, 'Rollback tecnico', 'check Tranche 17A presidia rollback tecnico')
assertContains(tranche17aApi, 'manager.crea(', 'check Tranche 17A API presidia riuso GestioneFatturazione')
assertContains(tranche17aApi, 'fatturazione.scrivi', 'check Tranche 17A API presidia permessi backend')
assertContains(tranche17aNoFiscalLogic, 'calculateIva', 'check Tranche 17A blocca calcolo fiscale frontend')
assertContains(tranche7aGate, '/preventivi/conferimento/nuovo', 'check Tranche 7A verifica nuovo conferimento')
assertContains(tranche7aSecrets, 'react_preventivi_bridge.py', 'check Tranche 7A anti-segreti scansiona bridge preventivi')
assertContains(tranche7aNoCompensiLogic, 'calculateCompenso', 'check Tranche 7A blocca logica compensi frontend')
assertContains(tranche7aNoDocumentGeneration, 'generatePdf', 'check Tranche 7A blocca generazione documenti')
assertContains(tranche8aGate, '/compensi-forensi', 'check Tranche 8A verifica compensi forensi')
assertContains(tranche8aGate, '/tariffario', 'check Tranche 8A verifica tariffario')
assertContains(tranche8aSecrets, 'react_compensi_forensi_bridge.py', 'check Tranche 8A anti-segreti scansiona bridge compensi')
assertContains(tranche8aNoCompensiLogic, 'calculateCompenso', 'check Tranche 8A blocca logica compensi frontend')
assertContains(tranche8aNoDocumentGeneration, 'generatePdf', 'check Tranche 8A blocca generazione documenti')
assertContains(tranche8aOpenDesign, 'impeccable-open-design.css', 'check Tranche 8A verifica token Open Design')
assertContains(tranche9aGate, '/template-atti/catalogo', 'check Tranche 9A verifica catalogo template')
assertContains(tranche9aGate, '/redazione-atti', 'check Tranche 9A verifica redazione atti')
assertContains(tranche9aSecrets, 'react_template_atti_bridge.py', 'check Tranche 9A anti-segreti scansiona bridge template')
assertContains(tranche9aNoDocumentRaw, 'dangerouslySetInnerHTML', 'check Tranche 9A blocca document raw')
assertContains(tranche9aNoLegalGeneration, 'generateAtto', 'check Tranche 9A blocca redazione automatica')
assertContains(tranche9aNoDocumentGeneration, 'generatePdf', 'check Tranche 9A blocca produzione file')
assertContains(tranche9aOpenDesign, 'openDesignDocumentSurface', 'check Tranche 9A verifica Open Design documentale')
assertContains(uiAllowedClasses, '"allowedPrefix": "iu-"', 'policy classi UI prefisso iu')
assertContains(routeRiskRules, '"critical"', 'regole rischio route critical')
assertContains(impeccableOpenDesignCss, '--iu-od-space-', 'token Open Design spazio')
assertContains(impeccableOpenDesignCss, '--iu-od-focus', 'token Open Design focus')
assertContains(impeccableOpenDesignCss, '--iu-od-doc-gap', 'token Open Design documentale gap')
assertContains(impeccableOpenDesignCss, '.iu-od-action-row', 'utility Open Design azioni documentali')
assertContains(openDesign, 'Impeccable / Open Design', 'contratto Open Design interno')
assertContains(openDesign, "classPrefix: 'iu-'", 'contratto Open Design prefisso classi')
assertContains(openDesign, 'openDesignDocumentSurface', 'contratto Open Design superficie documentale')
assertContains(tranche8aOpenDesignReport, 'Token creati', 'report Open Design 8A')
if (routeManifest.policy?.currentReleaseUnlocksRoutes !== true) {
  throw new Error('route manifest: currentReleaseUnlocksRoutes deve essere true nelle tranche di promozione')
}
const allowedGovernedUnlocks = new Set(['/statistiche', '/audit', '/registro-attivita', '/utenti', '/utenti/nuovo', '/profili', '/backup', '/sito-studio', '/sito-studio/contatti', '/studio', '/amministrazione', '/fatturazione', '/fatturazione/nuova', '/incassi-pagamenti', '/preventivi', '/preventivi/nuovo', '/preventivi/wizard', '/preventivi/conferimento/nuovo', '/compensi-forensi', '/tariffario', '/template-atti', '/template-atti/catalogo', '/redazione-atti', '/giurisprudenza', '/legal-intelligence', '/legal-intelligence/news', '/legal-intelligence/mediazione', '/ricerca-legale'])
const allowedManifestStatuses = new Set(['legacy_operational', 'react_shell', 'react_bridge', 'react_operational_partial', 'react_operational_full'])
const unlockStatuses = new Set(['react_bridge', 'react_operational_partial', 'react_operational_full'])
for (const entry of routeManifest.routes ?? []) {
  if (entry.unlockFromGate === true && !allowedGovernedUnlocks.has(entry.route)) {
    throw new Error(`route manifest: ${entry.route} non puo essere sbloccata nelle tranche governate`)
  }
  if (!allowedManifestStatuses.has(entry.status)) {
    throw new Error(`route manifest: ${entry.route} ha status non ammesso ${entry.status}`)
  }
  if (entry.status === 'react_full') {
    throw new Error(`route manifest: ${entry.route} usa react_full deprecato`)
  }
  if (entry.unlockFromGate === true && !unlockStatuses.has(entry.status)) {
    throw new Error(`route manifest: ${entry.route} sbloccata con status non operativo ${entry.status}`)
  }
  if (!entry.route || !entry.family || !entry.status || !entry.risk || !entry.targetComponent || !entry.targetData || !entry.targetBridge || !entry.legacyContract) {
    throw new Error(`route manifest: entry incompleta per ${entry.route || 'route senza nome'}`)
  }
}
for (const [route, status] of [
  ['/utenti/nuovo', 'react_operational_full'],
  ['/utenti', 'react_operational_full'],
  ['/profili', 'react_operational_full'],
  ['/backup', 'react_operational_full'],
  ['/sito-studio', 'react_bridge'],
  ['/sito-studio/contatti', 'react_bridge'],
  ['/fatturazione/nuova', 'react_operational_full'],
  ['/preventivi/wizard', 'react_operational_partial'],
  ['/tariffario', 'react_operational_partial'],
  ['/giurisprudenza', 'react_bridge'],
  ['/legal-intelligence', 'react_bridge'],
  ['/legal-intelligence/news', 'react_bridge'],
  ['/legal-intelligence/mediazione', 'react_bridge'],
  ['/ricerca-legale', 'react_bridge'],
]) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== status || entry.unlockFromGate !== true) {
    throw new Error(`route manifest: ${route} deve essere ${status} con unlockFromGate=true`)
  }
}
for (const route of ['/sito-studio/builder', '/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/sincronizzazione-calendari']) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    throw new Error(`route manifest: ${route} deve restare legacy_operational con unlockFromGate=false`)
  }
}
for (const route of ['/fatturazione/*', '/preventivi/*', '/compensi-forensi/*', '/tariffario/*', '/template-atti/nuovo', '/template-atti/*', '/redazione-atti/*', '/giurisprudenza/nuova', '/giurisprudenza/*', '/legal-intelligence/*', '/ricerca-legale/*', '/deposito/checklist', '/impostazioni/pagamenti']) {
  const entry = (routeManifest.routes ?? []).find((item) => item.route === route)
  if (!entry || entry.status !== 'legacy_operational' || entry.unlockFromGate !== false) {
    throw new Error(`route manifest: ${route} deve restare legacy_operational con unlockFromGate=false`)
  }
}
for (const route of ['/utenti', '/profili', '/audit', '/registro-attivita', '/studio', '/amministrazione', '/impostazioni', '/impostazioni-studio', '/impostazioni/calendario', '/impostazioni/pagamenti', '/sincronizzazione-calendari', '/backup', '/sito-studio', '/sito-studio/contatti', '/sito-studio/builder', '/statistiche', '/fatturazione', '/fatturazione/nuova', '/fatturazione/*', '/incassi-pagamenti', '/preventivi', '/preventivi/nuovo', '/preventivi/conferimento/nuovo', '/preventivi/*', '/preventivi/wizard', '/compensi-forensi', '/compensi-forensi/*', '/tariffario', '/tariffario/*', '/template-atti', '/template-atti/catalogo', '/template-atti/nuovo', '/template-atti/*', '/redazione-atti', '/redazione-atti/*', '/checklist', '/giurisprudenza', '/giurisprudenza/nuova', '/giurisprudenza/*', '/legal-intelligence', '/legal-intelligence/news', '/legal-intelligence/mediazione', '/legal-intelligence/*', '/ricerca-legale', '/ricerca-legale/*', '/deposito/checklist', '/polisWeb', '/pdp', '/pat', '/sigit', '/sigp', '/portali/*']) {
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
assertContains(app, "PreventivoWizardPage", 'route preventivo guidato react')
assertContains(app, "CompensiForensiPage", 'route compensi forensi react')
assertContains(app, "TariffarioPage", 'route tariffario react')
assertContains(app, "TemplateAttiPage", 'route template atti react')
assertContains(app, "RedazioneAttiPage", 'route redazione atti react')
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
assertContains(app, "isPreventivoWizardPage", 'detection preventivo guidato react')
assertContains(app, "isCompensiForensiPage", 'detection compensi forensi react')
assertContains(app, "isTariffarioPage", 'detection tariffario react')
assertContains(app, "isTemplateAttiPage", 'detection template atti react')
assertContains(app, "isRedazioneAttiPage", 'detection redazione atti react')
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
assertContains(app, "isPreventivoWizardPage?<PreventivoWizardPage/>", 'render preventivo guidato prima della lista preventivi')
assertContains(app, "isPreventiviPage?<PreventiviPage/>", 'render preventivi prima dello studio module')
assertContains(app, "isCompensiForensiPage?<CompensiForensiPage/>", 'render compensi prima dello studio module')
assertContains(app, "isTariffarioPage?<TariffarioPage/>", 'render tariffario prima dello studio module')
assertContains(app, "isTemplateAttiPage?<TemplateAttiPage/>", 'render template atti prima dello studio module')
assertContains(app, "isRedazioneAttiPage?<RedazioneAttiPage/>", 'render redazione atti prima dello studio module')
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
assertContains(preventivoWizardPage, 'getPreventivoWizardPage', 'PreventivoWizardPage usa getPreventivoWizardPage')
assertContains(preventivoWizardPage, 'runPreventivoWizardCalculation', 'PreventivoWizardPage usa calcolo wizard reale')
assertContains(preventivoWizardPage, 'createPreventivoWizard', 'PreventivoWizardPage usa creazione wizard reale')
assertContains(preventivoWizardPage, 'Cliente e contesto', 'PreventivoWizardPage espone step cliente')
assertContains(preventivoWizardPage, 'Tipologia e motore preventivo', 'PreventivoWizardPage espone step tipologia')
assertContains(preventivoWizardPage, 'Compenso base e fasi', 'PreventivoWizardPage espone step calcolo')
assertContains(preventivoWizardPage, 'Bozza del preventivo', 'PreventivoWizardPage espone step bozza')
assertContains(preventivoWizardPage, 'practiceMatchesFilters', 'PreventivoWizardPage filtri pratica coerenti')
assertContains(preventivoWizardPage, 'Azzera filtri visibili', 'PreventivoWizardPage recupero filtri visibili incoerenti')
assertContains(preventivoWizardPage, 'Aggiungi voce area pratica', 'PreventivoWizardPage aggiunta voce area pratica')
assertContains(preventivoWizardPage, 'iu-pwiz-added-practices', 'PreventivoWizardPage riepilogo voci area pratica aggiunte')
assertContains(preventivoWizardPage, 'Il cliente ha accettato il preventivo', 'PreventivoWizardPage richiede accettazione prima del conferimento')
assertContains(preventivoWizardPage, 'preventivo_accettato', 'PreventivoWizardPage invia stato accettazione preventivo')
assertContains(preventivoWizardPage, 'quando la tabella ministeriale espone solo un importo unico', 'PreventivoWizardPage spiega il riparto operativo del compenso unico')
assertContains(preventivoWizardPage, 'compenso_unico: phases.includes', 'PreventivoWizardPage lascia decidere all avvocato il flag compenso unico')
assertNotContains(preventivoWizardPage, 'CLASSIFICAZIONE OPERATIVA', 'PreventivoWizardPage classificazione operativa silenziosa')
assertNotContains(preventivoWizardPage, 'Tassonomia tecnica di supporto', 'PreventivoWizardPage tassonomia tecnica silenziosa')
assertContains(preventivoWizardPage, 'iu-pwiz-action-label-short', 'PreventivoWizardPage CTA footer compatta')
assertContains(preventivoWizardCss, "grid-template-areas: 'sidebar main'", 'PreventivoWizardPage riepilogo a sinistra')
assertContains(preventivoWizardCss, '.iu-pwiz-money-grid > div', 'PreventivoWizardPage riepilogo economico affiancato')
assertContains(apiBridge, 'conferimento_richiesto_senza_accettazione', 'PreventivoWizardPage blocca conferimento senza accettazione')
assertNotContains(preventivoWizardBridge, 'Il calcolo economico resta nel motore preventivo Python.', 'PreventivoWizardPage senza avviso motore backend visibile')
assertNotContains(preventivoWizardBridge, 'La vista tecnica storica resta disponibile con ?_legacy=1.', 'PreventivoWizardPage senza avviso legacy visibile')
assertContains(compensiForensiPage, 'getCompensiForensiPage', 'CompensiForensiPage usa getCompensiForensiPage')
assertContains(tariffarioPage, 'getTariffarioPage', 'TariffarioPage usa getTariffarioPage')
assertContains(templateAttiPage, 'getTemplateAttiPage', 'TemplateAttiPage usa getTemplateAttiPage')
assertContains(templateAttiPage, 'getTemplateAttiCatalogoPage', 'TemplateAttiPage usa getTemplateAttiCatalogoPage')
assertContains(redazioneAttiPage, 'getRedazioneAttiPage', 'RedazioneAttiPage usa getRedazioneAttiPage')
assertNotContains(utentiPage, 'LegacyPostForm', 'UtentiPage non usa LegacyPostForm nel flusso principale')
assertContains(utentiData, 'apiPostJson<unknown>', 'utentiData usa apiPostJson per le azioni utenti')
assertContains(utentiPage, 'updateUtenteStatus', 'UtentiPage aggiorna stato via data client')
assertContains(utentiPage, 'updateUtenteRole', 'UtentiPage aggiorna ruolo via data client')
assertContains(utentiPage, 'resetUtentePassword', 'UtentiPage resetta credenziale via data client')
assertContains(utentiPage, 'updateUtenteProfile', 'UtentiPage aggiorna profilo via data client')
assertContains(utentiPage, 'Operazione completata', 'UtentiPage gestisce success')
assertContains(utentiPage, 'Controlla i dati', 'UtentiPage gestisce errori validazione')
assertContains(utentiPage, 'Permesso negato', 'UtentiPage gestisce errore permesso')
assertContains(utentiPage, 'Errore di rete', 'UtentiPage gestisce errore server')
assertContains(utentiPage, 'passwordRef', 'UtentiPage non conserva password nello stato React')
assertNotContains(utentiPage, 'localStorage', 'UtentiPage non usa localStorage')
assertNotContains(utentiPage, 'sessionStorage', 'UtentiPage non usa sessionStorage')
assertNotContains(profiliPage, 'LegacyPostForm', 'ProfiliPage non usa LegacyPostForm nel flusso principale')
assertContains(profiliPage, 'saveProfiliPermissions', 'ProfiliPage salva profili via JSON')
assertNotContains(backupPage, 'LegacyPostForm', 'BackupPage non usa LegacyPostForm nel flusso principale')
assertContains(backupPage, 'createBackup', 'BackupPage crea backup via data client JSON')
assertContains(backupPage, 'verifyBackupIntegrity', 'BackupPage verifica integrita via data client JSON')
assertContains(sitoStudioPage, 'LegacyPostForm', 'SitoStudioPage usa LegacyPostForm per azioni legacy')
assertNotContains(fatturazionePage, 'LegacyPostForm', 'FatturazionePage non usa LegacyPostForm nel flusso nuova fatturazione')
assertContains(fatturazionePage, 'createFattura', 'FatturazionePage salva nuova parcella via JSON')
assertContains(fatturazionePage, 'saveStatus', 'FatturazionePage gestisce saving/success/error')
assertContains(fatturazionePage, 'Rollback tecnico', 'FatturazionePage confina il fallback legacy in sezione tecnica')
assertContains(fatturazioneData, 'apiPostJson<CreateFatturaResult>', 'fatturazioneData usa apiPostJson per nuova parcella')
assertContains(fatturazioneBridge, '"writes": "json_api"', 'bridge nuova fatturazione dichiara scrittura JSON')
assertContains(fatturazioneBridge, '"canonical_calculation": "backend"', 'bridge nuova fatturazione dichiara calcolo canonico backend')
assertContains(apiBridge, '@api_v1_react.post("/fatturazione/nuova")', 'endpoint JSON crea nuova parcella')
assertContains(apiBridge, '_puo_scrivere_fatturazione()', 'nuova parcella controlla permesso scrittura fatturazione')
assertNotContains(preventiviPage, 'LegacyPostForm', 'PreventiviPage non usa LegacyPostForm nel flusso principale')
assertContains(preventiviPage, 'createPreventivo', 'PreventiviPage crea preventivo via JSON')
assertContains(preventiviPage, 'createConferimento', 'PreventiviPage crea conferimento via JSON')
assertContains(preventiviPage, 'getPreventivoDetail', 'PreventiviPage legge dettaglio preventivo via JSON')
assertContains(preventiviPage, 'updatePreventivoStatus', 'PreventiviPage aggiorna stato preventivo via JSON')
assertContains(preventiviPage, 'Rollback tecnico', 'PreventiviPage confina il fallback legacy in sezione tecnica')
assertContains(preventiviData, 'apiPostJson<CreatePreventivoResult>', 'preventiviData usa apiPostJson per nuovo preventivo')
assertContains(preventiviData, 'apiPostJson<CreateConferimentoResult>', 'preventiviData usa apiPostJson per nuovo conferimento')
assertContains(preventiviData, 'apiPostJson<PreventivoMutationResult>', 'preventiviData usa apiPostJson per azioni archivio preventivi')
assertContains(apiBridge, '@api_v1_react.post("/preventivi/nuovo")', 'endpoint JSON crea preventivo')
assertContains(apiBridge, '@api_v1_react.post("/preventivi/conferimento/nuovo")', 'endpoint JSON crea conferimento')
assertContains(apiBridge, '@api_v1_react.get("/preventivi/<id_preventivo>")', 'endpoint JSON dettaglio preventivo')
assertContains(apiBridge, '@api_v1_react.post("/preventivi/<id_preventivo>/stato")', 'endpoint JSON stato preventivo')
assertContains(fatturazionePage, 'getFatturazioneDetail', 'FatturazionePage legge dettaglio archivio via JSON')
assertContains(fatturazionePage, 'updateFatturazioneStatus', 'FatturazionePage aggiorna stato archivio via JSON')
assertContains(fatturazionePage, 'markFatturazionePaid', 'FatturazionePage segna pagamento via JSON')
assertContains(fatturazioneData, 'apiPostJson<FatturazioneMutationResult>', 'fatturazioneData usa apiPostJson per azioni archivio')
assertContains(apiBridge, '@api_v1_react.get("/fatturazione/<id_documento>")', 'endpoint JSON dettaglio fatturazione')
assertContains(apiBridge, '@api_v1_react.post("/fatturazione/<id_documento>/stato")', 'endpoint JSON stato fatturazione')
assertContains(compensiForensiPage, 'LegacyPostForm', 'CompensiForensiPage usa LegacyPostForm se presente')
assertContains(tariffarioPage, 'LegacyPostForm', 'TariffarioPage usa LegacyPostForm se presente')
assertContains(tariffarioPage, 'RIEPILOGO IN TEMPO REALE', 'TariffarioPage espone riepilogo economico in tempo reale')
assertContains(tariffarioPage, 'iu-tar-summary-sticky', 'TariffarioPage rende sticky il riepilogo economico')
assertContains(tariffarioPage, 'Calcola e aggiorna il quadro', 'TariffarioPage porta il refresh nel riepilogo sticky')
assertContains(tariffarioPage, 'aria-live="polite"', 'TariffarioPage aggiorna il riepilogo senza rumore')
assertNotContains(tariffarioPage, '<StatsGrid', 'TariffarioPage senza KPI tecniche sopra il workspace')
assertNotContains(tariffarioPage, '<WarningList', 'TariffarioPage senza avvisi tecnici bootstrap in pagina')
assertContains(tariffarioCss, '.iu-tar-summary-sticky', 'TariffarioPage CSS sticky dedicato al riepilogo')
if (tariffarioCss.includes('position: sticky;')) {
  assertContains(tariffarioCss, 'position: sticky;', 'TariffarioPage riepilogo segue lo scroll desktop')
} else {
  assertContains(tariffarioPage, "position: 'fixed'", 'TariffarioPage riepilogo flottante segue lo scroll desktop')
}
assertContains(tariffarioCss, '.iu-tar-realtime-head', 'TariffarioPage azioni compatte nel riepilogo')
assertNotContains(tariffarioBridge, 'Creazione preventivo, parcella e flussi fiscali restano sulle route Flask esistenti.', 'Bridge tariffario senza avviso scritture legacy visibile')
assertNotContains(tariffarioBridge, 'Il motore tariffario canonico resta nel backend Python.', 'Bridge tariffario senza avviso motore backend visibile')
assertContains(statisticheData, '/api/v1/ui/statistiche', 'statisticheData usa endpoint statistiche')
assertContains(auditData, '/api/v1/ui/audit', 'auditData usa endpoint audit')
assertContains(auditData, '/api/v1/ui/registro-attivita', 'auditData usa endpoint registro attivita')
assertContains(utentiData, '/api/v1/ui/utenti', 'utentiData usa endpoint utenti')
assertContains(profiliData, '/api/v1/ui/profili', 'profiliData usa endpoint profili')
assertContains(profiliData, 'apiPostJson<SaveProfiliResult>', 'profiliData usa apiPostJson per salvataggio profili')
assertContains(backupData, '/api/v1/ui/backup', 'backupData usa endpoint backup')
assertContains(backupData, 'apiPostJson', 'backupData usa apiPostJson per azioni backup')
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
assertContains(preventivoWizardData, '/api/v1/ui/preventivi/wizard', 'preventivoWizardData usa endpoint bootstrap wizard')
assertContains(preventivoWizardData, '/api/v1/ui/preventivi/wizard/calculate', 'preventivoWizardData usa endpoint calcolo wizard')
assertContains(preventivoWizardData, '/api/v1/ui/preventivi/wizard/create', 'preventivoWizardData usa endpoint creazione wizard')
assertContains(compensiForensiData, '/api/v1/ui/compensi-forensi', 'compensiForensiData usa endpoint compensi forensi')
assertContains(tariffarioData, '/api/v1/ui/tariffario', 'tariffarioData usa endpoint tariffario')
assertContains(templateAttiData, '/api/v1/ui/template-atti', 'templateAttiData usa endpoint template atti')
assertContains(templateAttiData, '/api/v1/ui/template-atti/catalogo', 'templateAttiData usa endpoint catalogo template atti')
assertContains(redazioneAttiData, '/api/v1/ui/redazione-atti', 'redazioneAttiData usa endpoint redazione atti')
assertContains(statisticheBridge, '"route_owner": "react_shell"', 'bridge statistiche route_owner react_shell')
assertContains(auditBridge, '"route_owner": "react_shell"', 'bridge audit route_owner react_shell')
assertContains(utentiBridge, '"route_owner": "react_shell"', 'bridge utenti route_owner react_shell')
assertContains(profiliBridge, '"route_owner": "react_shell"', 'bridge profili route_owner react_shell')
assertContains(backupBridge, '"route_owner": "react_shell"', 'bridge backup route_owner react_shell')
assertContains(backupBridge, '"writes": "json_api"', 'bridge backup scritture JSON operative')
assertContains(backupBridge, '"restore_migrated": False', 'bridge backup restore non migrato')
assertContains(sitoStudioBridge, '"route_owner": "react_shell"', 'bridge sito studio route_owner react_shell')
assertContains(fatturazioneBridge, '"route_owner": "react_shell"', 'bridge fatturazione route_owner react_shell')
assertContains(incassiPagamentiBridge, '"route_owner": "react_shell"', 'bridge incassi pagamenti route_owner react_shell')
assertContains(preventiviBridge, '"route_owner": "react_shell"', 'bridge preventivi route_owner react_shell')
assertContains(preventivoWizardBridge, '"route_owner": "react_shell"', 'bridge preventivo guidato route_owner react_shell')
assertContains(preventivoWizardBridge, '"writes": "operational_routes"', 'bridge preventivo guidato scritture operative')
assertContains(preventivoWizardBridge, '"mock_fallback": False', 'bridge preventivo guidato senza mock fallback')
assertContains(preventivoWizardBridge, 'motore_calcola', 'bridge preventivo guidato riusa motore tariffario')
assertContains(compensiForensiBridge, '"route_owner": "react_shell"', 'bridge compensi route_owner react_shell')
assertContains(tariffarioBridge, '"route_owner": "react_shell"', 'bridge tariffario route_owner react_shell')
assertContains(templateAttiBridge, '"route_owner": "react_shell"', 'bridge template atti route_owner react_shell')
assertContains(redazioneAttiBridge, '"route_owner": "react_shell"', 'bridge redazione atti route_owner react_shell')
assertContains(apiBridge, '@api_v1_react.get("/statistiche")', 'endpoint UI statistiche')
assertContains(apiBridge, '@api_v1_react.get("/audit")', 'endpoint UI audit')
assertContains(apiBridge, '@api_v1_react.get("/registro-attivita")', 'endpoint UI registro attivita')
assertContains(apiBridge, '@api_v1_react.get("/utenti")', 'endpoint UI utenti')
assertContains(apiBridge, '@api_v1_react.post("/utenti/nuovo")', 'endpoint UI nuovo utente JSON')
assertContains(apiBridge, 'def utenti_nuovo_crea', 'handler JSON nuovo utente')
assertContains(apiBridge, '_puo_scrivere_utenti()', 'nuovo utente controlla permesso scrittura')
assertContains(apiBridge, 'manager.crea(', 'nuovo utente riusa manager utenti')
assertContains(apiBridge, 'manager.registra_evento(', 'nuovo utente registra audit')
assertNotContains(apiBridge, '"password":', 'API React non restituisce password')
assertContains(apiBridge, '@api_v1_react.get("/profili")', 'endpoint UI profili')
assertContains(apiBridge, '@api_v1_react.post("/profili")', 'endpoint JSON scrittura profili')
assertContains(apiBridge, '@api_v1_react.get("/backup")', 'endpoint UI backup')
assertContains(apiBridge, '@api_v1_react.post("/backup/crea")', 'endpoint JSON crea backup')
assertContains(apiBridge, '@api_v1_react.post("/backup/verifica")', 'endpoint JSON verifica backup')
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
assertContains(apiBridge, '@api_v1_react.get("/preventivi/wizard")', 'endpoint UI preventivo guidato')
assertContains(apiBridge, '@api_v1_react.post("/preventivi/wizard/calculate")', 'endpoint calcolo preventivo guidato')
assertContains(apiBridge, '@api_v1_react.post("/preventivi/wizard/create")', 'endpoint creazione preventivo guidato')
assertContains(apiBridge, '@api_v1_react.get("/compensi-forensi")', 'endpoint UI compensi forensi')
assertContains(apiBridge, '@api_v1_react.get("/tariffario")', 'endpoint UI tariffario')
assertContains(apiBridge, '@api_v1_react.get("/template-atti")', 'endpoint UI template atti')
assertContains(apiBridge, '@api_v1_react.get("/template-atti/catalogo")', 'endpoint UI catalogo template atti')
assertContains(apiBridge, '@api_v1_react.get("/redazione-atti")', 'endpoint UI redazione atti')
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
assertNotContains(legacyOperationalTuple, '"/compensi-forensi"', 'gate legacy senza compensi forensi exact')
assertNotContains(legacyOperationalTuple, '"/tariffario"', 'gate legacy senza tariffario exact')
assertNotContains(legacyOperationalTuple, '"/template-atti"', 'gate legacy senza template atti exact')
assertNotContains(legacyOperationalTuple, '"/redazione-atti"', 'gate legacy senza redazione atti exact')
assertContains(legacyOperationalTuple, '"/impostazioni"', 'gate legacy mantiene impostazioni')
assertContains(legacyOperationalTuple, '"/impostazioni-studio"', 'gate legacy mantiene impostazioni studio')
assertContains(legacyOperationalTuple, '"/sincronizzazione-calendari"', 'gate legacy mantiene sincronizzazione calendari')
assertContains(legacyOperationalTuple, '"/checklist"', 'gate legacy mantiene checklist')
assertContains(legacyOperationalTuple, '"/deposito/checklist"', 'gate legacy mantiene deposito checklist')
assertNotContains(legacyOperationalTuple, '"/giurisprudenza"', 'gate legacy senza giurisprudenza exact')
assertNotContains(legacyOperationalTuple, '"/legal-intelligence"', 'gate legacy senza legal intelligence exact')
assertNotContains(legacyOperationalTuple, '"/ricerca-legale"', 'gate legacy senza ricerca legale exact')
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
assertContains(reactRouteGate, '"/preventivi/wizard"', 'gate consente preventivo guidato react')
assertContains(reactRouteGate, '"/preventivi/conferimento/nuovo"', 'gate consente nuovo conferimento')
assertNotContains(reactRouteGate, 'lower == "/compensi-forensi" or lower.startswith("/compensi-forensi/")', 'gate non blocca exact compensi forensi')
assertNotContains(reactRouteGate, 'lower == "/tariffario" or lower.startswith("/tariffario/")', 'gate non blocca exact tariffario')
assertContains(reactRouteGate, 'lower.startswith("/compensi-forensi/")', 'gate protegge nested compensi forensi')
assertContains(reactRouteGate, 'lower.startswith("/tariffario/")', 'gate protegge nested tariffario')
assertContains(reactRouteGate, 'lower == "/template-atti/nuovo"', 'gate protegge nuovo template atti legacy')
assertContains(reactRouteGate, 'lower.startswith("/template-atti/") and lower != "/template-atti/catalogo"', 'gate protegge nested template atti legacy')
assertContains(reactRouteGate, 'lower.startswith("/redazione-atti/")', 'gate protegge nested redazione atti legacy')
assertContains(reactRouteGate, 'lower == "/checklist" or lower.startswith("/checklist/")', 'gate protegge checklist legacy')
assertContains(reactRouteGate, 'lower == "/deposito/checklist" or lower.startswith("/deposito/checklist/")', 'gate protegge deposito checklist legacy')
assertContains(reactRouteGate, 'lower.startswith("/giurisprudenza/")', 'gate protegge nested giurisprudenza legacy')
assertContains(reactRouteGate, 'lower.startswith("/legal-intelligence/") and lower not in {', 'gate protegge nested legal intelligence legacy')
assertContains(reactRouteGate, '"/legal-intelligence/news"', 'gate consente legal intelligence news')
assertContains(reactRouteGate, '"/legal-intelligence/mediazione"', 'gate consente legal intelligence mediazione')
assertContains(reactRouteGate, 'lower.startswith("/ricerca-legale/")', 'gate protegge nested ricerca legale legacy')
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
assertNotContains(shellLegacyFirstTuple, '"/compensi-forensi"', 'shell legacy-first senza compensi exact')
assertNotContains(shellLegacyFirstTuple, '"/tariffario"', 'shell legacy-first senza tariffario exact')
assertNotContains(shellLegacyFirstTuple, '"/template-atti"', 'shell legacy-first senza template atti exact')
assertNotContains(shellLegacyFirstTuple, '"/redazione-atti"', 'shell legacy-first senza redazione atti exact')
assertContains(shellLegacyFirstTuple, '"/impostazioni"', 'shell legacy-first mantiene impostazioni')
assertContains(shellLegacyFirstTuple, '"/impostazioni-studio"', 'shell legacy-first mantiene impostazioni studio')
assertContains(shellLegacyFirstTuple, '"/sincronizzazione-calendari"', 'shell legacy-first mantiene sincronizzazione calendari')
assertNotContains(shellLegacyFirstTuple, '"/giurisprudenza"', 'shell legacy-first senza giurisprudenza exact')
assertNotContains(shellLegacyFirstTuple, '"/legal-intelligence"', 'shell legacy-first senza legal intelligence exact')
assertNotContains(shellLegacyFirstTuple, '"/ricerca-legale"', 'shell legacy-first senza ricerca legale exact')
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
assertContains(reactShellBlueprint, '"/preventivi/wizard"', 'shell consente preventivo guidato react')
assertNotContains(reactShellBlueprint, 'lower == "/compensi-forensi" or lower.startswith("/compensi-forensi/")', 'shell non blocca exact compensi forensi')
assertNotContains(reactShellBlueprint, 'lower == "/tariffario" or lower.startswith("/tariffario/")', 'shell non blocca exact tariffario')
assertContains(reactShellBlueprint, 'lower.startswith("/compensi-forensi/")', 'shell protegge nested compensi forensi')
assertContains(reactShellBlueprint, 'lower.startswith("/tariffario/")', 'shell protegge nested tariffario')
assertContains(reactShellBlueprint, 'lower == "/template-atti/nuovo"', 'shell protegge nuovo template atti legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/template-atti/") and lower != "/template-atti/catalogo"', 'shell protegge nested template atti legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/redazione-atti/")', 'shell protegge nested redazione atti legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/giurisprudenza/")', 'shell protegge nested giurisprudenza legacy')
assertContains(reactShellBlueprint, 'lower.startswith("/legal-intelligence/") and lower not in {', 'shell protegge nested legal intelligence legacy')
assertContains(reactShellBlueprint, '"/legal-intelligence/news"', 'shell consente legal intelligence news')
assertContains(reactShellBlueprint, '"/legal-intelligence/mediazione"', 'shell consente legal intelligence mediazione')
assertContains(reactShellBlueprint, 'lower.startswith("/ricerca-legale/")', 'shell protegge nested ricerca legale legacy')
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
  ['CompensiForensiPage', compensiForensiPage],
  ['TariffarioPage', tariffarioPage],
  ['TemplateAttiPage', templateAttiPage],
  ['RedazioneAttiPage', redazioneAttiPage],
]) {
  assertNoBootstrapClass(source, `${label} senza classi Bootstrap`)
  assertNotContains(source, 'href="#"', `${label} senza href placeholder`)
  assertNotContains(source, 'mockResults', `${label} senza mockResults`)
  assertNotContains(source, 'mock_fallback: true', `${label} senza mock fallback true`)
  assertNoFetchPost(source, `${label} senza fetch POST`)
  assertNoPasswordUseState(source, `${label} senza password in useState`)
  assertNoClientStorage(source, `${label} senza storage client per dati amministrativi`)
}
assertNoBootstrapClass(preventivoWizardPage, 'PreventivoWizardPage senza classi Bootstrap')
assertNotContains(preventivoWizardPage, 'href="#"', 'PreventivoWizardPage senza href placeholder')
assertNotContains(preventivoWizardPage, 'mockResults', 'PreventivoWizardPage senza mockResults')
assertNotContains(preventivoWizardPage, 'mock_fallback: true', 'PreventivoWizardPage senza mock fallback true')
assertNotContains(preventivoWizardPage, 'alert(', 'PreventivoWizardPage senza alert')
assertNoFetchPost(preventivoWizardPage, 'PreventivoWizardPage senza fetch POST')
assertNoPasswordUseState(preventivoWizardPage, 'PreventivoWizardPage senza password in useState')
assertNoSensitivePayloadWords(preventivoWizardPage, 'PreventivoWizardPage senza campi riservati')
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
  ['react_preventivo_wizard_bridge', preventivoWizardBridge],
  ['react_compensi_forensi_bridge', compensiForensiBridge],
  ['react_tariffario_bridge', tariffarioBridge],
  ['react_template_atti_bridge', templateAttiBridge],
  ['react_redazione_atti_bridge', redazioneAttiBridge],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
  ['preventivoWizardData', preventivoWizardData],
  ['preventivoWizardUtils', preventivoWizardUtils],
  ['compensiForensiData', compensiForensiData],
  ['tariffarioData', tariffarioData],
  ['templateAttiData', templateAttiData],
  ['redazioneAttiData', redazioneAttiData],
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
assertNoFetchPost(preventivoWizardPage, 'PreventivoWizardPage senza fetch POST')
assertNoFetchPost(templateAttiPage, 'TemplateAttiPage senza fetch POST')
assertNoFetchPost(redazioneAttiPage, 'RedazioneAttiPage senza fetch POST')
assertNoFetchPost(fatturazioneData, 'fatturazioneData senza fetch POST')
assertNoFetchPost(incassiPagamentiData, 'incassiPagamentiData senza fetch POST')
assertNoFetchPost(preventiviData, 'preventiviData senza fetch POST')
assertNoFetchPost(preventivoWizardData, 'preventivoWizardData senza fetch POST')
assertNoFetchPost(templateAttiData, 'templateAttiData senza fetch POST')
assertNoFetchPost(redazioneAttiData, 'redazioneAttiData senza fetch POST')
for (const [label, source] of [
  ['react_backup_bridge', backupBridge],
  ['react_sito_studio_bridge', sitoStudioBridge],
  ['react_studio_bridge', studioBridge],
  ['react_amministrazione_bridge', amministrazioneBridge],
  ['react_fatturazione_bridge', fatturazioneBridge],
  ['react_incassi_pagamenti_bridge', incassiPagamentiBridge],
  ['react_preventivi_bridge', preventiviBridge],
  ['react_preventivo_wizard_bridge', preventivoWizardBridge],
  ['react_compensi_forensi_bridge', compensiForensiBridge],
  ['react_tariffario_bridge', tariffarioBridge],
  ['react_template_atti_bridge', templateAttiBridge],
  ['react_redazione_atti_bridge', redazioneAttiBridge],
  ['backupData', backupData],
  ['sitoStudioData', sitoStudioData],
  ['studioData', studioData],
  ['amministrazioneData', amministrazioneData],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
  ['preventivoWizardData', preventivoWizardData],
  ['preventivoWizardUtils', preventivoWizardUtils],
  ['compensiForensiData', compensiForensiData],
  ['tariffarioData', tariffarioData],
  ['templateAttiData', templateAttiData],
  ['redazioneAttiData', redazioneAttiData],
  ['BackupPage', backupPage],
  ['SitoStudioPage', sitoStudioPage],
  ['StudioPage', studioPage],
  ['AmministrazionePage', amministrazionePage],
  ['FatturazionePage', fatturazionePage],
  ['IncassiPagamentiPage', incassiPagamentiPage],
  ['PreventiviPage', preventiviPage],
  ['CompensiForensiPage', compensiForensiPage],
  ['TariffarioPage', tariffarioPage],
  ['TemplateAttiPage', templateAttiPage],
  ['RedazioneAttiPage', redazioneAttiPage],
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
  ['CompensiForensiPage', compensiForensiPage],
  ['TariffarioPage', tariffarioPage],
  ['fatturazioneData', fatturazioneData],
  ['incassiPagamentiData', incassiPagamentiData],
  ['preventiviData', preventiviData],
  ['compensiForensiData', compensiForensiData],
  ['tariffarioData', tariffarioData],
  ['TemplateAttiPage', templateAttiPage],
  ['RedazioneAttiPage', redazioneAttiPage],
  ['templateAttiData', templateAttiData],
  ['redazioneAttiData', redazioneAttiData],
]) {
  assertNoFetchBlob(source, `${label} senza fetch blob`)
  if (!label.includes('Template') && !label.includes('Redazione') && !label.includes('templateAtti') && !label.includes('redazioneAtti')) {
    assertNoFiscalLogic(source, `${label} senza calcolo fiscale canonico`)
  }
}
for (const [label, source] of [
  ['PreventiviPage', preventiviPage],
  ['preventiviData', preventiviData],
  ['CompensiForensiPage', compensiForensiPage],
  ['compensiForensiData', compensiForensiData],
  ['TariffarioPage', tariffarioPage],
  ['tariffarioData', tariffarioData],
]) {
  const sourceWithoutBackendContract = source.replaceAll('dm55_calculation', '')
  assertNotContains(sourceWithoutBackendContract, 'calculate', `${label} senza calculate frontend`)
  assertNotContains(sourceWithoutBackendContract, 'DM55', `${label} senza DM55 frontend`)
  assertNotContains(sourceWithoutBackendContract, 'dm55', `${label} senza dm55 frontend`)
  assertNotContains(sourceWithoutBackendContract, 'Math.round', `${label} senza arrotondamenti economici`)
  assertNotContains(sourceWithoutBackendContract, '.toFixed(', `${label} senza formattazioni economiche calcolate`)
}
for (const [label, source] of [
  ['CompensiForensiPage', compensiForensiPage],
  ['TariffarioPage', tariffarioPage],
  ['TemplateAttiPage', templateAttiPage],
  ['RedazioneAttiPage', redazioneAttiPage],
]) {
  assertNotContains(source, 'style={{', `${label} senza inline style`)
  assertNotContains(source, '#', `${label} senza colori hardcoded`)
  assertNotContains(source, 'dangerouslySetInnerHTML', `${label} senza HTML pericoloso`)
  assertNotContains(source, 'contentEditable', `${label} senza editor inline`)
}
for (const [label, source] of [
  ['TemplateAttiPage', templateAttiPage],
  ['RedazioneAttiPage', redazioneAttiPage],
  ['templateAttiData', templateAttiData],
  ['redazioneAttiData', redazioneAttiData],
  ['react_template_atti_bridge', templateAttiBridge],
  ['react_redazione_atti_bridge', redazioneAttiBridge],
]) {
  assertNotContains(source, 'template_raw', `${label} senza template raw`)
  assertNotContains(source, 'document_raw', `${label} senza document raw`)
  assertNotContains(source, 'html_raw', `${label} senza html raw`)
  assertNotContains(source, 'pdf_raw', `${label} senza pdf raw`)
  assertNotContains(source, 'docx_raw', `${label} senza docx raw`)
  assertNotContains(source, 'templateBody', `${label} senza corpo template React`)
  assertNotContains(source, 'templateHtml', `${label} senza HTML template React`)
  assertNotContains(source, 'documentText', `${label} senza testo documento React`)
  assertNotContains(source, 'generatedText', `${label} senza testo generato React`)
  assertNotContains(source, 'promptAI', `${label} senza prompt AI`)
  assertNotContains(source, 'promptLex', `${label} senza prompt Lex`)
  assertNotContains(source, 'generatePdf', `${label} senza produzione PDF`)
  assertNotContains(source, 'generateDocx', `${label} senza produzione DOCX`)
  assertNotContains(source, 'generateAtto', `${label} senza generazione atto`)
  assertNotContains(source, 'OpenAI', `${label} senza chiamate OpenAI`)
  assertNotContains(source, 'ChatCompletion', `${label} senza chat completion`)
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

const tranche10aFrontendBundle = [
  giurisprudenzaPage,
  giurisprudenzaData,
  legalIntelligencePage,
  legalIntelligenceData,
].join('\n')
const tranche10aFullBundle = [
  tranche10aFrontendBundle,
  giurisprudenzaBridge,
  legalIntelligenceBridge,
].join('\n')

function manifestRoute(route) {
  return (routeManifest.routes ?? []).find((entry) => entry.route === route)
}

function assertManifestRoute(route, status, unlockFromGate) {
  const entry = manifestRoute(route)
  if (!entry || entry.status !== status || entry.unlockFromGate !== unlockFromGate) {
    throw new Error(`route manifest 10A: ${route} deve essere ${status} con unlockFromGate=${unlockFromGate}`)
  }
}

assertContains(app, 'GiurisprudenzaPage', 'App.tsx contiene GiurisprudenzaPage')
assertContains(app, 'LegalIntelligencePage', 'App.tsx contiene LegalIntelligencePage')
assertContains(app, 'isGiurisprudenzaPage', 'App.tsx contiene isGiurisprudenzaPage')
assertContains(app, 'isLegalIntelligencePage', 'App.tsx contiene isLegalIntelligencePage')
assertContains(giurisprudenzaPage, 'getGiurisprudenzaPage', 'GiurisprudenzaPage usa getGiurisprudenzaPage')
assertContains(legalIntelligencePage, 'getLegalIntelligencePage', 'LegalIntelligencePage usa getLegalIntelligencePage')
assertContains(legalIntelligencePage, 'getLegalIntelligenceNewsPage', 'LegalIntelligencePage usa getLegalIntelligenceNewsPage')
assertContains(legalIntelligencePage, 'getLegalIntelligenceMediazionePage', 'LegalIntelligencePage usa getLegalIntelligenceMediazionePage')
assertContains(legalIntelligencePage, 'getRicercaLegalePage', 'LegalIntelligencePage usa getRicercaLegalePage')
assertNoFetchPost(giurisprudenzaPage, 'GiurisprudenzaPage')
assertNoFetchPost(legalIntelligencePage, 'LegalIntelligencePage')
assertNoFetchBlob(giurisprudenzaPage, 'GiurisprudenzaPage')
assertNoFetchBlob(legalIntelligencePage, 'LegalIntelligencePage')
assertNotContains(giurisprudenzaPage, 'dangerouslySetInnerHTML', 'GiurisprudenzaPage senza HTML non sicuro')
assertNotContains(legalIntelligencePage, 'dangerouslySetInnerHTML', 'LegalIntelligencePage senza HTML non sicuro')
assertNotContains(giurisprudenzaPage, 'contentEditable', 'GiurisprudenzaPage senza editor inline')
assertNotContains(legalIntelligencePage, 'contentEditable', 'LegalIntelligencePage senza editor inline')
assertContains(giurisprudenzaData, '/api/v1/ui/giurisprudenza', 'giurisprudenzaData endpoint')
assertContains(legalIntelligenceData, '/api/v1/ui/legal-intelligence', 'legalIntelligenceData dashboard endpoint')
assertContains(legalIntelligenceData, '/api/v1/ui/legal-intelligence/news', 'legalIntelligenceData news endpoint')
assertContains(legalIntelligenceData, '/api/v1/ui/legal-intelligence/mediazione', 'legalIntelligenceData mediazione endpoint')
assertContains(legalIntelligenceData, '/api/v1/ui/ricerca-legale', 'legalIntelligenceData ricerca legale endpoint')
assertContains(apiBridge, '@api_v1_react.get("/giurisprudenza")', 'API React giurisprudenza')
assertContains(apiBridge, '@api_v1_react.get("/legal-intelligence")', 'API React legal intelligence')
assertContains(apiBridge, '@api_v1_react.get("/legal-intelligence/news")', 'API React legal intelligence news')
assertContains(apiBridge, '@api_v1_react.get("/legal-intelligence/mediazione")', 'API React legal intelligence mediazione')
assertContains(apiBridge, '@api_v1_react.get("/ricerca-legale")', 'API React ricerca legale')

const legacyPrefixes10a = pythonTupleSource(reactRouteGate, '_LEGACY_OPERATIONAL_PREFIXES')
assertNotContains(legacyPrefixes10a, '"/giurisprudenza"', 'gate senza /giurisprudenza nei legacy prefix')
assertNotContains(legacyPrefixes10a, '"/legal-intelligence"', 'gate senza /legal-intelligence nei legacy prefix')
assertNotContains(legacyPrefixes10a, '"/ricerca-legale"', 'gate senza /ricerca-legale nei legacy prefix')
for (const snippet of [
  'lower.startswith("/giurisprudenza/")',
  'lower.startswith("/legal-intelligence/") and lower not in {',
  '"/legal-intelligence/news",',
  '"/legal-intelligence/mediazione",',
  'lower.startswith("/ricerca-legale/")',
  'lower == "/checklist" or lower.startswith("/checklist/")',
  'lower == "/deposito/checklist" or lower.startswith("/deposito/checklist/")',
]) {
  assertContains(reactRouteGate, snippet, `protezione route gate ${snippet}`)
}
assertManifestRoute('/giurisprudenza', 'react_bridge', true)
assertManifestRoute('/giurisprudenza/nuova', 'legacy_operational', false)
assertManifestRoute('/giurisprudenza/*', 'legacy_operational', false)
assertManifestRoute('/legal-intelligence', 'react_bridge', true)
assertManifestRoute('/legal-intelligence/news', 'react_bridge', true)
assertManifestRoute('/legal-intelligence/mediazione', 'react_bridge', true)
assertManifestRoute('/legal-intelligence/*', 'legacy_operational', false)
assertManifestRoute('/ricerca-legale', 'react_bridge', true)
assertManifestRoute('/ricerca-legale/*', 'legacy_operational', false)
assertManifestRoute('/deposito/checklist', 'legacy_operational', false)

for (const [source, label] of [
  [giurisprudenzaPage, 'GiurisprudenzaPage'],
  [legalIntelligencePage, 'LegalIntelligencePage'],
]) {
  assertNoBootstrapClass(source, label)
  assertNotContains(source, 'href="#"', `${label} senza href vuoto`)
  assertNotContains(source, 'style={{', `${label} senza stili inline`)
  if (/#[0-9A-Fa-f]{3,8}\b/.test(source)) {
    throw new Error(`${label}: contiene colore hex hardcoded`)
  }
}
for (const [source, label] of [
  [giurisprudenzaData, 'giurisprudenzaData'],
  [legalIntelligenceData, 'legalIntelligenceData'],
]) {
  assertNoFetchPost(source, label)
  assertNoFetchBlob(source, label)
  assertNoClientStorage(source, label)
  assertNoSensitivePayloadWords(source, label)
}
assertNotContains(tranche10aFrontendBundle, 'mockResults', '10A senza mockResults')
assertNotContains(tranche10aFrontendBundle, 'mock_fallback: true', '10A senza mock fallback frontend')
for (const word of ['prompt_raw', 'ai_output_raw', 'document_raw', 'html_raw', 'pdf_raw', 'docx_raw']) {
  assertNotContains(tranche10aFullBundle, word, `10A senza campo ${word}`)
}
for (const term of ['fetch("http', "fetch('http", 'requests.get', 'requests.post', 'httpx.', 'urllib.request', 'BeautifulSoup', 'bs4', 'selenium', 'playwright', 'external_fetch: true']) {
  assertNotContains(tranche10aFullBundle, term, `10A senza chiamata esterna ${term}`)
}
for (const term of ['generateMassima', 'generateCitation', 'generateSummary', 'generateOrientamento', 'classifyCase', 'classifySentenza', 'autoClassifica', 'ai_generation: true', 'sintesiGenerata', 'massimaGenerata', 'citazioneGenerata', 'orientamentoGenerato', 'MOCK_NEWS', 'DEMO_NEWS', 'SAMPLE_SENTENZA', 'MOCK_SENTENZA']) {
  assertNotContains(tranche10aFullBundle, term, `10A senza generazione ${term}`)
}
for (const term of ['rawHtml', 'rawText', 'documentText', 'documentHtml', 'sentenzaIntegrale', 'testoIntegrale', 'provvedimentoIntegrale', 'new Blob', 'URL.createObjectURL', 'FileReader', 'application/pdf']) {
  assertNotContains(tranche10aFullBundle, term, `10A senza documento raw ${term}`)
}
assertContains(impeccableOpenDesignCss, '--iu-od-source-gap', 'token source gap')
assertContains(impeccableOpenDesignCss, '.iu-od-source-card', 'utility source card')
assertContains(impeccableOpenDesignCss, '.iu-od-inference-warning', 'utility inference warning')
assertContains(openDesign, 'openDesignLegalKnowledgeSurface', 'contratto Open Design legal knowledge')
assertContains(giurisprudenzaCss, '.iu-legal-evidence-row', 'stili fonte/inferenza giurisprudenza')
assertContains(legalIntelligenceCss, '.iu-li-evidence-row', 'stili fonte/inferenza legal intelligence')
assertContains(runSafeReactMigration, "--tranche=10a", 'runner supporta tranche 10A')
assertContains(tranche10aGate, '/giurisprudenza', 'gate test 10A giurisprudenza')
assertContains(tranche10aSecrets, 'tranche-10a-secrets.md', 'check segreti 10A report')
assertContains(tranche10aNoExternalFetch, 'tranche-10a-no-external-fetch.md', 'check external 10A report')
assertContains(tranche10aNoAiGeneration, 'tranche-10a-no-ai-generation.md', 'check AI 10A report')
assertContains(tranche10aNoDocumentRaw, 'tranche-10a-no-document-raw.md', 'check document raw 10A report')
assertContains(tranche10aOpenDesign, 'tranche-10a-open-design-check.md', 'check Open Design 10A report')

console.log('Contratti React verificati.')
