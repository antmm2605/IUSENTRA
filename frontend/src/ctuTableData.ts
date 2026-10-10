export type CtuTableEntry = { value: string; label: string; tipo: string; base: string; unita: string }

/** La tabella non disponibile è un errore, non una tabella senza voci. */
export async function loadCtuTable(signal?: AbortSignal): Promise<CtuTableEntry[]> {
  try {
    const response = await fetch('/api/v1/ui/ctu/tabella', {
      credentials: 'same-origin', cache: 'no-store', headers: { Accept: 'application/json' }, signal,
    })
    if (response.status === 401) throw new Error('La sessione è scaduta. Accedi nuovamente per caricare la tabella.')
    if (response.status === 403) throw new Error('Non hai il permesso di caricare la tabella del compenso.')
    if (!response.ok) throw new Error('Caricamento della tabella del compenso non riuscito. Riprova.')
    const payload = await response.json()
    if (payload?.ok !== true || !Array.isArray(payload.voci) || !payload.voci.length ||
        payload.voci.some((entry: unknown) => {
          if (!entry || typeof entry !== 'object') return true
          const row = entry as Record<string, unknown>
          return ['value', 'label', 'tipo', 'base', 'unita'].some((key) => typeof row[key] !== 'string') ||
            !String(row.value).trim() || !String(row.label).trim()
        }) || new Set(payload.voci.map((entry: CtuTableEntry) => entry.value)).size !== payload.voci.length) {
      throw new Error('La tabella del compenso ricevuta è incompleta. Riprova il caricamento.')
    }
    return payload.voci
  } catch (error) {
    if (signal?.aborted) throw error
    if (error instanceof Error && /^(La sessione|Non hai|Caricamento|La tabella)/.test(error.message)) throw error
    throw new Error('Connessione non riuscita durante il caricamento della tabella. La bozza è conservata.')
  }
}
