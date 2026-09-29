/** Chiamate JSON della Preparazione udienza (stesso schema di risposta: ok, message, redirect, dati). */
export async function inviaPreparazione(url: string, corpo: Record<string, unknown>): Promise<Record<string, unknown>> {
  const risposta = await fetch(url, {
    method: 'POST', credentials: 'same-origin',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'X-Requested-With': 'XMLHttpRequest' },
    body: JSON.stringify(corpo),
  }).catch(() => null)
  if (!risposta) return { ok: false, message: 'Connessione non riuscita: riprova.' }
  return await risposta.json().catch(() => ({ ok: false, message: 'Risposta non valida dal server.' })) as Record<string, unknown>
}
