// Technical guardrails only: il Controllo della catena del fascicolo, sempre visibile sotto il quadro.
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import { anelliDaMostrare, avvisiDaMostrare, primaLettera, statoDelControllo } from '../../frontend/src/components/fascicoli/controlloCatena.ts'

const avviso = { codice: 'definito_con_udienza_futura', anello: 'quadro', descrizione: "il fascicolo è «Definito» ma c'è un'udienza il 09/02/2027",
  perche: 'una causa con un’udienza fissata non è definita', norma: '', dal: '2026-11-19' }
const anelli = ['letture', 'termini', 'passi', 'economia', 'quadro']

test('si mostrano solo gli avvisi con una descrizione, mai un payload in errore', () => {
  assert.deepEqual(avvisiDaMostrare({ ok: true, stato: 'verificato', avvisi: [avviso, { ...avviso, descrizione: '' }] }), [avviso])
  assert.deepEqual(avvisiDaMostrare({ ok: false, avvisi: [avviso] }), [])
  assert.deepEqual(avvisiDaMostrare(null), [])
  assert.equal(primaLettera('il fascicolo'), 'Il fascicolo')
})

test('gli anelli della catena ci sono sempre, nell’ordine letture → termini → passi → economia → quadro', () => {
  assert.deepEqual(anelliDaMostrare(null).map((a) => a.codice), anelli)
  assert.ok(anelliDaMostrare({ ok: false }).every((a) => a.esito === 'non_controllato'))
  const dalServer = anelliDaMostrare({ ok: true, stato: 'verificato', anelli: [
    { codice: 'quadro', nome: 'Quadro', descrizione: '', esito: 'da_verificare', etichetta: 'da verificare', avvisi: 1, riparate: 0 },
    { codice: 'termini', nome: 'Termini e udienze', descrizione: '', esito: 'riparato', etichetta: 'riparato dal software', avvisi: 0, riparate: 2 },
  ] })
  assert.deepEqual(dalServer.map((a) => a.codice), anelli)
  assert.equal(dalServer[4].esito, 'da_verificare')
  assert.equal(dalServer[1].esito, 'riparato')
})

test('la frase di stato dice sempre qualcosa: verificata, da verificare, in aggiornamento, mai controllata', () => {
  const quando = { quando: '2026-11-21T13:07:13+00:00' }
  assert.match(statoDelControllo({ ok: true, stato: 'verificato', ultimoControllo: quando, avvisi: [] }), /^Catena verificata.*21\/11\/2026 14:07/)
  assert.match(statoDelControllo({ ok: true, stato: 'verificato', avvisi: [avviso] }), /1 punto da verificare/)
  assert.match(statoDelControllo({ ok: true, stato: 'in_aggiornamento' }), /in aggiornamento/)
  assert.match(statoDelControllo({ ok: true, stato: 'mai_controllato' }), /non è ancora stato eseguito/)
  assert.match(statoDelControllo({ ok: false }), /non disponibile/)
  assert.match(statoDelControllo(null), /in caricamento/)
})

test('il pannello è montato nella pagina del fascicolo sotto il quadro, non dentro una sezione chiusa', () => {
  const pagina = readFileSync(new URL('../../frontend/src/components/FascicoliPage.tsx', import.meta.url), 'utf8')
  assert.match(pagina, /\{quadroFascicolo\}\n\s*<ControlloCatena fascicoloId=/)
  const lettura = readFileSync(new URL('../../frontend/src/components/fascicoli/LetturaFascicoloPanel.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(lettura, /<ControlloCatena/)
  const componente = readFileSync(new URL('../../frontend/src/components/fascicoli/ControlloCatena.tsx', import.meta.url), 'utf8')
  assert.doesNotMatch(componente, /return null/)
})
