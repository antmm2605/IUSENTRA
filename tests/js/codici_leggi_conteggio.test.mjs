// Collaudo 21/11/2026: durante il caricamento del catalogo compariva «0 articoli trovati».
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { articoliTrovati } from '../../frontend/src/components/codiciLeggiResults.ts'

test('mentre il catalogo si carica non si dice «0 articoli trovati»', () => {
  assert.equal(articoliTrovati(false, true, { total: 0 }), 'Caricamento del catalogo normativo…')
  assert.equal(articoliTrovati(true, true, { total: 0 }), 'Ricerca in corso…')
  assert.equal(articoliTrovati(false, false, { total: 0 }), '0 articoli trovati')
  assert.equal(articoliTrovati(false, false, { total: 1 }), '1 articolo trovato')
})

test('oltre la soglia il conteggio è dichiarato come limite', () => {
  assert.match(articoliTrovati(false, false, { total: 1000, total_oltre: true }), /^Più di 1\.?000 articoli/)
})

test('nomi delle pagine coerenti con il menu e senza diciture tecniche', () => {
  const src = resolve(import.meta.dirname, '../../frontend/src')
  const apprendimento = readFileSync(`${src}/components/LexLearningPage.tsx`, 'utf8')
  const lavori = readFileSync(`${src}/pages/workflow-agents/WorkflowAgentsHome.tsx`, 'utf8')
  assert.match(apprendimento, /Cosa sta imparando Lex<\/h1>/)
  assert.match(lavori, /title="Lavori automatici di Lex"/)
  for (const vietata of ['Apprendimento Lex</h1>', 'Robots.txt', 'rate-limit', 'policy,', 'fuori policy', 'job notturno dalla']) assert.ok(!apprendimento.includes(vietata), vietata)
  for (const vietata of ['Regia Agentica', "'Governato'", 'Scritture spente']) assert.ok(!lavori.includes(vietata), vietata)
})
