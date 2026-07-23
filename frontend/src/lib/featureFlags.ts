import { apiJson } from '@/lib/apiClient'

export type FeatureFlagKey =
  | 'features.sentenzaEconomicControl'
  | 'features.legalNotificationPresidia.enabled'
  | 'features.legalNotificationPresidia.primary'
  | 'lex.economicContextTools'
  | 'routes.appV2.dashboard.home'
  | 'routes.appV2.dashboard.regia'
  | 'routes.appV2.search.global'
  | 'routes.appV2.cases.list'
  | 'routes.appV2.cases.detail'
  | 'routes.appV2.cases.create'
  | 'routes.appV2.clients.list'
  | 'routes.appV2.clients.create'
  | 'routes.appV2.clients.detail'
  | 'routes.appV2.contacts.list'
  | 'routes.appV2.contacts.create'
  | 'routes.appV2.comms.deposits'
  | 'routes.appV2.comms.pec'
  | 'routes.appV2.comms.ordinaryMail'
  | 'routes.appV2.comms.messages'
  | 'routes.appV2.comms.newMessage'
  | 'routes.appV2.agenda.calendar'
  | 'routes.appV2.agenda.create'
  | 'routes.appV2.agenda.timesheet'
  | 'routes.appV2.deadlines.list'
  | 'routes.appV2.deadlines.create'
  | 'routes.appV2.deadlines.detail'
  | 'routes.appV2.deadlines.hearingWizard'
  | 'routes.appV2.documents.list'
  | 'routes.appV2.documents.templates'
  | 'routes.appV2.documents.templateEditor'
  | 'routes.appV2.documents.drafting'
  | 'routes.appV2.documents.editor'
  | 'routes.appV2.documents.uploadClassification'
  | 'routes.appV2.documents.checklist'
  | 'routes.appV2.legalResearch.home'
  | 'routes.appV2.legalResearch.giurisprudenza'
  | 'routes.appV2.telematico.center'
  | 'routes.appV2.telematico.surface'
  | 'routes.appV2.studio.home'
  | 'routes.appV2.studio.statistics'
  | 'routes.appV2.studio.modules'
  | 'routes.appV2.studio.site'
  | 'routes.appV2.studio.siteBuilder'
  | 'routes.appV2.studio.siteDrafting'
  | 'routes.appV2.admin.home'
  | 'routes.appV2.admin.users'
  | 'routes.appV2.admin.roles'
  | 'routes.appV2.admin.auditLogs'
  | 'routes.appV2.admin.database'
  | 'routes.appV2.admin.privacyRegistry'
  | 'routes.appV2.settings.studio'
  | 'routes.appV2.settings.payments'
  | 'routes.appV2.settings.notifications'
  | 'routes.appV2.settings.backup'
  | 'routes.appV2.settings.calendarSync'
  | 'routes.appV2.settings.sdi'
  | 'routes.appV2.billing.invoices'
  | 'routes.appV2.billing.payments'
  | 'routes.appV2.billing.quotes'
  | 'routes.appV2.billing.compensi'
  | 'routes.appV2.billing.tariffario'
  | 'routes.appV2.notifications.mobilePush'
  | 'lex.legalSkills.enabled'
  | 'lex.legalSkills.trustLayer'
  | 'lex.legalSkills.customSkills'
  | 'lex.legalSkills.scheduledAgents'
  | 'lex.autonomousLearning'
  | 'lex.workflowAgents.enabled'
  | 'lex.workflowAgents.writeActions'
  | 'lex.workflowAgents.scheduledRuns'
  | 'lex.dailyPlan.enabled'
  | 'lex.dailyPlan.scheduledRuns'
  | 'lex.dailyPlan.writeProposals'
  | 'lex.procedureCompletion.enabled'
  | 'lex.procedureCompletion.voiceRead.enabled'
  | 'lex.procedureCompletion.voiceRead.localOnly'
  | 'routes.appV2.procedureCompletion.home'
  | 'routes.appV2.legalSkills.catalog'
  | 'routes.appV2.legalSkills.profile'
  | 'routes.appV2.legalSkills.run'
  | 'routes.appV2.legalSkills.reviewQueue'
  | 'routes.appV2.legalSkills.promptLibrary'
  | 'routes.appV2.legalSkills.pathways'
  | 'routes.appV2.workflowAgents.home'
  | 'routes.appV2.workflowAgents.reviewQueue'
  | 'routes.appV2.dailyPlan.home'
  | 'routes.appV2.dailyPlan.reviewQueue'
  | 'routes.appV2.clientPortal.enabled'
  | 'routes.appV2.clientPortal.notifications'
  | 'routes.appV2.clientPortal.webPush'
  | 'routes.appV2.clientPortal.videoCalls'
  | 'routes.appV2.clientPortal.signatures'
  | 'routes.appV2.docsPanel'
  | 'routes.appV2.commsDeposits'
  | 'routes.appV2.uploadClassification'
  | 'routes.appV2.deadlines'
  | 'routes.appV2.agenda'
  | 'routes.appV2.caseFiles'
  | 'notifications.mobilePush'

