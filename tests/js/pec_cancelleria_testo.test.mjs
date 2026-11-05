// Testo della PEC di cancelleria leggibile per l'avvocato (frontend/src/features/comunicazioni/testoPec.ts).
import assert from 'node:assert/strict'
import test from 'node:test'
import { etichettaTecnica, formattaTestoPec, fraseDelRegistro, nomeProprio, sezioneLeggibile } from '../../frontend/src/features/comunicazioni/testoPec.ts'

const CORPO = 'Messaggio di posta certificata Il giorno 05/11/2026 alle ore 11:20:06 (+0100) il messaggio "COMUNICAZIONE 1/2026/LAV" '
  + 'è stato inviato da "tribunale.vicenza@civile.ptel.giustiziacert.it" ed indirizzato a: studio@pec.it Il messaggio originale è incluso '
  + 'in allegato. Identificativo messaggio: 5EF0A4E9.prova@legalmail.it L\'allegato daticert.xml contiene informazioni di servizio. '
  + '----- Certified email message On 05/11/2026 at 11:20:06 (+0100) the message "COMUNICAZIONE 1/2026/LAV" was sent by x. '
  + 'Tribunale Ordinario di Vicenza. -- Comunicazione di cancelleria Sez/Coll.: 01 Tipo procedimento: Diritto del Lavoro '
  + 'Numero di Ruolo generale: 1/2026 Giudice: ROSSI MARIO Ricorr. principale: BIANCHI ANNA Resist. principale: AVVOCATURA '
  + 'DISTRETTUALE DI VENEZIA Oggetto: RIASSEGNAZIONE TERMINE PER NOTE Descrizione: RIASSEGNATO TERMINE il 23/11/2026 14:00 '
  + 'Note: Notificato alla PEC -- Si vedano gli eventuali allegati. Si prega di non replicare a questo messaggio automatico. '
  + 'Per ulteriori informazioni: http://pst.giustizia.it/ -- Comunicazione di cancelleria Sez/Coll.: 01 Tipo procedimento: Diritto del Lavoro'

test('la consegna in una riga, senza la copia in inglese del gestore', () => {
  const { consegna } = formattaTestoPec(CORPO)
  assert.equal(consegna, 'Consegnata il 05/11/2026 alle 11:20: «COMUNICAZIONE 1/2026/LAV», da tribunale.vicenza@civile.ptel.giustiziacert.it a studio@pec.it. Identificativo: 5EF0A4E9.prova@legalmail.it')
  assert.doesNotMatch(consegna, /Certified/)
})

test('i campi della comunicazione una volta sola, nell’ordine del registro', () => {
  const { campi, avvertenze } = formattaTestoPec(CORPO)
  assert.deepEqual(campi.map(([etichetta]) => etichetta), ['Sezione / collegio', 'Tipo di procedimento', 'Numero di ruolo', 'Giudice', 'Ricorrente', 'Resistente', 'Oggetto', 'Descrizione', 'Note'])
  assert.equal(Object.fromEntries(campi)['Numero di ruolo'], '1/2026')
  assert.equal(Object.fromEntries(campi)['Note'], 'Notificato alla PEC')
  assert.equal(avvertenze.length, 3)
})

test('nomi propri, registro in carattere normale, sezione e file tecnici', () => {
  assert.equal(nomeProprio('TRIBUNALE ORDINARIO DI VICENZA'), 'Tribunale Ordinario di Vicenza')
  assert.equal(nomeProprio("MINISTERO DELL'ISTRUZIONE E DEL MERITO"), "Ministero dell'Istruzione e del Merito")
  assert.equal(fraseDelRegistro('RIASSEGNATO TERMINE PER NOTE il 23/11/2026 14:00, ADEMPIMENTI RG 1/2026'), 'Riassegnato termine per note il 23/11/2026 14:00, adempimenti RG 1/2026')
  assert.equal(fraseDelRegistro('Testo già normale'), 'Testo già normale')
  assert.equal(sezioneLeggibile('01'), 'sezione 01')
  assert.equal(etichettaTecnica('daticert.xml'), 'Ricevuta del gestore PEC')
  assert.equal(etichettaTecnica('2276942s.pdf.zip'), '')
})
