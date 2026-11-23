// Technical guardrails only: parametri della ricerca nella prassi e nelle sentenze amministrative.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { prassiQueryString } from '../../frontend/src/components/legalIntelligence/prassiData.ts'

test('la ricerca porta le parole e, se scelto, l’ente; «ga» non è un ente della prassi', () => {
  assert.equal(prassiQueryString('  contributi sindacali ', ''), '?q=contributi+sindacali')
  assert.equal(prassiQueryString('"credito d\'imposta"', 'Agenzia delle Entrate'), '?q=%22credito+d%27imposta%22&ente=Agenzia+delle+Entrate')
  assert.equal(prassiQueryString('appalti', 'ga'), '?q=appalti')
})
