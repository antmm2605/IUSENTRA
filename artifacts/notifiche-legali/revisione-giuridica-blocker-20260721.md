# Revisione giuridica dei presìdi PEC — blocchi anti-regressione

Data di verifica tecnica: 21/07/2026.

## Perimetro corretto

1. La prova completa di una notifica non viene più ricostruita sommando parole presenti in documenti o attività indipendenti dello stesso fascicolo. La chiusura automatica richiede una catena strutturata unica con:
   - identificativo della stessa notifica;
   - legame dell'atto e della relata alla PEC sorgente o allo stesso hash dell'atto;
   - invio ai sensi della Legge 53/1994;
   - RAC e RdAC correlate allo stesso Message-ID dell'invio;
   - identità coincidente del destinatario tra invio e RdAC;
   - assenza di un esito negativo nella medesima catena.
2. Il cutoff storico del 19/07/2026 resta una regola di migrazione e non costituisce prova di esecuzione. Una PEC ancora operativa o una richiesta espressa di notifica rimane aperta senza prova completa; ciò copre anche il caso Alfano RG 1100/2026.
3. P.Q.M., dispositivo o richiamo isolato all'art. 429 c.p.c. non sono sufficienti a qualificare il documento come sentenza. La qualificazione richiede segnali decisori congiunti nella stessa fonte. Un provvedimento ex art. 127-ter c.p.c. continua quindi a generare il relativo termine per le note scritte quando non contiene una decisione effettiva.
4. Gli allegati vengono legati conservativamente all'evento corrente. Un'ordinanza operativa ex art. 127-ter c.p.c. non viene contaminata da una sentenza storica contenuta in un allegato separato; le fonti incompatibili e non correlate producono revisione conservativa, non una promozione automatica a sentenza.

## Fonti normative governate dal rulepack

Le regole relative alla comunicazione, notificazione della sentenza e termini di impugnazione citano le fonti già censite nel registro ufficiale del progetto: artt. 133, 285, 325, 326 e 429 c.p.c., oltre alla Legge 53/1994 per la catena PEC. Il rulepack è stato portato alla versione `legal_notification_detection_rules_v1.0.2` e non ammette più P.Q.M. o art. 429 isolati come segnali decisori autonomi.

## Dati e casi di regressione verificati

- evento PEC antecedente al cutoff ma ancora operativo, senza prova completa;
- richiesta espressa di notifica antecedente al cutoff;
- sentenza a verbale ex art. 429 con segnali decisori congiunti;
- P.Q.M. e richiamo all'art. 429 all'interno di un provvedimento ex art. 127-ter, senza sentenza;
- ordinanza corrente ex art. 127-ter e sentenza storica in due allegati separati;
- catena completa atto/relata/invio/RAC/RdAC riferita allo stesso atto;
- due notifiche complete ma indipendenti nello stesso fascicolo, riferite allo stesso atto ma a destinatari diversi da quello del presidio corrente.

## Verifiche automatiche eseguite

Comando mirato:

```text
python -m pytest -q tests/test_legal_notification_rulepack.py tests/test_pec_legal_event_understanding.py tests/test_pec_legal_deadline_proposer.py tests/test_pec_notification_presidio.py
```

Esito: 64 test superati.

Compatibilità mirata con la pipeline PEC già esistente:

```text
python -m pytest -q tests/test_pec_audit_pipeline.py::test_presidio_documentale_esclude_termine_pregresso_da_sentenza_decisoria tests/test_pec_audit_pipeline.py::test_sentenza_a_verbale_127_ter_non_diventa_udienza_audiovisiva tests/test_pec_audit_pipeline.py::test_sentenza_corrente_non_diventa_udienza_per_un_allegato_storico tests/test_pec_control_tower.py::test_pec_control_tower_sentenza_cancelleria_non_diventa_provvedimento_generico tests/test_pec_operational_chain.py::test_remote_127_audit_ignores_written_hearing_and_detects_decisory_misclassification
```

Esito: ulteriori 5 test superati.

Controlli aggiuntivi:

```text
python -m py_compile pct/pec_pipeline.py pct/pec_legal_event_understanding.py pct/pec_notification_presidio/historical_policy.py
git diff --check -- <file del perimetro>
```

Esito: nessun errore di sintassi e nessun errore di whitespace nel perimetro.

## Prova reale e limiti residui

La prova visuale sulla macchina reale `127.0.0.1:8080` non appartiene a questa tranche backend e non è stata eseguita da questo sotto-incarico. Il lavoro non viene quindi dichiarato accettato lato utente sulla sola base dei test automatici. Restano da verificare nella campagna end-to-end finale del task principale: materializzazione visibile del caso Alfano, terminologia in Agenda/Scadenziario e apertura della fonte corretta.

Il contratto è intenzionalmente conservativo: dati legacy privi degli identificativi strutturati non possono chiudere automaticamente un presidio. Devono restare da esaminare o essere riallineati con una catena probatoria strutturata; un testo libero o un nome file non è considerato prova completa.

