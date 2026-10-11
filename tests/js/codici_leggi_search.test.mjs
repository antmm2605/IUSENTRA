import { test } from 'node:test'
import assert from 'node:assert/strict'
import { matchesCatalogueAct, normaliseCatalogueText } from '../../frontend/src/components/codiciLeggiSearch.ts'

const act = (key, label) => ({ key, label, title: label })
test('privacy e ambiente trovano i codici dal nome ufficiale differente', () => {
  assert.equal(matchesCatalogueAct(act('codice_privacy', 'Codice in materia di protezione dei dati personali'), 'privacy'), true)
  assert.equal(matchesCatalogueAct(act('152/2006', 'Norme in materia ambientale'), 'ambiente'), true)
  assert.equal(matchesCatalogueAct(act('codice_penale', 'Codice penale'), 'privacy'), false)
})
test('appalti comprende le tre edizioni senza confonderle con altri codici', () => {
  const rows = [act('36/2023', 'Codice dei contratti pubblici — 2023'), act('50/2016', 'Codice dei contratti pubblici — 2016'), act('contratti_163_2006', 'Codice dei contratti pubblici — 2006 (storico)'), act('codice_civile', 'Codice civile')]
  assert.deepEqual(rows.filter(a => matchesCatalogueAct(a, 'appalti')).map(a => a.key), ['36/2023', '50/2016', 'contratti_163_2006'])
})
test('CAD e abbreviazioni restituiscono gli atti rispettivi', () => {
  for (const [key, label, query] of [['82/2005', 'Codice dell’amministrazione digitale', 'CAD'], ['codice_civile', 'Codice civile', 'cc'], ['codice_procedura_civile', 'Codice di procedura civile', 'cpc'], ['codice_penale', 'Codice penale', 'cp'], ['codice_procedura_penale', 'Codice di procedura penale', 'cpp'], ['codice_processo_amministrativo', 'Codice del processo amministrativo', 'cpa']]) assert.equal(matchesCatalogueAct(act(key, label), query), true)
})
test('sigle brevi non corrispondono ad altre sigle più lunghe', () => {
  assert.equal(matchesCatalogueAct(act('codice_procedura_penale', 'Codice di procedura penale'), 'cp'), false)
  assert.equal(matchesCatalogueAct(act('codice_procedura_civile', 'Codice di procedura civile'), 'cc'), false)
})

test('titoli letterali, accenti e apostrofi conservano la normalizzazione del catalogo', () => {
  assert.equal(normaliseCatalogueText('PROPRIETÀ dell’impresa'), "proprieta dell'impresa")
  assert.equal(matchesCatalogueAct(act('30/2005', 'Codice della proprietà industriale'), 'proprieta industriale'), true)
  assert.equal(matchesCatalogueAct(act('codice_strada', 'Codice della strada'), ''), true)
})
