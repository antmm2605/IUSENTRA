import type { ScadenziarioRow } from '../../scadenziarioData'

export type DeadlineFact = { label: string; value: string; wide?: boolean }
export type DeadlineFactGroup = { id: 'termine' | 'udienza' | 'remoto'; title: string; facts: DeadlineFact[] }

const GENERIC_PLATFORMS = new Set(['altra', 'da verificare', 'incerta', 'sconosciuta'])
const PASSCODE_STOPWORDS = new Set(['esito', 'accesso', 'fiscale', 'destinatario', 'ufficio', 'udienza', 'riunione'])

export function plausiblePasscode(value: string): string {
  const clean = String(value || '').trim()
  if (!clean || !/^[A-Za-z0-9]/.test(clean)) return ''
  const lower = clean.toLowerCase()
  if ([...PASSCODE_STOPWORDS].some((word) => lower.includes(word))) return ''
  const hasDigit = /\d/.test(clean)
  const mixedCase = /[a-z]/.test(clean) && /[A-Z]/.test(clean)
  return hasDigit || (mixedCase && clean.length >= 6) ? clean : ''
}

export function readablePlatform(value: string, hasLink: boolean): string {
  const clean = String(value || '').trim()
  if (!clean) return ''
  if (GENERIC_PLATFORMS.has(clean.toLowerCase())) return hasLink ? 'Altra piattaforma' : ''
  return clean
}

export function readableModeSource(value: string): string {
  const clean = String(value || '').trim()
  if (!clean) return ''
  if (/^testo\/href/i.test(clean)) return 'Testo o link della comunicazione'
  if (/^(profilo|matrice|pipeline)/i.test(clean)) return ''
  return clean
}

export function cleanAccessInfo(value: string): string {
  const parts = String(value || '')
    .split(/(?=\b(?:Piattaforma|ID riunione|Codice di accesso)\s*:)/i)
    .map((part) => part.trim())
    .filter(Boolean)
  const kept = parts.filter((part) => {
    const match = part.match(/^(Piattaforma|ID riunione|Codice di accesso)\s*:\s*(.*)$/i)
    if (!match) return true
    const [, label, raw] = match
    if (/^piattaforma$/i.test(label)) return Boolean(readablePlatform(raw, false))
    if (/^codice di accesso$/i.test(label)) return Boolean(plausiblePasscode(raw))
    return Boolean(raw.trim())
  })
  return kept.join(' ').trim()
}

export function deadlineFactGroups(row: ScadenziarioRow, { notificationPresidio }: { notificationPresidio: boolean }): DeadlineFactGroup[] {
  const hasLink = Boolean(row.remoteHearingUrl)
  const groups: DeadlineFactGroup[] = [
    {
      id: 'termine',
      title: notificationPresidio ? 'Attività' : 'Termine',
      facts: [
        notificationPresidio
          ? { label: 'Visibilità', value: 'Calendario e notifiche operative' }
          : { label: 'Scadenza operativa', value: row.operationalDueLabel || 'Non impostata' },
        { label: 'Responsabile', value: row.ownerLabel || 'Non assegnato' },
        { label: 'Tipo', value: notificationPresidio ? '' : row.typeLabel },
      ],
    },
    {
      id: 'udienza',
      title: 'Udienza e ufficio',
      facts: [
        { label: 'Evento', value: row.sourceEventTypeLabel, wide: true },
        { label: 'Ufficio', value: row.officeLabel },
        { label: 'Modalità udienza', value: row.hearingMode },
        { label: 'Orario udienza', value: row.hearingTime },
        { label: 'Verifica orario', value: row.hearingTimeVerificationRequired ? "L'orario letto non è valido: apri la fonte e registra quello corretto." : '', wide: true },
        { label: 'Fonte modalità', value: readableModeSource(row.hearingModeSource) },
        { label: 'Operatività ufficio', value: row.officeModeLabel },
        { label: 'Patrono ufficio', value: row.officePatronLabel },
        { label: 'Osservanza', value: row.octoberObservanceBlocks ? 'Osservanza bloccante' : '' },
      ],
    },
    {
      id: 'remoto',
      title: 'Collegamento da remoto',
      facts: [
        { label: 'Allegato udienza', value: row.remoteHearingSource },
        { label: 'Piattaforma', value: readablePlatform(row.remoteHearingPlatform, hasLink) },
        { label: 'ID riunione', value: row.remoteHearingMeetingId },
        { label: 'Codice di accesso', value: plausiblePasscode(row.remoteHearingPasscode) },
        { label: 'Controllo link', value: hasLink ? (row.remoteHearingVerified ? 'Verificato sull’allegato' : 'Da controllare sull’allegato') : '' },
        { label: 'Link udienza', value: row.remoteHearingPdfRequired ? 'Da acquisire dal PDF allegato' : '' },
        { label: 'Istruzioni', value: cleanAccessInfo(row.remoteHearingAccessInfo), wide: true },
      ],
    },
  ]
  return groups
    .map((group) => notificationPresidio && group.id !== 'termine'
      ? { ...group, facts: group.facts.filter((fact) => ['Evento', 'Ufficio', 'Operatività ufficio', 'Patrono ufficio', 'Osservanza'].includes(fact.label)) }
      : group)
    .map((group) => ({ ...group, title: notificationPresidio && group.id === 'udienza' ? 'Provvedimento e ufficio' : group.title }))
    .map((group) => ({ ...group, facts: group.facts.filter((fact) => String(fact.value || '').trim()) }))
    .filter((group) => group.facts.length)
}

export function deadlineWhatToDo(row: ScadenziarioRow): string {
  const text = String(row.detailDescription || row.description || '').trim()
  const match = text.match(/Attivit[àa] per l['’]avvocato\s*:\s*(.+)$/i)
  const activity = (match ? match[1] : text).trim()
  if (!activity) return 'Dettaglio operativo della scadenza selezionata.'
  return activity.charAt(0).toUpperCase() + activity.slice(1)
}
