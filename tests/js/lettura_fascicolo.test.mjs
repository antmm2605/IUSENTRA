// Technical guardrails only: trasformazioni pure del pannello «Lettura del fascicolo».
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  etichettaFase,
  etichettaUrgenza,
  hrefCalcoloTermine,
  normeDelPasso,
  passiOrdinati,
  presidiCards,
  riassuntoStatoPassi,
  tonoFase,
} from '../../frontend/src/components/fascicoli/letturaFascicolo.ts'

const passo = (overrides) => ({ urgenza: 2, azione: 'Azione', motivo: '', entro: '', fonte: 'scadenziario', norma: '', fonti: [], href: '#udienze', template: '', ...overrides })

const lettura = (overrides = {}) => ({
  versione: 'v', generata_il: '14/09/2026',
  intestazione: { numero: '1', titolo: 'T', rg: '1/2026', ufficio: 'U', cliente: 'C', controparte: 'X', stato: 'in corso', stato_codice: 'IN_CORSO', da_archiviare: false, valore_causa: '', area: '', rito: '', parti: {} },
  oggetto: { oggetto_dichiarato: '', atti_principali: [], domanda: null },
  cronologia: [],
  depositi: { totale: 2, perfezionati: [1], in_corso: [], falliti: [1], tutti: [] },
  notifiche: { totale: 1, perfezionate: [], aperte: [1], fallite: [], tutte: [] },
  pec: { totale: 3, collegate: 1, per_corrispondenza: {}, da_controllare: [{}], termini_da_registrare: [{}], udienze_da_registrare: [], ultima: null },
  documenti: { totale: 10, catalogati: 9, confermati: 4, da_verificare: [{}], non_indicizzati: [], conteggi: {} },
  economico: { presente: true, preventivato_it: '', conferito_it: '', fatturato_it: '€ 2.500,00', incassato_it: '€ 1.000,00', saldo_aperto_it: '€ 1.500,00', parcelle_scadute: [{ numero: '2026/002', totale_it: '€ 900,00', scadenza: '31/05/2026' }], importo_scaduto_it: '€ 900,00', ha_incarico: true },
  fase: { codice: 'trattazione', descrizione: 'fase di trattazione', prove: [], incoerenze: [], prossima_udienza: '', stato_dichiarato: 'in corso' },
  prossimi_passi: [passo({ urgenza: 1, azione: 'B' }), passo({ urgenza: 0, azione: 'A', fonte: 'scadenziario' }), passo({ urgenza: 3, azione: 'C', fonte: 'catalogazione' })],
  stato_passi: { attivi: true, motivo: '' },
  lacune: [],
  conoscenza: { versione: 'v', rito: {}, deposito: {}, notifiche: [] },
  narrativa: '',
  ...overrides,
})

test('urgenze e fasi hanno etichette italiane e toni coerenti', () => {
  assert.equal(etichettaUrgenza(0).etichetta, 'Subito')
  assert.equal(etichettaUrgenza(0).tono, 'danger')
  assert.equal(etichettaUrgenza(9).etichetta, 'Di governo')
  assert.equal(etichettaFase('iscritta_a_ruolo'), 'Iscritta a ruolo')
  assert.equal(etichettaFase('sconosciuta_x'), 'sconosciuta x')
  assert.equal(tonoFase('decisa'), 'warning')
  assert.equal(tonoFase('chiusa'), 'neutral')
  assert.equal(tonoFase('trattazione'), 'success')
})

