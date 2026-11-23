// Technical guardrails only: parametri della ricerca nella prassi e nelle sentenze amministrative.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import { prassiQueryString, testoSuRichiestaHref } from '../../frontend/src/components/legalIntelligence/prassiData.ts'

test('la ricerca porta le parole e, se scelto, l’ente; «ga» non è un ente della prassi', () => {
  assert.equal(prassiQueryString('  contributi sindacali ', ''), '?q=contributi+sindacali')
  assert.equal(prassiQueryString('"credito d\'imposta"', 'Agenzia delle Entrate'), '?q=%22credito+d%27imposta%22&ente=Agenzia+delle+Entrate')
  assert.equal(prassiQueryString('appalti', 'ga'), '?q=appalti')
})

test('una sentenza per estremi si apre nel lettore che la scarica subito se manca', () => {
  assert.equal(testoSuRichiestaHref(' TAR Lazio ', 'n. 1.731', '2025'),
    '/api/v1/ui/giustizia-amministrativa/testo/pagina?organo=TAR+Lazio&numero=1731&anno=2025')
})
