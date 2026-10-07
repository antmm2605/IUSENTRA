const WORK_ROUTES = /^\/(?:agenda|fascicoli|clienti|soggetti|scadenziario|wizard-pro|messaggi|email|email-ordinaria|notifiche-legali|timesheet|global-search|workspace-intelligente|oggi|fatturazione|incassi-pagamenti|lex-operativo|preventivi|compensi-forensi|tariffario|prima-nota|studio|documenti|statistiche|ricerca-legale|legal-skills|workflow-agents|giurisprudenza|strumenti-legali|strumenti-operativi|strumenti-documentali|impostazioni|amministrazione|utenti|profili|backup|audit|registro-attivita|sito-studio|cartelle-condivise|privacy|editor-professionale|redazione-atti|template-atti)(?:\/|$)/
export function workWindowUrl(href: string, origin: string): URL | null {
  try {
    const url = new URL(href, origin)
    if (url.origin !== origin || url.username || url.password || (url.pathname !== '/' && !WORK_ROUTES.test(url.pathname))) return null
    if (/\/(?:elimina|archivia|stato|sposta|logout|export\.ics)(?:\/|$)/.test(url.pathname)) return null
    if (/^\/email(?:-ordinaria)?\/?$/.test(url.pathname) && !url.searchParams.get('id') && !url.searchParams.get('audit_id')) {
      url.searchParams.set('view', 'mailbox')
    }
    url.searchParams.set('embed', 'source')
    return url
  } catch { return null }
}