test('le card dei presìdi leggono i numeri della lettura e portano dove si agisce', () => {
  const cards = presidiCards(lettura())
  const perId = Object.fromEntries(cards.map((card) => [card.id, card]))
  assert.deepEqual(cards.map((card) => card.id), ['documenti', 'depositi', 'notifiche', 'pec', 'scadenze', 'economico'])
  assert.equal(perId.documenti.valore, '9/10')
  assert.equal(perId.documenti.tono, 'warning')
  assert.equal(perId.depositi.tono, 'danger')
  assert.match(perId.depositi.nota, /1 da ripetere/)
  assert.equal(perId.notifiche.tono, 'warning')
  assert.equal(perId.pec.tono, 'warning')
  assert.match(perId.pec.nota, /1 da controllare · 1 termini da registrare/)
  assert.equal(perId.scadenze.valore, '2')
  assert.equal(perId.scadenze.tono, 'info')
  assert.equal(perId.economico.valore, '€ 1.500,00')
  assert.equal(perId.economico.tono, 'danger')
  assert.match(perId.economico.nota, /1 parcelle scadute per € 900,00/)
  assert.equal(perId.economico.href, '#presidio-fascicolo')
})

test('gli atti acquisiti dal fascicolo d\'ufficio si leggono come tali', () => {
  const cards = presidiCards(lettura({ depositi: { totale: 16, importati: new Array(16).fill({}), perfezionati: [], in_corso: [], falliti: [], tutti: [] } }))
  const card = cards.find((c) => c.id === 'depositi')
  assert.equal(card.valore, '16')
  assert.equal(card.nota, "16 atti acquisiti dal fascicolo d'ufficio")
  assert.equal(card.tono, 'neutral')
})

test('fascicolo senza presìdi resta leggibile', () => {
  const vuota = lettura({
    depositi: { totale: 0, perfezionati: [], in_corso: [], falliti: [], tutti: [] },
    notifiche: { totale: 0, perfezionate: [], aperte: [], fallite: [], tutte: [] },
    pec: { totale: 0, collegate: 0, per_corrispondenza: {}, da_controllare: [], termini_da_registrare: [], udienze_da_registrare: [], ultima: null },
    documenti: { totale: 0, catalogati: 0, confermati: 0, da_verificare: [], non_indicizzati: [], conteggi: {} },
    economico: { presente: false, preventivato_it: '', conferito_it: '', fatturato_it: '', incassato_it: '', saldo_aperto_it: '', parcelle_scadute: [], importo_scaduto_it: '', ha_incarico: false },
    prossimi_passi: [],
  })
  const cards = presidiCards(vuota)
  assert.ok(cards.every((card) => card.tono === 'neutral' || card.id === 'scadenze'))
  assert.equal(cards.find((card) => card.id === 'economico').valore, '—')
  assert.equal(riassuntoStatoPassi(vuota), 'Nessun adempimento risulta aperto: il fascicolo è allineato.')
})

test('i passi si ordinano per urgenza e il riassunto conta subito e pochi giorni', () => {
  const ordinati = passiOrdinati(lettura())
  assert.deepEqual(ordinati.map((p) => p.azione), ['A', 'B', 'C'])
  assert.equal(riassuntoStatoPassi(lettura()), '3 passaggi · 1 da fare subito · 1 entro pochi giorni')
  assert.equal(riassuntoStatoPassi(lettura({ stato_passi: { attivi: false, motivo: 'Fascicolo definito: nessun passaggio da eseguire.' } })), 'Fascicolo definito: nessun passaggio da eseguire.')
})

test('norma del passo e link al calcolo del termine', () => {
  assert.equal(normeDelPasso(passo({ norma: 'art. 165 c.p.c.' })), 'art. 165 c.p.c.')
  assert.equal(normeDelPasso(passo({ fonti: [{ norma: 'art. 147 c.p.c.' }, { norma: 'L. 53/1994, art. 3-bis' }] })), 'art. 147 c.p.c.; L. 53/1994, art. 3-bis')
  assert.equal(hrefCalcoloTermine(passo({ template: 'CIV_APPELLO_BREVE' })), '/strumenti-legali?strumento=termini-processuali&template=CIV_APPELLO_BREVE')
  assert.equal(hrefCalcoloTermine(passo()), '')
})

