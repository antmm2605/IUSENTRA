export function depositActionMessage(payload: { message?: unknown; messaggio?: unknown; errore?: unknown; error?: unknown; requires_guided_completion?: boolean; package_ready?: boolean }): string {
  const blocked = Boolean(payload.requires_guided_completion || !payload.package_ready)
  const values = blocked
    ? [payload.errore, payload.error, payload.message, payload.messaggio]
    : [payload.message, payload.messaggio, payload.errore, payload.error]
  return values.map(value => String(value || '').trim()).find(Boolean)
    || (blocked ? 'Completa i dati indicati prima di proseguire.' : 'Pacchetto di controllo preparato. Nessun invio PEC reale eseguito.')
}

export function duplicateParticipantTaxCode(message: string): string {
  if (!/AK_PARTECIPANTI(?:PU)?|codice fiscale .*ripetuto nei partecipanti/i.test(message)) return ''
  return /Codice fiscale ([A-Z0-9]{11,16}) ripetuto/i.exec(message)?.[1]
    || /Duplicate key-sequence \['([A-Z0-9]{11,16})'\]/i.exec(message)?.[1]
    || ''
}

export function canCheckPctDeposit(channel: string): boolean {
  return /^(?:SICID|SIECIC|SIGP|PCT(?: civile)?|CASSAZIONE)$/i.test(channel.trim())
}

export function depositCorrectionArea(message: string): 'contributo' | 'parti' | 'documenti' | 'fascicolo' | 'dati' {
  if (/contributo unificato|esenzione|pagamento del contributo/i.test(message)) return 'contributo'
  if (/numero (?:di )?R\.?\s*G\.?|anno (?:di )?(?:R\.?\s*G\.?|ruolo)|ufficio giudiziario/i.test(message)) return 'fascicolo'
  if (/AK_PARTECIPANTI|codice fiscale|anagrafica|partecipant/i.test(message)) return 'parti'
  if (/atto principale|documento|allegato|PDF/i.test(message)) return 'documenti'
  return 'dati'
}
