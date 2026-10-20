# SICID 19 ottobre 2026 e correzione errori deposito

## Risultato richiesto

Usare il pacchetto XSD ufficiale entrato in esercizio il 19 ottobre e intercettare
il duplicato dei partecipanti con spiegazione e correzione nel contesto del fascicolo.
Solo requisiti effettivamente obbligatori per l'atto selezionato; nessun nuovo vincolo
sui campi facoltativi. Firma, cifratura e trasporto PEC restano invariati.

## Fonti e confronto

Pacchetto XSD_SICI_20260720.zip, SHA256
83E5CA05691E9D1E0422DE84695ED8FDAB4AA1E080E2FCCA9DDAC9E9BA11A264.
Fonte: [PST NWS5167](https://pst.giustizia.it/PST/page/it/processo_civile_telematico__comunicazione_alle_software_house_aggiornamento_specifiche_tecniche_deposito_atti_sicid_it_4?contentId=NWS5167&modelId=4).
156 schemi originali: rispetto a maggio cambiano solo tipi-base.xsd (13 nuovi codici)
ed eventi.xsd (Documentazione InfoCamere). Catalogo tecnico e UI allineati a 835 codici
SICID, 1031 totali. Anticipazione di giugno non attivata.

## Comportamento

La validazione XSD finale esistente resta l'autorità. Il messaggio aggiunge CF,
nome, riga e riferimento dei partecipanti esclusivamente dopo il rifiuto ufficiale
AK_PARTECIPANTI; non unisce né elimina automaticamente parti. Gli errori effettivi
non vengono sostituiti dal messaggio generico «pacchetto preparato».
Le correzioni aprono le schede native conservando la bozza. Lo scollegamento è
esplicito, limitato al fascicolo, controlla la revisione e conserva soggetto e altri
collegamenti. Le fonti di correzione non usano la lista visuale che deduplica i nomi.
Il controllo facoltativo usa la modalità esistente prova_senza_invio; non richiama
i ponti di firma o PEC e non considera completo un pacchetto ancora da firmare.

## Guardrail tecnici eseguiti

- 41 test mirati XSD, cataloghi, campi SICID, duplicati, firma gate e provenienza.
- 22 test anagrafica ministeriale esistente.
- 411 test frontend e 8 sulle dipendenze, typecheck/build e controlli condivisi.
- Correzione collegamenti: SQLite verificato, PostgreSQL ancora da provare localmente.
- Confronto dei moduli firma/trasporto con il rilascio locale precedente: nessuna modifica.

## Accettazione reale e rilascio

Ancora da eseguire sulla copia aggiornata 127.0.0.1:8080: dati validi, errori diversi,
risposte e correzioni suggerite, salvataggio, riapertura e prova senza invio.
Commit, deploy di questa modifica e pulizia finale ancora da eseguire.
Nessuna dichiarazione di completamento sulla base dei soli test tecnici.

## Aggiornamento collaudo 20 ottobre 2026

- Schemi attivi: audit canonico su 283 voci, 282 eseguibili e verificate; nessun errore nell'audit. Il conteggio non certifica operazioni giudiziarie reali.
- Rimossi i campi generici non consumati per i 32 tipi SICID censiti: il test confronta lo stesso XML prima e dopo la rimozione dei valori e ne valida la conformità XSD. Per le citazioni resta la data richiesta da Datacitazione; il valore già presente nel fascicolo è riutilizzato senza sovrascrivere una scelta salvata nella busta.
- I gruppi interamente facoltativi sono chiusi sotto «Altri dati, solo se pertinenti». Nessun valore viene cancellato. La validazione finale e i moduli firma/trasporto rimangono invariati.
- La rigenerazione del profilo tecnico del fascicolo conserva preparazione, selezione documenti e dati busta. Test SQL con modifica effettiva dell'ufficio e confronto del dato persistito: superato.
- Test mirati più recenti: 62 campi/catalogo/duplicati/contributo, 9 profilo deposito, 413 frontend e 8 dipendenze; build/typecheck e controlli frontend superati. Correzione concorrente verificata anche sul repository PostgreSQL controllato.

### Osservato personalmente sul browser reale 8080

Caso controllato 443BCDCA, unico PDF di collaudo C83E1CBA, senza firma o invio PEC reale:

1. Citazione: non compaiono Istanza e Data dell'atto; compare la sola Data di notificazione, già valorizzata dal dato del fascicolo 19/10/2026. Classificazione salvata.
2. Memoria ex art. 171-ter n. 1: un solo atto principale, nessuna richiesta della data di notificazione, del contributo o dell'autocertificazione. Il controllo senza invio restituisce il requisito effettivamente mancante: atto principale non firmato.
3. Dati facoltativi: Sub-procedimento assente dalla vista ordinaria, accessibile aprendo la sezione facoltativa, richiudibile senza modificare i dati.
4. Modifica nativa del fascicolo e successiva riapertura del deposito: tipo Memoria, documento selezionato e dati preparazione conservati. Il numero controllato è stato variato e poi ripristinato; nessun fascicolo reale modificato per questa prova.

Rimangono da documentare in browser il percorso completo di correzione del CF duplicato e il successivo esito del controllo, oltre a commit, gate remoti, riallineamento locale/server e pulizia finale. La prova tecnica AK_PARTECIPANTI non viene presentata come prova visiva del percorso completo. L'incarico complessivo resta aperto.
