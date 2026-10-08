import { test } from 'node:test'
import assert from 'node:assert/strict'
import { describeLocalAiStatus } from '../../frontend/src/features/impostazioni/localAi.ts'

test('il motore disponibile non rende confermate le citazioni senza fonte corrente', () => {
  const result = describeLocalAiStatus({ runtime_online: true,
    embedding_provider: { provider: 'embeddinggemma2_local', ready: true },
    source_provenance: { checked_chunks: 3, excluded_chunks: 1 },
    counts: { chunks_pending: 2 } })
  assert.equal(result.ok, false)
  assert.equal(result.status, 'warning')
  assert.match(result.message, /1 passaggio consultato non trova riscontro/)
  assert.match(result.message, /2 segmenti da indicizzare/)
})

test('il controllo della fonte ripristinato elimina il solo problema realmente superato', () => {
  const result = describeLocalAiStatus({ runtime_online: true,
    embedding_provider: { provider: 'embeddinggemma2_local', ready: true },
    source_provenance: { checked_chunks: 3, excluded_chunks: 0 },
    counts: { chunks_pending: 0, chunks_invalid: 0 } })
  assert.equal(result.ok, true)
})
