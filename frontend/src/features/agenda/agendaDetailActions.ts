import type { AgendaEvent } from '../../agendaData'

/**
 * Dettaglio operativo agenda: attività proposte eseguibili e ordine del carosello "In evidenza".
 * Le attività nascono dalla riga "Attività per l'avvocato" scritta da PEC/documenti; ogni passo
 * porta direttamente all'azione (fonte, fascicolo, deposito, cliente, notifica, termine).
 */

export const AGENDA_ACTIVITY_PREFIX = /^attivit[àa] per l['’]avvocato\s*:\s*/i

export type AgendaProposedStep = {
  id: 'fonte' | 'quando' | 'fascicolo' | 'atti' | 'cliente' | 'notifica' | 'termine'
  label: string
  actionLabel: string
  href?: string
}

export function agendaActivityText(event: AgendaEvent): string {
  const line = event.detailLines.find((item) => AGENDA_ACTIVITY_PREFIX.test(item.trim()))
  return line ? line.trim().replace(AGENDA_ACTIVITY_PREFIX, '').trim() : ''
}

export function agendaProposedSteps(
  event: AgendaEvent,
  activity: string,
  { editHref, isDeadline, clientReminderHref }: { editHref: string; isDeadline: boolean; clientReminderHref: string },
): AgendaProposedStep[] {
  const text = (activity || `${event.legalLabel} ${event.title}`).toLocaleLowerCase('it-IT')
  const steps: AgendaProposedStep[] = []
  const add = (step: AgendaProposedStep) => {
    if (!steps.some((item) => item.id === step.id)) steps.push(step)
  }
  if (event.sourceHref && (/provvediment|decreto|ordinanza|verbale|comunicazione|pec|fonte/.test(text) || !activity)) {
    add({ id: 'fonte', label: 'Leggi il provvedimento o la comunicazione che ha generato l’impegno', actionLabel: 'Visualizza fonte' })
  }
  if (/\bdata\b|\bora\b|orario|rinvi/.test(text)) {
    add({ id: 'quando', label: 'Verifica data e ora; se sono cambiate aggiorna l’impegno', actionLabel: isDeadline ? 'Apri scadenza' : 'Aggiorna data e ora', href: isDeadline ? editHref : `${editHref}#quando` })
  }
  if (event.matterId && /fascicol|pratica|\brg\b|udienza/.test(text)) {
    add({ id: 'fascicolo', label: 'Controlla il fascicolo collegato', actionLabel: 'Apri fascicolo', href: `/fascicoli/${encodeURIComponent(event.matterId)}` })
  }
  if (event.matterId && /\bnote\b|\batt[io]\b|memori|deposit|127-ter/.test(text)) {
    add({ id: 'atti', label: 'Predisponi note o atti e prepara il deposito', actionLabel: 'Prepara deposito', href: `/fascicoli/${encodeURIComponent(event.matterId)}/deposito/prepara` })
  }
  if (/comunicazion|cliente|avvis|promemoria/.test(text)) {
    add({ id: 'cliente', label: 'Informa il cliente o invia le comunicazioni richieste', actionLabel: 'Avvisa cliente', href: clientReminderHref })
  }
  if (event.matterId && /notific/.test(text)) {
    add({ id: 'notifica', label: 'Prepara la notifica collegata', actionLabel: 'Prepara notifica', href: `/notifiche-legali?id_fascicolo=${encodeURIComponent(event.matterId)}&fase=notifica` })
  }
  if (/termine|scadenz|giorni/.test(text)) {
    add({ id: 'termine', label: 'Ricalcola il termine e verifica la scadenza', actionLabel: 'Calcola termine', href: '/scadenziario/calcola-termini' })
  }
  return steps
}


export function agendaHighlightStartIndex(events: AgendaEvent[], nextEvent?: AgendaEvent): number {
  if (!events.length) return 0
  const byId = nextEvent ? events.findIndex((event) => event.id === nextEvent.id) : -1
  if (byId >= 0) return byId
  const now = Date.now()
  const upcoming = events.findIndex((event) => !event.completed && new Date(event.start).getTime() >= now)
  return upcoming >= 0 ? upcoming : 0
}
