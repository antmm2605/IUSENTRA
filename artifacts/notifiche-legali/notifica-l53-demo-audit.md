# Demo notifiche legali L. 53/1994

Generato il 2026-05-23T18:25:03+00:00.

Scenario: demo controllata, nessun invio PEC reale e nessun deposito su portali esterni.

## Passaggi notifica
1. Precompilazione da pratica e studio - IUSENTRA propone avvocato, assistito, procedimento, destinatario e documenti già presenti nel fascicolo. [L. 53/1994, art. 3-bis, commi 5 e 6]
2. Documento rilasciato dall'ufficio - Quando il fascicolo segnala un documento d'ufficio da notificare, il percorso richiede l'acquisizione governata dal Portale Servizi prima di generare la relata. [D.M. 44/2011, art. 18; specifiche tecniche art. 19-bis]
3. Verifica PEC su pubblico elenco - Il percorso registra fonte, data e ora della verifica dell'indirizzo PEC del mittente e del destinatario. [L. 53/1994, art. 3-bis, comma 1; D.L. 179/2012, art. 16-ter]
4. Preparazione allegati - Sono ammessi più documenti; per ciascun file vengono riportati nome, origine, eventuale attestazione e impronta SHA-256 quando disponibile. [Specifiche tecniche D.M. 44/2011, art. 19-bis]
5. Relata separata e attestazioni - Il sistema genera la relata separata e le attestazioni richieste; l'avvocato rivede e firma digitalmente prima dell'invio. [L. 53/1994, art. 3-bis, commi 2 e 5]
6. PEC con oggetto obbligatorio - L'oggetto è fissato alla formula prevista e la ricevuta richiesta resta completa. [L. 53/1994, art. 3-bis, commi 3 e 4; D.M. 44/2011, art. 18, comma 6]
7. Pacchetto prova e deposito - Dopo l'invio si conservano PEC inviata, RAC e RdAC complete in originale digitale e si prepara l'indicizzazione per il deposito. [L. 53/1994, art. 9; Specifiche tecniche D.M. 44/2011, art. 19-bis, comma 5]

## Verifiche notifica
- Oggetto PEC obbligatorio: superato (L. 53/1994, art. 3-bis, comma 4)
- PEC notificante da pubblico elenco: superato (L. 53/1994, art. 3-bis, comma 1)
- PEC destinatario e fonte: superato (D.L. 179/2012, art. 16-ter)
- Allegati della notifica: superato (Specifiche tecniche D.M. 44/2011, art. 19-bis)
- Documento ufficio acquisito: superato (D.M. 44/2011, art. 18; specifiche tecniche art. 19-bis)
- Attestazioni di conformità: superato (L. 53/1994, art. 3-bis, comma 2)
- Relata separata e firma digitale: superato (L. 53/1994, art. 3-bis, comma 5)
- RdAC completa: superato (D.M. 44/2011, art. 18, comma 6)

## Audit notifica
- Esito: superato
- Allegati controllati: 3
- Acquisizione documento ufficio: True
- Cartella prova prevista: notifica_23-05-2026_controparte_s_p_a

## Acquisizione Portale Servizi
- Il monitor fascicolo rileva il documento d'ufficio rilasciato.
- La notifica di sistema apre il collegamento precompilato con fascicolo, numero RG e ufficio.
- L'avvocato accede con credenziali personali e scarica/importa il documento.
- Il documento acquisito viene inserito nei documenti della relata ed è tracciato nell'audit.

## Passaggi deposito prova
1. Raccolta atti notificati - La prova può includere più atti o allegati notificati, con nome e impronta SHA-256. [Specifiche tecniche D.M. 44/2011, art. 19-bis, comma 5]
2. Ricevute originali - Per ogni destinatario servono RAC e RdAC completa in formato originale digitale .eml o .msg. [L. 53/1994, art. 3-bis, comma 3; D.M. 44/2011, art. 18, comma 6]
3. Indicizzazione ricevute - I riferimenti delle ricevute sono preparati per il file DatiAtto.xml della busta telematica. [Specifiche tecniche D.M. 44/2011, art. 19-bis, comma 5]
4. Audit e controllo finale - Il pacchetto prova registra file, impronte e controlli prima del deposito. [L. 53/1994, art. 9]

## Verifiche deposito prova
- Atti notificati: superato (Specifiche tecniche D.M. 44/2011, art. 19-bis, comma 5)
- Relata firmata: superato (L. 53/1994, art. 3-bis, comma 5)
- PEC inviata: superato (L. 53/1994, art. 3-bis, comma 3)
- RAC e RdAC originali: superato (L. 53/1994, art. 9; D.M. 44/2011, art. 18, comma 6)
- Impronte SHA-256: superato (Audit interno IUSENTRA)
- Riferimenti DatiAtto.xml: superato (Specifiche tecniche D.M. 44/2011, art. 19-bis, comma 5)

## Audit deposito prova
- Esito: superato
- File pacchetto prova: 10
- Anomalie: 0 blocchi, 0 avvisi

## Fonti normative operative
- Portale Servizi Telematici, Notifiche in proprio degli avvocati: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC432&modelId=12
- L. 53/1994, art. 3-bis e art. 9; D.L. 179/2012, art. 16-ter; D.M. 44/2011 e specifiche tecniche art. 18 e 19-bis.
