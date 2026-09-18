// Technical guardrails only: trasformazioni pure del registro delle letture del fascicolo.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  anomalieOrdinate,
  etichettaCampo,
  fraseCollaudo,
  fraseLetturaAutomatica,
  fraseNovita,
  lettoriDaMostrare,
  oggettiInAttesa,
  riassuntoArchivio,
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

const archivio = (overrides = {}) => ({ totale: 5, per_verifica: { verificata: 3, plausibile: 1, respinta: 1, corretta: 0, ignorata: 0 }, udienze: 1, termini: 2, notifiche: 0, prove_notifica: 1, ruoli: 1, eventi: 0, per_motore: { documenti: 4, pec: 1 }, da_confermare: [], lettura_automatica: { in_corso: false, da_leggere: 0, completa: true, ultima_lettura: '2026-09-16T05:00:00Z', ultima_lettura_it: '16/09/2026 07:00' }, collaudo_lettore: { eseguito: true, superato: true, corretti: 3, totali: 3, eseguito_il_it: '16/09/2026 04:10' }, ...overrides })

test('archivio completo: il registro non mostra vecchi lettori come lavoro aperto', () => {
  const stato = letture({
    oggetti: 42,
    archivio: archivio({ per_motore: { documenti: 42, pec: 0 } }),
    lettori: [
      lettore({ lettore: 'ocr', etichetta: 'Testo e ricerca', da_leggere: 42 }),
      lettore({ lettore: 'catalogo', etichetta: 'Catalogo dal contenuto', da_leggere: 41 }),
      lettore({ lettore: 'motore_documenti', etichetta: 'Motore documenti (archivio)', letti: 42 }),
      lettore({ lettore: 'motore_pec', etichetta: 'Motore PEC (archivio)', letti: 0 }),
    ],
    per_oggetto: [oggetto({ letture: { ocr: 'da_leggere', catalogo: 'da_leggere', motore_documenti: 'letto' } })],
  })
  assert.equal(riassuntoLetture(stato).tono, 'success')
  assert.match(riassuntoLetture(stato).testo, /Tutto letto e collaudato: 42/)
  assert.deepEqual(oggettiInAttesa(stato), [])
  assert.deepEqual(lettoriDaMostrare(stato).map((voce) => voce.lettore), ['motore_documenti', 'motore_pec'])
})

test('archivio: riassunto dei dati verificati, da confermare, in attesa di lettura', () => {
  const pieno = riassuntoArchivio(archivio())
  assert.equal(pieno.tono, 'success')
  assert.equal(pieno.testo, '3 dati verificati dal software (1 udienza, 2 termini, 1 prova di notifica, 1 numero di ruolo), nessuno da confermare.')
  const conferme = riassuntoArchivio(archivio({ da_confermare: [{ id: 'f1', campo: 'udienza', etichetta: 'Udienza del 10/11/2026', valore: '2026-11-10', valore_letto: '1O/11/2O26', oggetto_id: 'd1', tipo: 'documento', contesto: '', prove: [] }] }))
  assert.equal(conferme.tono, 'warning')
  assert.match(conferme.testo, /1 da confermare\.$/)
  assert.equal(riassuntoArchivio(archivio({ totale: 0, lettura_automatica: { in_corso: true, da_leggere: 3, completa: false, ultima_lettura: '', ultima_lettura_it: '' } })).tono, 'info')
  assert.equal(riassuntoArchivio(archivio({ totale: 0, lettura_automatica: { in_corso: false, da_leggere: 3, completa: false, ultima_lettura: '', ultima_lettura_it: '' } })).testo, 'Lettura automatica in attesa: 3 oggetti da leggere.')
  assert.equal(riassuntoArchivio(undefined).tono, 'neutral')
})

test('riassunto letture: se la lettura automatica è partita non chiede intervento manuale', () => {
  const stato = letture({
    oggetti: 7,
    archivio: archivio({ lettura_automatica: { in_corso: true, da_leggere: 7, completa: false, ultima_lettura: '', ultima_lettura_it: '' } }),
  })

  const riassunto = riassuntoLetture(stato)
  assert.equal(riassunto.tono, 'info')
  assert.equal(riassunto.testo, 'Lettura automatica in corso: 7 oggetti in lavorazione.')
})

test('collaudo del lettore e lettura automatica in frasi italiane', () => {
  assert.equal(fraseCollaudo(archivio().collaudo_lettore).testo, 'Collaudo del lettore superato il 16/09/2026 04:10: 3/3 pagine di prova lette correttamente.')
  const fallito = fraseCollaudo({ eseguito: true, superato: false, corretti: 2, totali: 3, eseguito_il_it: '', casi_falliti: ['Relata con dati anagrafici'] })
  assert.equal(fallito.tono, 'danger')
  assert.match(fallito.testo, /NON superato: 2\/3 pagine corrette\. Non superato: Relata con dati anagrafici\./)
  assert.equal(fraseCollaudo(undefined).tono, 'neutral')
  assert.equal(fraseLetturaAutomatica(archivio().lettura_automatica), 'Tutto letto e collaudato; ultima lettura automatica 16/09/2026 07:00. Si rilegge solo ciò che cambia.')
  assert.equal(fraseLetturaAutomatica({ in_corso: false, da_leggere: 1, completa: false, ultima_lettura: '', ultima_lettura_it: '' }), 'Lettura automatica: 1 oggetto ancora da leggere (il prossimo giro parte da solo).')
})

test('lettura automatica: dice quale oggetto manca e perché', () => {
  const stato = {
    in_corso: false, da_leggere: 1, completa: false, ultima_lettura: '', ultima_lettura_it: '',
    in_attesa: [{ tipo: 'documento', oggetto_id: 'd1', nome: 'Ricorso.pdf', motore: 'documenti', motivo: 'non ancora letto dai motori' }],
  }
  assert.equal(
    fraseLetturaAutomatica(stato),
    'Lettura automatica: 1 oggetto ancora da leggere: «Ricorso.pdf» (non ancora letto dai motori) (il prossimo giro parte da solo).',
  )
  const molti = {
    in_corso: false, da_leggere: 5, completa: false, ultima_lettura: '', ultima_lettura_it: '',
    in_attesa: ['a', 'b', 'c', 'd', 'e'].map((nome) => ({ tipo: 'documento', oggetto_id: nome, nome, motore: 'documenti', motivo: 'il contenuto è cambiato: va riletto' })),
  }
  assert.match(fraseLetturaAutomatica(molti), /«a».*«b».*«c».*e altri 2/)
})
