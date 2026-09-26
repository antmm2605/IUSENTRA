# Rassegne del 25 e 26 settembre 2026: che cosa cambia in IUSENTRA

Questo documento riassume cinque spunti delle rassegne e dice per ciascuno che cosa entra nella logica di IUSENTRA. Distingue ciò che la 2.408.0 già fa da ciò che resta da fare.

Il principio resta quello delle fonti certe: il modello propone, le regole decidono. Nessun valore letto da un modello diventa un'azione se non si ritrova nel testo della fonte o in un registro ufficiale.

## 1. Lasso, «The Provenance Tax»

**Che cosa dice.** Un marcatore di provenienza inserito nel contesto di un agente ne cambia il comportamento: nel 6,5% dei casi cambiano le chiamate agli strumenti. Anche un'informazione di servizio, se entra nel prompt, orienta le scelte del modello.

**Che cosa ne ricaviamo.** La provenienza si registra *fuori* dal prompt:

- nei metadati della lettura (catalogo);
- nell'audit (editor);

mai come testo che il modello legge. In IUSENTRA il modello non chiama strumenti con effetti: le azioni restano alle regole deterministiche. Il rischio segnalato riguarda soprattutto la stabilità delle proposte.

**Esperimento previsto.** Si ripete la prova su 30 PEC ostili, anonimizzate, con due configurazioni di Lex:

- senza marcatore;
- con un marcatore di provenienza nel contesto.

Si confrontano quattro misure:

- evento riconosciuto;
- campi proposti;
- valori bloccati dal cancello;
- tempo.

Una differenza oltre il 5% sui campi proposti rende obbligatorio tenere i marcatori fuori dal prompt, come già si fa.

## 2. Registro di provenienza dell'AI (ICC, Appleton)

**Che cosa dice.** Chi usa l'AI in ambito legale deve poter dire, per ogni uscita, quale modello l'ha prodotta, su quale input, con quale verifica e chi l'ha approvata.

**Implementato in 2.408.0.** Il modulo è `pct/provenienza_ai.py`.

- Il record `Provenienza` contiene:
  - l'azione;
  - il modello;
  - la versione delle regole;
  - l'impronta SHA-256 dell'input;
  - la citazione;
  - i parametri;
  - l'esito del cancello;
  - l'approvazione;
  - la data;
  - il sigillo del record precedente.
- Il sigillo SHA-256 rende riconoscibile ogni modifica successiva. Si controlla con `verifica_sigillo`.
- La seconda lettura del catalogo (`catalog_lex.applica_esito`) salva la provenienza in `metadata.lex_lettura.provenienza`. I controlli sono due: la voce appartiene al catalogo chiuso e la citazione si ritrova nel documento.
- La bozza dell'editor AI registra nell'evento `editor_ai.generation.completed` tre dati: il modello (`provider:model` del gateway Lex), l'impronta della richiesta e l'impronta della bozza.

**Resta da fare.** Una vista «Provenienza» nel fascicolo, che elenca le uscite AI con modello, esito del cancello e approvazione, e il loro invio nell'hash-chain di `audit/`. Serve un nuovo `AuditKind`.

## 3. TX Text Control: AI probabilistica, modifiche deterministiche

**Che cosa dice.** Il modello suggerisce, ma la modifica del documento la esegue un motore deterministico, verificabile e ripetibile.

**Che cosa c'è già e che cosa aggiunge la 2.408.0.**

- L'editor lavora sempre su una **copia** quando il documento fa prova: PDF da portali e PEC, firmati, buste .p7m, email (`web/services/pdf_modificabile.py`). L'originale resta intatto, con firma e impronta (artt. 20 e 22 CAD).
- Le proposte dell'editor AI si accettano o si rifiutano una per una (`accept_edit` / `reject_edit`).
- Il **cancello di ancoraggio** (`cancello_ancoraggio`) blocca ogni data, numero, nome o codice proposto dal modello che non si ritrova nel testo o in un registro. Il controllo è deterministico e non chiede nulla al modello.

## 4. Sondaggio AAA / Jus Mundi: il 78% teme le allucinazioni

**Che cosa ne ricaviamo.** La fiducia nasce dalle prove, non dalle rassicurazioni. Ogni dato che IUSENTRA propone porta la sua prova:

- la frase del documento;
- il codice fiscale con il carattere di controllo;
- la norma che fonda l'obbligo.

Quando la prova manca, il dato resta «da verificare» con il motivo. Le nuove funzioni della 2.408.0 seguono questa regola:

