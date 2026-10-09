export const OPERATIONAL_REFRESH_EVENT = 'iusentra:operational-data-updated'
export type OperationalDomain = 'agenda' | 'scadenze' | 'comunicazioni' | 'clienti' | 'soggetti' | 'fascicoli' | 'preventivi' | 'privacy' | 'timesheet' | 'utenti' | 'incassi' | 'fatturazione' | 'sito'
export const operationalDomains: OperationalDomain[] = ['agenda', 'scadenze', 'comunicazioni', 'clienti', 'soggetti', 'fascicoli', 'preventivi', 'privacy', 'timesheet', 'utenti', 'incassi', 'fatturazione', 'sito']
export function publishOperationalRefresh(domains: OperationalDomain[], options: { remote?: boolean } = {}) {
  const distinct = [...new Set(domains)]
  if (distinct.length) window.dispatchEvent(new CustomEvent(OPERATIONAL_REFRESH_EVENT, { detail: { domains: distinct, remote: options.remote === true } }))
}
export function publishMutationRefresh(endpoint: string) {
  let path: string
  try {
    const url = new URL(endpoint, window.location.origin)
    if (url.origin !== window.location.origin) return
    path = url.pathname.replace(/^\/api\/v1(?:\/ui)?/, '')
  } catch { return }
  // Solo i domini di scrittura esplicitamente governati. Firma e invio PEC restano esclusi.
  if (/\/(?:firma|deposito|invia|smtp|simula|calcola|anteprima|valida)(?:\/|$)/.test(path)) return
  const rules: [RegExp, OperationalDomain[]][] = [
    [/^\/sito-studio\/contatti\/\d+\/collega$/, ['sito', 'clienti']],
    [/^\/sito-studio\/prenotazioni\/\d+\/stato$/, ['sito', 'agenda']],
    [/^\/sito-studio(?:\/|$)/, ['sito']],
    [/^\/incassi-pagamenti(?:\/|$)/, ['incassi', 'fatturazione']],
    [/^\/fatturazione(?:\/|$)/, ['fatturazione', 'incassi']],
    [/^\/timesheet(?:\/|$)/, ['timesheet']],
    [/^\/clienti(?:\/|$)/, ['clienti', 'soggetti', 'fascicoli']],
    [/^\/condivisioni(?:\/|$)/, ['clienti', 'fascicoli', 'utenti']],
    [/^\/soggetti(?:\/|$)/, ['soggetti', 'fascicoli']],
    [/^\/agenda(?:\/|$)/, ['agenda', 'scadenze']],
    [/^\/api\/agenda\/[^/]+\/sposta$/, ['agenda', 'scadenze']],
    [/^\/(?:scadenziario|scadenze)(?:\/|$)/, ['scadenze', 'agenda']],
    [/^\/scadenze-rapide\/lette$/, ['scadenze']],
    [/^\/controllo-studio\/(?:pec|comunicazioni)\/lette$/, ['comunicazioni']],
    [/^\/email(?:-ordinaria)?\/(?:bulk-action|sincronizza|[^/]+\/(?:segna-letta|segna-non-letta|cestino|ripristina|elimina))$/, ['comunicazioni']],
    [/^\/privacy(?:\/|$)/, ['privacy']],
    [/^\/(?:utenti|profili)(?:\/|$)/, ['utenti']],
    [/^\/preventivi(?:\/|$)/, ['preventivi']],
  ]
  const domains = rules.find(([pattern]) => pattern.test(path))?.[1]
  if (domains) publishOperationalRefresh(domains)
}
