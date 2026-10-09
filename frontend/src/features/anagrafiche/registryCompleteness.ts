/** Completezza dei campi correnti, distinta da verifica e salvataggio. */
export type RegistryCompletenessItem = { label: string; complete: boolean; detail: string }

export function registryCompleteness(
  values: Record<string, string | boolean>,
  options: { legal: boolean; subject?: boolean; documentRejected?: boolean; allowedRoles?: string[] },
): RegistryCompletenessItem[] {
  const present = (key: string) => typeof values[key] === 'string' && Boolean(String(values[key]).trim())
  const item = (label: string, fields: string[], detail: string): RegistryCompletenessItem => ({
    label, complete: fields.every(present), detail: fields.every(present) ? 'Compilato' : detail,
  })
  const prefix = options.legal && !options.subject ? 'sl_' : ''
  const rows = [
    item(options.legal ? 'Ragione sociale e dato fiscale' : 'Nome, cognome e codice fiscale',
      options.legal ? ['ragione_sociale', present('codice_fiscale') ? 'codice_fiscale' : 'partita_iva'] : ['nome', 'cognome', 'codice_fiscale'],
      'Dati identificativi da completare'),
    { label: 'Recapito operativo', complete: ['telefono', 'cellulare', 'email', 'pec'].some(present),
      detail: ['telefono', 'cellulare', 'email', 'pec'].some(present) ? 'Compilato' : 'Nessun recapito compilato' },
    item(options.legal && !options.subject ? 'Indirizzo della sede' : 'Indirizzo',
      ['via', 'comune', 'provincia', 'cap'].map(key => prefix + key), 'Indirizzo da completare'),
  ]
  if (options.subject) {
    const role = String(values.qualifica || '').trim()
    const complete = Boolean(role && options.allowedRoles?.includes(role))
    rows.push({ label: 'Ruolo processuale', complete, detail: complete ? 'Selezionato' : 'Ruolo da selezionare' })
  } else if (!options.legal) {
    rows.push(options.documentRejected
      ? { label: 'Dati del documento', complete: false, detail: 'Lettura non accettata: controlla il lettore documento' }
      : item('Dati del documento', ['doc_numero', 'doc_rilasciato_da', 'doc_data_rilascio', 'doc_data_scadenza'],
        'Numero, ente, rilascio o scadenza da completare'))
  }
  return rows
}
