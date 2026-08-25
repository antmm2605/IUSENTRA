export type PstRegistryOption = {
  schema: string
  label: string
  numeroLabel: string
  annoLabel: string
  ricercaEsatta: string
  ricercaAnnuale: string
  dopoSelezione: string
}

export type PstRoleOption = {
  code: string
  label: string
}

export const PST_REGISTRY_OPTIONS: readonly PstRegistryOption[] = [
  {
    schema: 'civile', label: 'Civile ordinario', numeroLabel: 'Numero R.G.', annoLabel: 'Anno R.G.',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti, storico e documenti del fascicolo',
  },
  {
    schema: 'lavoro', label: 'Lavoro e previdenza', numeroLabel: 'Numero R.G.', annoLabel: 'Anno R.G.',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti, storico e documenti del fascicolo',
  },
  {
    schema: 'volontaria', label: 'Volontaria giurisdizione', numeroLabel: 'Numero R.G.', annoLabel: 'Anno R.G.',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti, storico e documenti del fascicolo',
  },
  {
    schema: 'minori', label: 'Minorenni', numeroLabel: 'Numero R.G.', annoLabel: 'Anno R.G.',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti, storico e documenti del fascicolo',
  },
  {
    schema: 'esecuzioni mobiliari', label: 'Esecuzioni mobiliari', numeroLabel: 'Numero procedura', annoLabel: 'Anno procedura',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti dell’esecuzione, storico e documenti',
  },
  {
    schema: 'esecuzioni immobiliari', label: 'Esecuzioni immobiliari', numeroLabel: 'Numero procedura', annoLabel: 'Anno procedura',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti dell’esecuzione, storico e documenti',
  },
  {
    schema: 'procedure concorsuali', label: 'Procedure concorsuali', numeroLabel: 'Numero procedura', annoLabel: 'Anno procedura',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo, parti della procedura, storico e documenti',
  },
  {
    schema: 'giudice di pace', label: 'Giudice di Pace', numeroLabel: 'Numero R.G. (facoltativo)', annoLabel: 'Anno R.G.',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco senza numero',
    dopoSelezione: 'Profilo, parti, storico e documenti del fascicolo',
  },
  {
    schema: 'cassazione civile', label: 'Cassazione civile', numeroLabel: 'Numero ricorso', annoLabel: 'Anno deposito',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Intervallo depositi dell’anno',
    dopoSelezione: 'Profilo del ricorso, storico e documenti',
  },
  {
    schema: 'cassazione penale', label: 'Cassazione penale', numeroLabel: 'Numero ricorso', annoLabel: 'Anno ricorso',
    ricercaEsatta: 'Numero e anno', ricercaAnnuale: 'Elenco per anno',
    dopoSelezione: 'Profilo del ricorso, storico e documenti',
  },
]

export const PST_ROLE_OPTIONS: readonly PstRoleOption[] = [
  { code: 'AVV', label: 'Avvocato' },
  { code: 'DEL', label: 'Delegato' },
  { code: 'AUS', label: 'Ausiliario' },
  { code: 'CTU', label: 'Consulente/perito' },
  { code: 'CUR', label: 'Curatore' },
  { code: 'PARTE', label: 'Parte' },
  { code: 'CUS', label: 'Custode' },
  { code: 'NOT', label: 'Notaio' },
  { code: 'TUT', label: 'Tutore' },
]

export const PST_EVENT_CLASSIFICATIONS = [
  'Evento',
  'Iscrizione',
  'Udienza',
  'Comunicazione',
  'Provvedimento',
  'Rinvio',
  'Termine/scadenza',
  'Deposito/istanza',
] as const

export function uniquePstValues(values: Iterable<string>): string[] {
  return Array.from(new Set(Array.from(values, (value) => value.trim()).filter(Boolean)))
}

export function resolvedPstDocumentMode(
  modes: Readonly<Record<string, 'originale' | 'copia'>>,
  key: string,
  defaultOriginal: boolean,
): 'originale' | 'copia' {
  return modes[key] || (defaultOriginal ? 'originale' : 'copia')
}

export function pstRegistryOptionForSchema(schema: string): PstRegistryOption | undefined {
  const normalized = schema.trim().toLocaleLowerCase('it-IT')
  return PST_REGISTRY_OPTIONS.find((option) => option.schema === normalized)
}

export function pstAutomaticSchemasForOffice(officeType: string, services: readonly string[]): string[] {
  const type = officeType.trim().toLocaleUpperCase('it-IT')
  const available = services.map((service) => service.trim().toLocaleUpperCase('it-IT')).filter(Boolean)
  const has = (fragment: string) => available.some((service) => service.includes(fragment))
  const schemas: string[] = []
  const add = (...values: string[]) => values.forEach((value) => {
    if (!schemas.includes(value)) schemas.push(value)
  })

  if (type === 'CORTE_CASSAZIONE' || has('CASS')) add('cassazione civile', 'cassazione penale')
  if (type === 'GDP' || has('SIGP')) add('giudice di pace')
  if (has('SIECIC')) add('esecuzioni mobiliari', 'esecuzioni immobiliari', 'procedure concorsuali')
  if (has('SICID')) add('civile', 'lavoro', 'volontaria', 'minori')
  if (has('SIL')) add('lavoro')
  if (has('SIVG')) add('volontaria')
  if (has('SIMIN') || has('MIN')) add('minori')

  if (!schemas.length && (type === 'TRIBUNALE' || type === 'CORTE_APPELLO' || type === 'TM')) add('civile')
  return schemas
}
