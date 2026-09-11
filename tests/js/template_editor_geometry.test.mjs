// Technical guardrails only: geometria reale della pagina dell'editor atti.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildPageMetrics,
  clampZoom,
  countWords,
  fitWidthZoom,
  mmToPx,
  pageCountForContentEnd,
  pageIndexAt,
  stackHeight,
  writableBottom,
  writableTop,
} from '../../frontend/src/components/templateEditor/pageGeometry.ts'

const margins = { top: 25, right: 22, bottom: 25, left: 32 }

test('A4 verticale e orizzontale in millimetri reali', () => {
  const portrait = buildPageMetrics({ orientation: 'verticale', margins })
  const landscape = buildPageMetrics({ orientation: 'orizzontale', margins })
  assert.equal(Math.round(portrait.widthPx), Math.round(mmToPx(210)))
  assert.equal(Math.round(portrait.heightPx), Math.round(mmToPx(297)))
  assert.equal(Math.round(landscape.widthPx), Math.round(mmToPx(297)))
  assert.equal(Math.round(portrait.contentWidthPx), Math.round(mmToPx(210 - 22 - 32)))
})

test('area scrivibile rispetta margini, timbro e spazio tra i fogli', () => {
  const metrics = buildPageMetrics({ orientation: 'verticale', margins, headerReservePx: 40, gapPx: 32 })
  assert.ok(metrics.contentTopPx > metrics.marginTopPx + 40)
  assert.equal(writableTop(1, metrics), metrics.stridePx + metrics.contentTopPx)
  assert.equal(writableBottom(0, metrics), metrics.heightPx - metrics.marginBottomPx)
  assert.equal(pageIndexAt(metrics.stridePx - 1, metrics), 0)
  assert.equal(pageIndexAt(metrics.stridePx + 1, metrics), 1)
  assert.equal(stackHeight(3, metrics), (metrics.heightPx * 3) + (32 * 2))
  assert.equal(pageCountForContentEnd(writableBottom(1, metrics), metrics), 2)
})

test('timbro enorme lascia comunque spazio al testo', () => {
  const metrics = buildPageMetrics({ orientation: 'orizzontale', margins, headerReservePx: 5000 })
  assert.ok(metrics.contentHeightPx >= mmToPx(40) - 0.001)
})

test('zoom adatta alla larghezza del telefono senza restringere la pagina', () => {
  const metrics = buildPageMetrics({ orientation: 'verticale', margins })
  const zoom = fitWidthZoom(390, metrics)
  assert.ok(zoom > 0.4 && zoom < 0.5)
  assert.equal(clampZoom(9), 2)
  assert.equal(clampZoom(0.01), 0.3)
  assert.equal(clampZoom(Number.NaN), 1)
})

test('conteggio parole italiano', () => {
  assert.equal(countWords("L'avvocato  deposita l'atto n. 12/2026"), 5)
  assert.equal(countWords(''), 0)
})
