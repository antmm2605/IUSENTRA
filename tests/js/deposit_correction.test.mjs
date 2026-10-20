import assert from 'node:assert/strict'
import { test } from 'node:test'
import { canCheckPctDeposit, depositActionMessage, depositCorrectionArea, duplicateParticipantTaxCode } from '../../frontend/src/components/depositCorrection.ts'

test('un blocco conserva errore reale anche in presenza del messaggio generico', () => {
  assert.equal(depositActionMessage({ package_ready: false, requires_guided_completion: true, errore: 'Codice fiscale ripetuto', message: 'Pacchetto preparato' }), 'Codice fiscale ripetuto')
})
test('un pacchetto positivo mantiene il risultato corrente senza riusare un errore precedente', () => {
  assert.equal(depositActionMessage({ package_ready: true, message: 'Controlli superati', errore: 'vecchio dettaglio' }), 'Controlli superati')
})
test('un errore non viene trasformato in una preparazione positiva', () => {
  assert.equal(depositActionMessage({ requires_guided_completion: true }), 'Completa i dati indicati prima di proseguire.')
})
test('riconosce il CF INPS solo nel rifiuto ministeriale dei partecipanti', () => {
  assert.equal(duplicateParticipantTaxCode("Duplicate key-sequence ['80078750587'] in unique identity-constraint '{namespace}AK_PARTECIPANTI'."), '80078750587')
  assert.equal(duplicateParticipantTaxCode('Codice fiscale 80078750587 ripetuto nei partecipanti (ControParte parte_2).'), '80078750587')
  assert.equal(duplicateParticipantTaxCode('80078750587: ricevuta di pagamento duplicata'), '')
})

test('il controllo senza firma riconosce il canale ministeriale scelto anche senza profilo Regia', () => {
  for (const channel of ['SICID', 'SIECIC', 'SIGP', 'PCT civile', 'CASSAZIONE']) assert.equal(canCheckPctDeposit(channel), true)
  for (const channel of ['', 'Canale da verificare', 'PAT', 'UNEP', 'PDP', 'non-SICID']) assert.equal(canCheckPctDeposit(channel), false)
})

test('la correzione riguarda il dato realmente rifiutato senza indirizzare il contributo alle parti', () => {
  assert.equal(depositCorrectionArea('Manca il contributo unificato.'), 'contributo')
  assert.equal(depositCorrectionArea('AK_PARTECIPANTI: codice fiscale ripetuto'), 'parti')
  assert.equal(depositCorrectionArea('Manca atto principale'), 'documenti')
  assert.equal(depositCorrectionArea('Data citazione non valida'), 'dati')
  assert.equal(depositCorrectionArea('Manca il numero di R.G..'), 'fascicolo')
})