type FeatureFlagsPayload = {
  ok: boolean
  flags: Partial<Record<FeatureFlagKey, boolean>>
}

const emptyFeatureFlags: FeatureFlagsPayload = { ok: false, flags: {} }
let featureFlagsCache: Partial<Record<FeatureFlagKey, boolean>> | null = null

const featureFlagAliases: Partial<Record<FeatureFlagKey, FeatureFlagKey>> = {
  'routes.appV2.docsPanel': 'routes.appV2.documents.list',
  'routes.appV2.commsDeposits': 'routes.appV2.comms.deposits',
  'routes.appV2.uploadClassification': 'routes.appV2.documents.uploadClassification',
  'routes.appV2.deadlines': 'routes.appV2.deadlines.list',
  'routes.appV2.agenda': 'routes.appV2.agenda.calendar',
  'routes.appV2.caseFiles': 'routes.appV2.cases.list',
  'notifications.mobilePush': 'routes.appV2.notifications.mobilePush',
}

const appV2RouteFlagRules: Array<[RegExp, FeatureFlagKey]> = [
  [/^\/fascicoli\/[^/]+\/documenti\/[^/]+\/editor$/, 'routes.appV2.documents.editor'],
  [/^\/fascicoli\/nuovo(?:\/|$)/, 'routes.appV2.cases.create'],
  [/^\/fascicoli\/archivio(?:\/|$)/, 'routes.appV2.cases.list'],
  [/^\/fascicoli\/[^/]+(?:\/|$)/, 'routes.appV2.cases.detail'],
  [/^\/fascicoli(?:\/|$)/, 'routes.appV2.cases.list'],
  [/^\/clienti\/nuovo(?:\/|$)/, 'routes.appV2.clients.create'],
  [/^\/clienti\/[^/]+\/modifica$/, 'routes.appV2.clients.create'],
  [/^\/clienti\/[^/]+(?:\/|$)/, 'routes.appV2.clients.detail'],
  [/^\/clienti(?:\/|$)/, 'routes.appV2.clients.list'],
  [/^\/soggetti\/nuovo(?:\/|$)/, 'routes.appV2.contacts.create'],
  [/^\/soggetti\/[^/]+\/modifica$/, 'routes.appV2.contacts.create'],
  [/^\/soggetti(?:\/|$)/, 'routes.appV2.contacts.list'],
  [/^\/cartelle-condivise(?:\/|$)/, 'routes.appV2.clients.detail'],
  [/^\/email-ordinaria\/scrivi(?:\/|$)/, 'routes.appV2.comms.ordinaryMail'],
  [/^\/email-ordinaria(?:\/|$)/, 'routes.appV2.comms.ordinaryMail'],
  [/^\/email\/scrivi(?:\/|$)/, 'routes.appV2.comms.pec'],
  [/^\/email(?:\/|$)/, 'routes.appV2.comms.pec'],
  [/^\/notifiche-legali(?:\/|$)/, 'routes.appV2.comms.pec'],
  [/^\/messaggi\/nuovo(?:\/|$)/, 'routes.appV2.comms.newMessage'],
  [/^\/messaggi(?:\/|$)/, 'routes.appV2.comms.messages'],
  [/^\/comunicazioni(?:\/|$)/, 'routes.appV2.comms.deposits'],
  [/^\/agenda\/nuovo(?:\/|$)/, 'routes.appV2.agenda.create'],
  [/^\/agenda(?:\/|$)/, 'routes.appV2.agenda.calendar'],
  [/^\/timesheet(?:\/|$)/, 'routes.appV2.agenda.timesheet'],
  [/^\/scadenziario\/nuova(?:\/|$)/, 'routes.appV2.deadlines.create'],
  [/^\/scadenziario\/[^/]+\/modifica$/, 'routes.appV2.deadlines.detail'],
  [/^\/scadenziario\/[^/]+(?:\/|$)/, 'routes.appV2.deadlines.detail'],
  [/^\/scadenziario(?:\/|$)/, 'routes.appV2.deadlines.list'],
  [/^\/wizard-pro(?:\/|$)/, 'routes.appV2.deadlines.hearingWizard'],
  [/^\/documenti(?:\/|$)/, 'routes.appV2.documents.list'],
  [/^\/template-atti\/nuovo(?:\/|$)/, 'routes.appV2.documents.templateEditor'],
  [/^\/template-atti(?:\/|$)/, 'routes.appV2.documents.templates'],
  [/^\/redazione-atti(?:\/|$)/, 'routes.appV2.documents.drafting'],
  [/^\/(?:checklist|deposito\/checklist)(?:\/|$)/, 'routes.appV2.documents.checklist'],
  [/^\/giurisprudenza(?:\/|$)/, 'routes.appV2.legalResearch.giurisprudenza'],
  [/^\/(?:legal-intelligence|ricerca-legale)(?:\/|$)/, 'routes.appV2.legalResearch.home'],
  [/^\/(?:global-search|ricerca-studio|cerca)(?:\/|$)/, 'routes.appV2.search.global'],
  [/^\/(?:telematico|servizi-telematici)(?:\/|$)/, 'routes.appV2.telematico.center'],
  [/^\/(?:polisweb|pst|pdp|pat|ptt|sigit|tribunali|guida\/firma-digitale|portali)(?:\/|$)/, 'routes.appV2.telematico.surface'],
  [/^\/studio(?:\/|$)/, 'routes.appV2.studio.home'],
  [/^\/statistiche(?:\/|$)/, 'routes.appV2.studio.statistics'],
  [/^\/(?:strumenti-legali|strumenti-operativi|applicazioni)(?:\/|$)/, 'routes.appV2.studio.modules'],
  [/^\/sito-studio\/builder(?:\/|$)/, 'routes.appV2.studio.siteBuilder'],
  [/^\/sito-studio\/redazione-ai(?:\/|$)/, 'routes.appV2.studio.siteDrafting'],
  [/^\/sito-studio(?:\/|$)/, 'routes.appV2.studio.site'],
  [/^\/amministrazione(?:\/|$)/, 'routes.appV2.admin.home'],
  [/^\/utenti(?:\/|$)/, 'routes.appV2.admin.users'],
  [/^\/profili(?:\/|$)/, 'routes.appV2.admin.roles'],
  [/^\/(?:audit|registro-attivita)(?:\/|$)/, 'routes.appV2.admin.auditLogs'],
  [/^\/(?:admin\/database|database)(?:\/|$)/, 'routes.appV2.admin.database'],
  [/^\/(?:privacy\/registro|registro-gdpr)(?:\/|$)/, 'routes.appV2.admin.privacyRegistry'],
  [/^\/impostazioni\/pagamenti(?:\/|$)/, 'routes.appV2.settings.payments'],
  [/^\/(?:impostazioni\/sdi|impostazioni\/canali-sdi)(?:\/|$)/, 'routes.appV2.settings.sdi'],
  [/^\/(?:notifiche|notifiche-whatsapp)(?:\/|$)/, 'routes.appV2.settings.notifications'],
  [/^\/backup(?:\/|$)/, 'routes.appV2.settings.backup'],
  [/^\/(?:impostazioni\/calendario|sincronizzazione-calendari)(?:\/|$)/, 'routes.appV2.settings.calendarSync'],
  [/^\/(?:impostazioni|impostazioni-studio)(?:\/|$)/, 'routes.appV2.settings.studio'],
  [/^\/fatturazione(?:\/|$)/, 'routes.appV2.billing.invoices'],
  [/^\/incassi-pagamenti(?:\/|$)/, 'routes.appV2.billing.payments'],
  [/^\/(?:preventivi|preventivi\/wizard)(?:\/|$)/, 'routes.appV2.billing.quotes'],
  [/^\/compensi-forensi(?:\/|$)/, 'routes.appV2.billing.compensi'],
  [/^\/tariffario(?:\/|$)/, 'routes.appV2.billing.tariffario'],
  [/^\/legal-skills\/percorsi(?:\/|$)/, 'routes.appV2.legalSkills.pathways'],
  [/^\/legal-skills\/prompt(?:\/|$)/, 'routes.appV2.legalSkills.promptLibrary'],
  [/^\/legal-skills\/profile(?:\/|$)/, 'routes.appV2.legalSkills.profile'],
  [/^\/legal-skills\/(?:run|packs\/[^/]+\/skills\/[^/]+\/run)(?:\/|$)/, 'routes.appV2.legalSkills.run'],
    [/^\/legal-skills\/(?:runs|review|review-queue)(?:\/|$)/, 'routes.appV2.legalSkills.reviewQueue'],
  [/^\/legal-skills(?:\/|$)/, 'routes.appV2.legalSkills.catalog'],
  [/^\/procedure-completion(?:\/|$)/, 'routes.appV2.procedureCompletion.home'],
  [/^\/workflow-agents\/(?:runs|approvals)(?:\/|$)/, 'routes.appV2.workflowAgents.reviewQueue'],
  [/^\/(?:workflow-agents|regia-agentica)(?:\/|$)/, 'routes.appV2.workflowAgents.home'],
  [/^\/oggi(?:\/|$)/, 'routes.appV2.dailyPlan.home'],
  [/^\/app\/portale-clienti(?:\/|$)/, 'routes.appV2.clientPortal.enabled'],
  [/^\/portale-cliente(?:\/|$)/, 'routes.appV2.clientPortal.enabled'],
  [/^\/(?:workspace-intelligente|regia-operativa|app\/regia)(?:\/|$)/, 'routes.appV2.dashboard.regia'],
  [/^\/app\/fascicoli(?:\/|$)/, 'routes.appV2.cases.list'],
  [/^\/app\/anagrafiche(?:\/|$)/, 'routes.appV2.clients.list'],
  [/^\/app\/agenda(?:\/|$)/, 'routes.appV2.agenda.calendar'],
  [/^\/app\/mandato(?:\/|$)/, 'routes.appV2.billing.quotes'],
  [/^\/app\/documenti(?:\/|$)/, 'routes.appV2.documents.list'],
  [/^\/app\/telematico(?:\/|$)/, 'routes.appV2.telematico.center'],
  [/^\/app\/comunicazioni(?:\/|$)/, 'routes.appV2.comms.deposits'],
  [/^\/app\/lex(?:\/|$)/, 'routes.appV2.legalResearch.home'],
  [/^\/app\/legal-skills(?:\/|$)/, 'routes.appV2.legalSkills.catalog'],
  [/^\/app\/amministrazione(?:\/|$)/, 'routes.appV2.admin.home'],
  [/^\/app\/impostazioni(?:\/|$)/, 'routes.appV2.settings.studio'],
  [/^\/(?:app)?$/, 'routes.appV2.dashboard.home'],
]

