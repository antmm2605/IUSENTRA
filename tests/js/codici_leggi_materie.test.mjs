import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupByMateria } from '../../frontend/src/components/codiciLeggiGruppi.ts'
import { matchesCatalogueAct } from '../../frontend/src/components/codiciLeggiSearch.ts'

const a = (id, label, materia, tipo) => ({ id, label, title: label, articles: 1, category: '', materia, tipo })
test('le materie seguono l’ordine dichiarato e i codici precedono leggi e decreti', () => {
  const groups = groupByMateria([
    a(1, 'Statuto dei lavoratori', 'Lavoro e previdenza', 'Legge'),
    a(2, 'Codice civile', 'Diritto civile', 'Codice'),
    a(3, 'Locazioni abitative', 'Diritto civile', 'Legge'),
    a(4, 'Senza materia', undefined, 'Legge'),
  ])
  assert.deepEqual(groups.map(g => g.materia), ['Diritto civile', 'Lavoro e previdenza', 'Altre norme'])
  assert.deepEqual(groups[0].acts.map(x => x.id), [2, 3])
})
test('la ricerca trova gli atti anche per materia e tipo', () => {
  const act = a(5, 'Disciplina dei licenziamenti individuali', 'Lavoro e previdenza', 'Legge')
  assert.equal(matchesCatalogueAct(act, 'lavoro'), true)
  assert.equal(matchesCatalogueAct(act, 'decreto legislativo'), false)
})
