// Technical guardrails only: trasformazioni pure del registro delle letture del fascicolo.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  anomalieOrdinate,
  etichettaCampo,
  fraseNovita,
  oggettiInAttesa,
  riassuntoLetture,
  tonoGravita,
} from '../../frontend/src/components/fascicoli/lettureFascicolo.ts'

const lettore = (overrides) => ({ lettore: 'ocr', etichetta: 'Testo e ricerca', versione: 'v', letti: 0, da_leggere: 0, errori: 0, ultima_lettura: '', ultima_lettura_it: '', completa: true, ...overrides })
const oggetto = (overrides) => ({ tipo: 'documento', oggetto_id: 'd1', nome: 'atto.pdf', etichetta: 'atto.pdf', sha256: 'a', impronta: 'a', data_oggetto: '', letture: {}, ...overrides })
const letture = (overrides = {}) => ({ impronta: 'x', oggetti: 3, tutto_letto: false, lettori: [], per_oggetto: [], novita: { prima_vista: true, visto_il: '', visto_il_it: '', nuovi: [], cambiati: [], rimossi: [] }, anomalie: [], anomalie_aperte: 0, ...overrides })

test('riassunto: tutto letto, da leggere per lettore, nessun oggetto', () => {
  assert.equal(riassuntoLetture(letture({ oggetti: 0 })).tono, 'neutral')
  const tutto = riassuntoLetture(letture({ lettori: [lettore({ letti: 3 })] }))
  assert.equal(tutto.tono, 'success')
  assert.match(tutto.testo, /Tutto letto: 3/)
  const parziale = riassuntoLetture(letture({ lettori: [lettore({ letti: 1, da_leggere: 2 }), lettore({ lettore: 'catalogo', etichetta: 'Catalogo dal contenuto', letti: 3 })] }))
  assert.equal(parziale.tono, 'warning')
  assert.equal(parziale.testo, 'Da leggere: 2 per testo e ricerca.')
  assert.equal(riassuntoLetture(letture({ lettori: [lettore({ errori: 1 })] })).tono, 'danger')
})

test('novità dall\'ultima apertura: prima vista silenziosa, poi conteggi in italiano', () => {
  assert.equal(fraseNovita({ prima_vista: true, visto_il: '', visto_il_it: '', nuovi: [], cambiati: [], rimossi: [] }), '')
  const frase = fraseNovita({ prima_vista: false, visto_il: '2026-09-15T10:00:00Z', visto_il_it: '15/09/2026 12:00', nuovi: [oggetto(), oggetto({ tipo: 'pec', oggetto_id: 'm1' })], cambiati: [oggetto({ oggetto_id: 'd2' })], rimossi: [{ tipo: 'documento', oggetto_id: 'd9' }] })
  assert.equal(frase, "Dall'ultima apertura (15/09/2026 12:00): nuovi 1 documento e 1 PEC · cambiato 1 documento · 1 rimosso.")
  assert.match(fraseNovita({ prima_vista: false, visto_il: '', visto_il_it: '', nuovi: [], cambiati: [], rimossi: [] }), /Nessuna novità/)
})

test('oggetti in attesa elencano solo i lettori mancanti con l\'etichetta italiana', () => {
  const stato = letture({
    lettori: [lettore(), lettore({ lettore: 'catalogo', etichetta: 'Catalogo dal contenuto' })],
    per_oggetto: [oggetto({ letture: { ocr: 'letto', catalogo: 'da_leggere' } }), oggetto({ oggetto_id: 'd2', letture: { ocr: 'non_leggibile', catalogo: 'letto' } }), oggetto({ oggetto_id: 'd3', letture: { ocr: 'da_rileggere', catalogo: 'errore' } })],
  })
  const attesa = oggettiInAttesa(stato)
  assert.deepEqual(attesa.map((voce) => [voce.oggetto.oggetto_id, voce.lettori]), [['d1', ['Catalogo dal contenuto']], ['d3', ['Testo e ricerca', 'Catalogo dal contenuto']]])
})

test('anomalie: gravità in tono e ordine, campi con etichetta', () => {
  assert.equal(tonoGravita('alta'), 'danger')
  assert.equal(tonoGravita('media'), 'warning')
  assert.equal(tonoGravita('bassa'), 'info')
  assert.equal(etichettaCampo('udienza'), 'data di udienza')
  assert.equal(etichettaCampo('dies_a_quo'), 'dies a quo')
  const base = { id: '', tipo: 'documento', oggetto_id: 'd', oggetto: 'b.pdf', lettore: 'ocr', lettore_etichetta: '', campo: 'udienza', valore_letto: '', valore_proposto: '', contesto: '', motivo: '', codice: '', stato: 'aperta', creata_il_it: '' }
  const ordinate = anomalieOrdinate([{ ...base, id: '1', gravita: 'bassa' }, { ...base, id: '2', gravita: 'alta', oggetto: 'z.pdf' }, { ...base, id: '3', gravita: 'alta', oggetto: 'a.pdf' }])
  assert.deepEqual(ordinate.map((voce) => voce.id), ['3', '2', '1'])
})
