// Il passo citato da una proposta (es. il dispositivo della sentenza) dentro lo strato di testo del lettore.
// Modulo puro: riceve i testi delle parole nell'ordine di lettura e restituisce quali parole evidenziare.

const normalizza = (testo) => String(testo || '')
  .toLowerCase()
  .normalize('NFD')
  .replace(/[̀-ͯ]/g, '')
  .match(/[a-z0-9]+/g) || []

/** Il passo dal frammento dell'indirizzo (`#passo=…`), mai inviato al server. */
export function passoDaIndirizzo(hash) {
  const valore = new URLSearchParams(String(hash || '').replace(/^#/, '')).get('passo')
  return valore ? valore.trim() : ''
}

/**
 * Indici delle parole che compongono il passo, o [] se il passo non si trova.
 * Cerca la sequenza iniziale più lunga possibile (12, 8, 5 parole, anche saltando le prime due o quattro)
 * e poi estende l'evidenza per tutta la lunghezza del passo: l'OCR può differire in qualche parola.
 */
export function trovaPasso(paroleTesto, passo) {
  const cercate = normalizza(passo)
  if (cercate.length < 3) return []
  const gettoni = []
  paroleTesto.forEach((testo, indice) => {
    for (const gettone of normalizza(testo)) gettoni.push({ gettone, indice })
  })
  // Prima dall'inizio del passo; se la prima parola è letta diversamente, da qualche parola più avanti.
  for (const salto of [0, 2, 4]) for (const lunghezza of [12, 8, 5]) {
    const testa = cercate.slice(salto, salto + Math.min(lunghezza, cercate.length - salto))
    if (testa.length < 3) continue
    for (let inizio = 0; inizio + testa.length <= gettoni.length; inizio += 1) {
      if (!testa.every((gettone, k) => gettoni[inizio + k].gettone === gettone)) continue
      // Le parole saltate in testa restano nell'evidenza: sono quelle che l'OCR ha letto diversamente.
      const primo = Math.max(0, inizio - salto)
      const fine = Math.min(gettoni.length, primo + cercate.length) - 1
      const indici = new Set()
      for (let k = primo; k <= fine; k += 1) indici.add(gettoni[k].indice)
      return [...indici].sort((a, b) => a - b)
    }
  }
  return []
}