## Rafforzamento P1 del 22/07/2026

La revisione indipendente ha individuato quattro ulteriori condizioni di falso positivo. Sono state corrette con i seguenti vincoli:

1. **Notifica a più destinatari.** La prova completa richiede, per ogni destinatario atteso o correlato, la stessa coppia strutturata `Message-ID + identità destinatario` nell'invio ex Legge 53/1994 e nella relativa RdAC, oltre alla RAC dello stesso invio. Una sola RdAC non chiude più una notifica indirizzata a due destinatari; il presidio resta `DETECTED`. I candidati multipli con destinatari privi di identità strutturata restano aperti per verifica.
2. **Ordinanza corrente e sentenza storica.** Il binding dell'allegato operativo riconosce anche rinvio e fissazione dell'udienza, non soltanto la trattazione scritta ex art. 127-ter c.p.c. Un'ordinanza corrente di rinvio viene selezionata come fonte operativa e la sentenza storica separata viene esclusa; non nasce quindi un candidato `judgment_to_notify_review` estraneo all'evento corrente.
3. **Riparazione delle vecchie scadenze Control Tower.** La sola distanza temporale di 180 secondi non è più sufficiente. La riparazione è ammessa con identificativo PEC, Message-ID header o hash evento deterministico; per le sole righe legacy senza fonte è necessario un fascicolo certo e un solo messaggio compatibile nella finestra temporale. Senza tali condizioni la scadenza non viene mutata e resta da verificare.
4. **Documento composto ricorso + provvedimento.** La parola `ricorso` nel nome del file non annulla più un segmento ufficiale esplicito dello stesso documento. Un file composto, quale `Ricorso e decreto di fissazione udienza.pdf`, è operativo soltanto quando il contesto locale contiene l'ordine autoritativo del giudice; il ricorso puro resta escluso e il decreto puro resta ammesso.

### Verifiche automatiche del rafforzamento

Nuove regressioni materiali:

- due destinatari e una sola RdAC: prova incompleta e presidio aperto;
- ordinanza di rinvio corrente più sentenza storica separata: nessuna notifica della sentenza storica;
- due PEC ravvicinate con fascicolo assente: nessuna riparazione della scadenza generica;
- ricorso puro, decreto puro e file combinato ricorso + decreto con ordine espresso.

Comando esteso:

```text
python -m pytest -q tests/test_legal_notification_rulepack.py tests/test_pec_legal_event_understanding.py tests/test_pec_legal_deadline_proposer.py tests/test_pec_notification_presidio.py tests/test_pec_deadline_legacy_repair.py <cinque test mirati del presidio documentale>
```

Esito: **74 test superati**.

Compatibilità mirata con la pipeline PEC: ulteriori **5 test superati**. Sono stati inoltre eseguiti `py_compile` e `git diff --check` sul perimetro modificato. La prova visuale reale su `127.0.0.1:8080` resta demandata alla campagna end-to-end del task principale e non viene sostituita dai test automatici qui documentati.

## Proiezione unica tra fascicolo e presidio PEC del 22/07/2026

Il materializzatore non pubblica più due volte lo stesso adempimento quando il controllo storico dei documenti del fascicolo e il presidio PEC avanzato descrivono la stessa fonte e lo stesso stadio operativo. Il presidio avanzato è autoritativo soltanto con una correlazione strutturata e conservativa:

- tenant del job già risolto e isolato;
- identificativo fascicolo identico;
- stadio operativo identico;
- identificativo PEC coincidente, se disponibile;
- documento sorgente univoco e coincidente, se disponibile; i contenitori tecnici `.zip`, `.p7m`, `.p7s` e `.smime` non cambiano l'identità del documento interno;
- nessun conflitto tra famiglia dell'atto, identificativo PEC e documento.

Se una PEC, un documento o lo stadio differiscono, le due attività restano separate. Quando invece la proiezione legacy viene sostituita, la relativa notifica viene fatta scadere dalla sincronizzazione e l'eventuale vecchia scadenza `IUSENTRA_LEGAL_NOTIFICATION:legal-notification:...` viene completata; la scadenza attiva conserva il marker del presidio avanzato, `PEC_AUDIT` e il nome della fonte PEC. Nessun documento o dato del fascicolo viene cancellato.

Verifica automatica mirata:

```text
python -m pytest tests/test_notification_relata_materializer.py -q
```

Esito: **18 test superati**, inclusi il caso `C3565650` con `19040620s.pdf` nel fascicolo e `19040620s.pdf.zip` nel presidio PEC, la riconciliazione del marker legacy già pubblicato e il controcaso con PEC/documento distinti nello stesso fascicolo e stadio. Sono passati anche `py_compile` e `git diff --check` sul perimetro. La verifica visibile su `127.0.0.1:8080` non è stata eseguita in questo sotto-incarico e resta parte della campagna reale finale.
