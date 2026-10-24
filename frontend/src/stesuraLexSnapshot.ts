export function stesuraSnapshot(modelCode: string, fascicoloId: string, clienteId: string, oggetto: string, ruolo: string, valori: Record<string,string>) {
  return JSON.stringify([modelCode, fascicoloId, clienteId, oggetto, ruolo, Object.entries(valori).sort(([a],[b]) => a.localeCompare(b))])
}
