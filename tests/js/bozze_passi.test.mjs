// Technical guardrails only: abbinamento puro delle bozze ai prossimi passi della Lettura.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { bozzeDelPasso, bozzeSenzaPasso, etichettaStatoBozza, riassuntoDaCompletare } from '../../frontend/src/components/fascicoli/bozzePassi.ts'

const bozza = (overrides = {}) => ({
  chiave: 'note_127ter:2026-12-16', tipo: 'note_127ter', titolo: 'Note scritte', modello: 'builtin-tmp-civ-012', modelloTitolo: "Note d'udienza",
  norma: 'art. 127-ter c.p.c.', daCompletare: ['conclusioni'], passi: [{ azione: 'Depositare le note scritte', entro: '16/12/2026' }],
  stato: 'pronta', statoEtichetta: 'Bozza pronta', documentoId: 'D1', apri: '/fascicoli/F/documenti/D1/editor',
  preparataIl: '18/11/2026', aggiornataIl: '18/11/2026', datiCambiatiIl: '', ...overrides,
})

test('la bozza si abbina al passo con la stessa azione e la stessa data', () => {
  const bozze = [bozza()]
  assert.equal(bozzeDelPasso(bozze, { azione: 'Depositare le note scritte', entro: '16/12/2026' }).length, 1)
  assert.equal(bozzeDelPasso(bozze, { azione: 'Depositare le note scritte', entro: '23/11/2026' }).length, 0)
  assert.equal(bozzeDelPasso([bozza({ stato: 'superata' })], { azione: 'Depositare le note scritte', entro: '16/12/2026' }).length, 0)
})

test('le bozze senza passo visibile restano mostrate a parte', () => {
  const credito = bozza({ chiave: 'richiesta_pagamento_pa:x', passi: [] })
  assert.deepEqual(bozzeSenzaPasso([bozza(), credito], [{ azione: 'Depositare le note scritte', entro: '16/12/2026' }]).map((b) => b.chiave), ['richiesta_pagamento_pa:x'])
})

test('lo stato dice se la bozza è dell’avvocato e se i dati sono cambiati, con date italiane', () => {
  assert.equal(etichettaStatoBozza(bozza()).testo, 'Preparata il 18/11/2026')
  assert.equal(etichettaStatoBozza(bozza({ stato: 'modificata' })).testo, 'Modificata da te')
  const cambiata = etichettaStatoBozza(bozza({ stato: 'dati_cambiati', datiCambiatiIl: '20/11/2026' }))
  assert.equal(cambiata.tono, 'warning')
  assert.match(cambiata.testo, /dati del fascicolo cambiati il 20\/11\/2026/)
  assert.equal(riassuntoDaCompletare(bozza()), '1 dato da completare')
  assert.equal(riassuntoDaCompletare(bozza({ daCompletare: [] })), 'Tutti i dati compilati dalle fonti del fascicolo')
})
