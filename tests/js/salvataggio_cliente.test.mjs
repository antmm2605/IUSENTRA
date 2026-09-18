// Technical guardrails only: dove si finisce dopo «Salva modifiche» nella scheda cliente.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  destinazioneDopoSalvataggio,
  destinazioneInterna,
  messaggioSalvataggio,
} from '../../frontend/src/lib/salvataggioCliente.ts'

test('in modifica si resta sulla scheda: chi corregge non va buttato fuori dal modulo', () => {
  assert.equal(destinazioneDopoSalvataggio({ mode: 'edit', query: { idCliente: 'FBA5C7FF' } }), null)
  assert.equal(destinazioneDopoSalvataggio({ mode: 'edit', query: { idCliente: 'FBA5C7FF' }, nextUrl: '' }), null)
})

test('in creazione si va alla cartella del cliente appena nato', () => {
  assert.equal(destinazioneDopoSalvataggio({ mode: 'create', idSalvato: 'FBA5C7FF' }), '/clienti/FBA5C7FF')
  assert.equal(destinazioneDopoSalvataggio({ mode: 'create' }), '/clienti')
})

test('un identificativo con caratteri strani non rompe il percorso', () => {
  assert.equal(destinazioneDopoSalvataggio({ mode: 'create', idSalvato: 'a b/c' }), '/clienti/a%20b%2Fc')
})

test('se la scheda e\' stata aperta da un\'altra pagina, si torna li\'', () => {
  assert.equal(
    destinazioneDopoSalvataggio({ mode: 'edit', query: { idCliente: 'X' }, nextUrl: '/fascicoli/5E864356' }),
    '/fascicoli/5E864356',
  )
})

test('il ritorno esce dal gestionale solo se e\' davvero interno', () => {
  // Il momento in cui l'utente uscirebbe e' subito dopo un salvataggio
  // riuscito, cioe' quando si fida di quello che vede.
  for (const ostile of [
    'https://esterno.example/x',
    '//esterno.example',
    '/\\esterno.example',
    '/\tevil',
    '/a/../../etc',
    'javascript:alert(1)',
  ]) {
    assert.equal(destinazioneInterna(ostile), null, `accettato: ${ostile}`)
    assert.equal(
      destinazioneDopoSalvataggio({ mode: 'edit', query: { idCliente: 'X' }, nextUrl: ostile }),
      null,
      `navigato fuori con: ${ostile}`,
    )
  }
})

test('un percorso interno vero passa, con gli spazi attorno ripuliti', () => {
  assert.equal(destinazioneInterna('  /clienti  '), '/clienti')
  assert.equal(destinazioneInterna('/fascicoli/5E864356/modifica'), '/fascicoli/5E864356/modifica')
  assert.equal(destinazioneInterna(''), null)
  assert.equal(destinazioneInterna(null), null)
})

test('il messaggio dice quello che e\' successo davvero', () => {
  assert.equal(messaggioSalvataggio(null), 'Modifiche salvate.')
  assert.equal(messaggioSalvataggio('/clienti/X'), 'Cliente salvato.')
  assert.equal(messaggioSalvataggio(null, 'Cliente aggiornato.'), 'Cliente aggiornato.')
})
