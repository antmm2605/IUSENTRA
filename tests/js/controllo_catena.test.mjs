// Technical guardrails only: avvisi del guardiano della catena nella Lettura del fascicolo.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { avvisiDaMostrare, primaLettera, statoDelControllo } from '../../frontend/src/components/fascicoli/controlloCatena.ts'

const avviso = { codice: 'definito_con_udienza_futura', descrizione: "il fascicolo è «Definito» ma c'è un'udienza il 09/02/2027",
  perche: 'una causa con un’udienza fissata non è definita', norma: '', dal: '2026-11-19' }

test('si mostrano solo gli avvisi con una descrizione, mai un payload in errore', () => {
  assert.deepEqual(avvisiDaMostrare({ ok: true, stato: 'verificato', avvisi: [avviso, { ...avviso, descrizione: '' }] }), [avviso])
  assert.deepEqual(avvisiDaMostrare({ ok: false, avvisi: [avviso] }), [])
  assert.deepEqual(avvisiDaMostrare(null), [])
})

test('il controllo in aggiornamento lo dice, quello verificato non aggiunge nulla', () => {
  assert.match(statoDelControllo({ ok: true, stato: 'in_aggiornamento' }), /in aggiornamento/)
  assert.equal(statoDelControllo({ ok: true, stato: 'verificato' }), '')
  assert.equal(primaLettera('il fascicolo'), 'Il fascicolo')
})
