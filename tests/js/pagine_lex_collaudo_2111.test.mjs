// Collaudo a vista del 21/11/2026: «Cosa sta imparando Lex» e «Lavori automatici di Lex» senza linguaggio tecnico.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const src = resolve(import.meta.dirname, '../../frontend/src')
const leggi = (percorso) => readFileSync(`${src}/${percorso}`, 'utf8')

test('Cosa sta imparando Lex: niente sigle, indirizzi stampati o console che risponde 403', () => {
  const pagina = leggi('components/LexLearningPage.tsx')
  for (const vietata of ["'Ontologia'", 'Robots (fail-closed)', 'Oltre soglia byte', 'Citazioni normalizzate', 'Revisione umana', '{lettura.url}\n']) {
    assert.ok(!pagina.includes(vietata), vietata)
  }
  assert.match(pagina, /Apri la fonte ufficiale/)
  assert.match(pagina, /job\.console_visibile \?/)
  assert.match(pagina, /Ultimo giro:/)
})

test('Lavori automatici di Lex: niente risparmio stimato, soglie o target; ultimo giro per ogni lavoro', () => {
  const home = leggi('pages/workflow-agents/WorkflowAgentsHome.tsx')
  const anteprima = leggi('pages/workflow-agents/AgentRunPreview.tsx')
  for (const vietata of ['AgentMetricsPanel', 'riduzione stimata', 'Base manuale stimata', 'Governato', 'Scritture spente', 'Target', 'Soglia']) {
    assert.ok(!home.includes(vietata), vietata)
  }
  assert.ok(!anteprima.includes('Risparmio:'))
  assert.match(home, /Ultimo giro: \{dataOraIt/)
  assert.match(home, /presidio_mattutino/)
})
