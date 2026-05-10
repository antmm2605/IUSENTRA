export function sanitizeDisplayText(value: string): string {
  return value
    .replace(/\bDati\s+applicativi\s*-\s*Consultazione\b/gi, 'Dati dello studio')
    .replace(/\bDati\s+applicativi\b/gi, 'Dati dello studio')
    .replace(/Editor,\s*compilazione\s+assistita,\s*esportazioni\s+e\s+stampe\s+restano\s+nei\s+percorsi\s+[^.]+[.]/gi, 'Redazione, controlli, esportazioni e stampe sono disponibili dai comandi operativi dedicati.')
    .replace(/React\s+riceve\s+solo\s+metadati[^.]+[.]/gi, 'La pagina mostra solo informazioni utili e collegamenti operativi sicuri.')
    .replace(/\bImpeccable\s*\/\s*Open\s+Design\b/gi, 'Presidio qualita studio')
    .replace(/\bOpen\s+Design\b/gi, 'Presidio qualita')
    .replace(/\bOpen\s+Designer\b/gi, 'Presidio qualita')
    .replace(/\bContratto\s+dati\b/gi, 'Dati disponibili')
    .replace(/\bOwner\s+route\b/gi, 'Responsabile funzione')
    .replace(/\bMock\s+fallback\b/gi, 'Dati non disponibili')
    .replace(/\bDashboard\b/gi, 'Cruscotto')
    .replace(/\bworkflow\b/gi, 'percorso')
    .replace(/\bWizard\b/gi, 'Percorso guidato')
    .replace(/\bBuilder\b/gi, 'Editor')
    .replace(/\bGET\s+JSON\b/gi, 'consultazione dati')
    .replace(/\bPOST\s+JSON\b/gi, 'salvataggio dati')
    .replace(/\bread-only\b/gi, 'sola consultazione')
    .replace(/\bReact\b/gi, 'pagina')
    .replace(/\bFlask\b/gi, 'percorso applicativo')
    .replace(/\bJSON\b/g, 'dati')
    .replace(/\bUI\b/g, 'pagina')
    .replace(/\bmetadati\b/gi, 'informazioni')
    .replace(/\bmetadata\b/gi, 'informazioni')
    .replace(/\bInterfaccia\b/gi, 'Pagina')
    .replace(/\brepository\b/gi, 'archivio')
    .replace(/\bauditati\b/gi, 'tracciati')
    .replace(/\bauditate\b/gi, 'tracciate')
    .replace(/\baudit\b/gi, 'registro')
    .replace(/\brollback\s+tecnico(?:\s+legacy)?\b/gi, 'Percorso di recupero')
    .replace(/\broute\s+Flask\b/gi, 'percorso applicativo')
    .replace(/\broute\b/gi, 'percorso')
    .replace(/\bGET\b/g, 'consulta')
    .replace(/\bPOST\b/g, 'salva')
    .replace(/\bsnapshot\b/gi, 'rilevazione')
    .replace(/\bserver-side\b/gi, 'lato applicazione')
    .replace(/\bjson_api\b/gi, 'azioni protette')
    .replace(/\bAPI\b/g, 'servizio')
    .replace(/\bbackend\b/gi, 'controlli operativi')
    .replace(/\bfrontend\b/gi, 'pagina')
    .replace(/\bserver\b/gi, 'ambiente')
    .replace(/\blegacy\b/gi, 'percorso di recupero')
    .replace(/\bfallback\s+tecnico\b/gi, 'verifica prudenziale')
    .replace(/\bpayload\b/gi, 'dati')
    .replace(/\bruntime\b/gi, 'ambiente di lavoro')
    .replace(/\bendpoint\b/gi, 'comando')
    .replace(/\bbridge\b/gi, 'collegamento')
    .replace(/\bprovider\b/gi, 'fornitore')
    .replace(/\bwebhook\b/gi, 'notifica automatica')
    .replace(/\bcache\b/gi, 'elenco locale')
    .replace(/\bRBAC\b/g, 'permessi')
    .replace(/\bCMS\b/g, 'contenuti')
    .replace(/\bKPI\b/g, 'indicatori')
    .replace(/\bdemo\b/gi, 'da verificare')
    .replace(/\b(undefined|null|todo|sample)\b/gi, 'non indicato')
}

export function displaySourceLabel(value: string): string {
  const source = value.trim().toLowerCase()
  if (!source) return 'Dati dello studio'
  if (source === 'repository_reali' || source === 'backend_storico') return 'Dati dello studio'
  if (source === 'react_shell') return 'Pagina operativa'
  return sanitizeDisplayText(value.replace(/[_-]+/g, ' '))
}

export function displayWritesLabel(value: string): string {
  const writes = value.trim().toLowerCase()
  if (!writes || writes === 'none') return 'Vista dati'
  if (writes === 'operational_routes') return 'Azioni operative tracciate'
  if (writes === 'json_api' || writes === 'azioni_protette') return 'Azioni protette'
  return sanitizeDisplayText(value.replace(/[_-]+/g, ' '))
}
