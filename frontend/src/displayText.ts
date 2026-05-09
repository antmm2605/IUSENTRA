export function sanitizeDisplayText(value: string): string {
  return value
    .replace(/\brollback\s+tecnico(?:\s+legacy)?\b/gi, 'Percorso di recupero')
    .replace(/\broute\s+Flask\b/gi, 'percorso applicativo')
    .replace(/\bserver-side\b/gi, 'lato applicazione')
    .replace(/\bjson_api\b/gi, 'servizi protetti')
    .replace(/\bbackend\b/gi, 'servizi applicativi')
    .replace(/\bfrontend\b/gi, 'interfaccia')
    .replace(/\blegacy\b/gi, 'percorso di recupero')
    .replace(/\bpayload\b/gi, 'dati')
    .replace(/\bruntime\b/gi, 'ambiente operativo')
    .replace(/\bendpoint\b/gi, 'servizio')
    .replace(/\bbridge\b/gi, 'collegamento')
    .replace(/\bprovider\b/gi, 'fornitore')
    .replace(/\bwebhook\b/gi, 'notifica automatica')
    .replace(/\bdemo\b/gi, 'da verificare')
    .replace(/\b(undefined|null|todo|sample)\b/gi, 'non indicato')
}

export function displaySourceLabel(value: string): string {
  const source = value.trim().toLowerCase()
  if (!source) return 'Dati applicativi'
  if (source === 'repository_reali' || source === 'backend_storico') return 'Dati applicativi'
  if (source === 'react_shell') return 'Interfaccia operativa'
  return sanitizeDisplayText(value.replace(/[_-]+/g, ' '))
}

export function displayWritesLabel(value: string): string {
  const writes = value.trim().toLowerCase()
  if (!writes || writes === 'none') return 'Consultazione'
  if (writes === 'operational_routes') return 'Azioni operative auditate'
  if (writes === 'json_api' || writes === 'azioni_protette') return 'Azioni protette'
  return sanitizeDisplayText(value.replace(/[_-]+/g, ' '))
}
