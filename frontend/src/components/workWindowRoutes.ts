const WORK_ROUTES = /^\/(?:agenda|fascicoli|clienti|soggetti|scadenziario|wizard-pro|messaggi|email|email-ordinaria|notifiche-legali|timesheet|global-search|workspace-intelligente|oggi|fatturazione|incassi-pagamenti|lex-operativo|lex-apprendimento|preventivi|compensi-forensi|tariffario|prima-nota|studio|documenti|statistiche|ricerca-legale|legal-skills|workflow-agents|giurisprudenza|strumenti-legali|strumenti-operativi|strumenti-documentali|applicazioni|recupero-crediti|impostazioni|amministrazione|utenti|profilo|profili|backup|audit|registro-attivita|sito-studio|cartelle-condivise|privacy|editor-professionale|redazione-atti|template-atti)(?:\/|$)/
export function workWindowUrl(href: string, origin: string): URL | null {
  try {
    const url = new URL(href, origin)
    const shellPage = /^(?:\/(?:crm|telematico|polisWeb|pdp|pat|sigit|tribunali|importa-pratiche)\/?|\/deposito\/checklist\/?|\/guida\/firma-digitale\/?|\/admin\/database\/?|\/app\/portale-clienti\/?)(?:$)/.test(url.pathname)
    if (url.origin !== origin || url.username || url.password || (url.pathname !== '/' && !WORK_ROUTES.test(url.pathname) && !shellPage)) return null
    if (/\/(?:elimina|archivia|stato|sposta|logout|export\.ics)(?:\/|$)/.test(url.pathname)) return null
    if (/^\/prima-nota\/(?:esporta|registro-iva)\.csv$/.test(url.pathname)) return null
    if (/^\/email(?:-ordinaria)?\/?$/.test(url.pathname) && !url.searchParams.get('id') && !url.searchParams.get('audit_id')) {
      url.searchParams.set('view', 'mailbox')
    }
    url.searchParams.set('embed', 'source')
    return url
  } catch { return null }
}