function bootstrapFlags(): Partial<Record<FeatureFlagKey, boolean>> {
  if (typeof document === 'undefined') return {}
  const element = document.getElementById('iusentra-react-bootstrap')
  if (!element?.textContent) return {}
  try {
    const parsed = JSON.parse(element.textContent) as { featureFlags?: Partial<Record<FeatureFlagKey, boolean>> }
    return parsed.featureFlags && typeof parsed.featureFlags === 'object' ? parsed.featureFlags : {}
  } catch {
    return {}
  }
}

function canonicalFeatureFlag(flag: FeatureFlagKey): FeatureFlagKey {
  return featureFlagAliases[flag] || flag
}

function normaliseAppV2Path(path: string): string {
  const raw = String(path || '/').split('?')[0]?.split('#')[0]?.trim() || '/'
  const clean = `/${raw.replace(/^\/+|\/+$/g, '')}`.toLowerCase()
  if (clean === '/app-v2') return '/'
  if (clean.startsWith('/app-v2/')) return clean.replace('/app-v2', '').replace(/\/+$/g, '') || '/'
  return clean.replace(/\/+$/g, '') || '/'
}

export async function loadFeatureFlags(): Promise<Partial<Record<FeatureFlagKey, boolean>>> {
  if (featureFlagsCache) return featureFlagsCache
  const initial = bootstrapFlags()
  if (Object.keys(initial).length > 0) {
    featureFlagsCache = initial
    return featureFlagsCache
  }
  const payload = await apiJson<FeatureFlagsPayload>('/api/v1/ui/feature-flags', emptyFeatureFlags)
  featureFlagsCache = payload.flags || {}
  return featureFlagsCache
}

export async function isFeatureFlagEnabled(flag: FeatureFlagKey): Promise<boolean> {
  const flags = await loadFeatureFlags()
  const canonical = canonicalFeatureFlag(flag)
  return flags[canonical] === true || flags[flag] === true
}

export function isFeatureFlagEnabledSync(flag: FeatureFlagKey): boolean {
  const flags = featureFlagsCache || bootstrapFlags()
  const canonical = canonicalFeatureFlag(flag)
  return flags[canonical] === true || flags[flag] === true
}

export function appV2FeatureFlagForPath(path: string): FeatureFlagKey | null {
  const clean = normaliseAppV2Path(path)
  const match = appV2RouteFlagRules.find(([pattern]) => pattern.test(clean))
  return match?.[1] || null
}
