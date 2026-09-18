// L'unione dei messaggi della chat del portale: nessuno si perde, nessuno raddoppia.
import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  ordinaMessaggi,
  segnalibroDa,
  unisciMessaggi,
} from '../../frontend/src/lib/conversazionePortale.ts'

const studio = { id: 'm1', body: 'Buongiorno', sender_type: 'studio', created_at: '2026-09-18T16:00:00+00:00' }
const cliente = { id: 'm2', body: 'Grazie', sender_type: 'cliente', created_at: '2026-09-18T16:00:05+00:00' }

test('il messaggio nuovo si aggiunge in coda', () => {
  const unione = unisciMessaggi([studio], [cliente])
  assert.deepEqual(unione.map((m) => m.id), ['m1', 'm2'])
})

test('il messaggio di confine che torna indietro non raddoppia', () => {
  // La coda comprende l'ultimo secondo gia' visto: il server rimanda m2.
  const unione = unisciMessaggi([studio, cliente], [cliente])
  assert.deepEqual(unione.map((m) => m.id), ['m1', 'm2'])
})

test('due messaggi nello stesso secondo restano entrambi', () => {
  const simultaneo = { id: 'm3', body: 'Promemoria', sender_type: 'studio', created_at: cliente.created_at }
  const unione = unisciMessaggi([studio, cliente], [cliente, simultaneo])
  assert.deepEqual(unione.map((m) => m.id), ['m1', 'm2', 'm3'])
})

test('la versione arrivata dal server sostituisce quella gia' + "'" + ' mostrata', () => {
  const corretto = { ...cliente, body: 'Grazie, ci sarò.' }
  const unione = unisciMessaggi([cliente], [corretto])
  assert.equal(unione.length, 1)
  assert.equal(unione[0].body, 'Grazie, ci sarò.')
})

test('l' + "'" + 'ordine e' + "'" + ' cronologico anche se arrivano al contrario', () => {
  assert.deepEqual(ordinaMessaggi([cliente, studio]).map((m) => m.id), ['m1', 'm2'])
})

test('a parita' + "'" + ' di istante decide l' + "'" + 'identificativo, senza scambi casuali', () => {
  const primo = { id: 'a', created_at: '2026-09-18T16:00:00+00:00' }
  const secondo = { id: 'b', created_at: '2026-09-18T16:00:00+00:00' }
  assert.deepEqual(ordinaMessaggi([secondo, primo]).map((m) => m.id), ['a', 'b'])
})

test('il segnalibro e' + "'" + ' l' + "'" + 'istante dell' + "'" + 'ultimo messaggio, vuoto se non ce ne sono', () => {
  assert.equal(segnalibroDa([studio, cliente]), '2026-09-18T16:00:05+00:00')
  assert.equal(segnalibroDa([]), '')
})

test('un messaggio senza identificativo non fa sparire gli altri', () => {
  const senzaId = { body: 'anonimo', created_at: '2026-09-18T16:00:09+00:00' }
  const unione = unisciMessaggi([studio], [senzaId])
  assert.equal(unione.length, 2)
})