test('le verifiche automatiche si leggono presidio per presidio', async () => {
  const { righeVerifiche } = await import('../../frontend/src/components/fascicoli/letturaFascicolo.ts')
  assert.deepEqual(righeVerifiche(undefined), [])
  assert.deepEqual(righeVerifiche({ in_corso: true }), [])
  const righe = righeVerifiche({
    eseguita_il: '2026-09-14T10:00:00+02:00',
    esiti: {
      pec: { esaminate: 3, collegate: 1, job_eseguiti: 2, da_confermare: [{ id: 'M2', oggetto: 'x', corrispondenza: 'cliente' }] },
      notifiche: { esaminati: 2, riallineati: 1 },
      depositi: { pendenti: 1, esito: 'pec_non_configurata' },
      documenti: { documenti: 5, indicizzati: 0, errori: 0, esito: 'tutti_letti' },
    },
    errori: { conoscenza: 'timeout' },
  })
  assert.deepEqual(righe.map((r) => r.presidio), ['Presidio PEC', 'Presidio notifiche', 'Presidio depositi', 'Presidio documentale', 'Verifica conoscenza'])
  assert.match(righe[0].esito, /1 da confermare/)
  assert.equal(righe[0].tono, 'warning')
  assert.equal(righe[2].tono, 'warning')
  assert.match(righe[2].esito, /casella PEC dello studio non configurata/)
  assert.equal(righe[3].esito, 'tutti i 5 documenti letti dall’archivio')
  assert.equal(righe[4].tono, 'danger')
})

test('il presidio economico legge liquidazione del giudice e bonifici', async () => {
  const { righeEconomico } = await import('../../frontend/src/components/fascicoli/letturaFascicolo.ts')
  const base = { presente: true, preventivato_it: '€ 3.000,00', conferito_it: '', fatturato_it: '€ 2.000,00', incassato_it: '€ 0,00', saldo_aperto_it: '€ 2.000,00', parcelle_scadute: [], importo_scaduto_it: '', ha_incarico: true }
  assert.deepEqual(righeEconomico({ ...base, presente: false }), [])
  const righe = righeEconomico({ ...base, liquidato: 4500, liquidato_it: '€ 4.500,00', liquidazione_incasso: 'non_incassata', liquidazione: { data: '01/09/2026', stato_etichetta: 'Da registrare' }, anticipazioni_da_recuperare: 259, anticipazioni_da_recuperare_it: '€ 259,00' })
  const liquidato = righe.find((r) => r.etichetta === 'Liquidato dal giudice')
  assert.equal(liquidato.valore, '€ 4.500,00')
  assert.equal(liquidato.tono, 'danger')
  assert.match(liquidato.nota, /sentenza del 01\/09\/2026 · da registrare nel presidio · non ancora bonificata/)
  assert.ok(righe.some((r) => r.etichetta === 'Anticipazioni da recuperare' && r.valore === '€ 259,00'))
  const incassata = righeEconomico({ ...base, incassato_it: '€ 4.500,00', liquidato: 4500, liquidato_it: '€ 4.500,00', liquidazione_incasso: 'incassata', bonifici: [{ numero: '2026/001', totale_it: '€ 4.500,00', pagata_il: '10/09/2026' }], incassato_bonifico_it: '€ 4.500,00' })
  assert.equal(incassata.find((r) => r.etichetta === 'Liquidato dal giudice').tono, 'success')
  assert.equal(incassata.find((r) => r.etichetta === 'Incassato').nota, 'di cui 1 bonifico per € 4.500,00')
  const card = presidiCards(lettura({ economico: { ...base, liquidato: 4500, liquidato_it: '€ 4.500,00', liquidazione_incasso: 'non_incassata' } })).find((c) => c.id === 'economico')
  assert.equal(card.valore, '€ 4.500,00')
  assert.equal(card.tono, 'danger')
  assert.match(card.nota, /liquidato dal giudice · non ancora bonificato/)
})