- **parti lette dagli atti**: la citazione dell'epigrafe e il difensore; una parte entra in anagrafica da sola solo con il lato certo e il codice fiscale valido;
- **obblighi di notifica**: la norma, la data da cui decorre il termine e la regola dei termini liberi. Senza data letta non si calcola nulla.

## 5. Reducto, «From Ingestion to Agents»: OCR agentico e valutazione per stadi

**Che cosa dice.**

- La qualità si misura stadio per stadio: lettura, estrazione, ricerca, azione. Un errore di lettura non deve comparire come errore dell'agente.
- Le tabelle vanno rappresentate in due modi, come testo e come struttura.
- Un valore numerico che non si riconduce alla pagina va bloccato.

**Come si applica.**

| Stadio | In IUSENTRA | Misura |
|---|---|---|
| Lettura | motore OCR unico (`legal_ocr/motore`), testo nativo, indice | corpus di collaudo (`legal_ocr/collaudo/corpus.py`), consenso fra le letture |
| Estrazione | motori dell'archivio delle letture: date, ruoli, importi, prove di notifica, **parti** | collaudo automatico dei fatti; test con testi sintetici per ogni regola |
| Ricerca | catalogo documentale, RAG del fascicolo | campione di documenti con la voce nota (vedi `docs/LEX_CONFRONTO_MODELLI_2026-09-26.md`) |
| Azione | presìdi che scrivono: scadenziario, agenda, **parti**, **obblighi di notifica** | consegne registrate con riferimento; **cancello di ancoraggio** |

**Esperimento previsto.** Su 30 pagine italiane anonimizzate si misura il cancello di ancoraggio: quanti valori numerici proposti dal modello blocca, e quanti ne blocca a torto. Obiettivo: nessun valore inventato che passa e meno del 2% di blocchi a torto.

Le tabelle restano un punto aperto. Il testo delle tabelle PDF oggi è lineare: la rappresentazione doppia serve soprattutto al presidio economico (prospetti di liquidazione) e sarà il prossimo passo sul motore OCR.

## Che cosa la 2.408.0 porta nella logica del fascicolo

**Catalogazione reale.**

- Nuove regole per:
  - le pronunce («ha pronunciato la presente sentenza/ordinanza»);
  - le procure;
  - le note di deposito con foliario;
  - il ricorso per l'ottemperanza;
  - l'atto di citazione.
- Il profilo del catalogo segue il tipo del fascicolo: amministrativo, tributario, penale, lavoro, famiglia, stragiudiziale, civile. I documenti amministrativi non restano più tutti a 55 e «da verificare».

**Lettura reale del fascicolo.**

- Il motore documenti v15 legge le parti dell'epigrafe e il numero di ricorso amministrativo (REG.RIC.).
- I documenti già letti si rileggono una volta.

**Parti, cliente e testimoni.**

- Il lato dello studio si riconosce dal difensore dello studio o dal nome del cliente.
- Le controparti si leggono con i loro difensori, compresa l'Avvocatura dello Stato.
- Testimoni e CTU restano proposte.
- Il presidio «Parti del fascicolo» scrive in anagrafica senza doppioni (stesso codice fiscale o stesso nome) e non duplica il cliente.
- Nel riquadro «Letture e verifiche», le parti non certe si aggiungono con un clic.

**Presidio notifiche che legge i documenti** (`pct/obblighi_notifica.py`). Dal documento catalogato nasce l'obbligo di notificare, con i destinatari e il termine. Gli obblighi coperti:

- art. 415 c.p.c. (lavoro);
- art. 644 c.p.c. (decreto ingiuntivo);
- art. 163-bis c.p.c. (citazione);
- artt. 641 e 645 c.p.c. (opposizione a decreto ingiuntivo);
- art. 660 c.p.c. (sfratto);
- artt. 479-482 c.p.c. (precetto);
- artt. 41 e 45 c.p.a. (ricorso al TAR);
- art. 114 c.p.a. (ottemperanza);
- artt. 325-330 c.p.c. (appello civile);
- art. 92 c.p.a. (appello al Consiglio di Stato);
- notifica della sentenza, facoltativa.

Le amministrazioni dello Stato si notificano presso l'Avvocatura distrettuale (art. 11 R.D. 1611/1933). Gli obblighi con una scadenza futura entrano nello scadenziario una volta sola, da confermare.

**Stato reale del fascicolo** (`pct/stato_fascicolo.py`).

- Il fascicolo passa da aperto a in corso con il numero di ruolo o con il deposito accettato.
- Il registro di cancelleria fa fede anche per «sospeso».
- La sentenza porta a «definito».
- Ogni cambio registra la prova nell'avanzamento.
- L'archiviazione resta un atto dello studio, perché crea l'archivio ZIP.
