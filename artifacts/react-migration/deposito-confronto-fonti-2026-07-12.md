# Deposito telematico: confronto funzionale e ministeriale del 12 luglio 2026

## Scopo e criterio di conformità

Questo rapporto conserva il lavoro svolto sul flusso `Prepara deposito` e deve essere richiamato nei controlli futuri. Il confronto usa due livelli distinti:

- il materiale decompilato del software di riferimento serve a ricostruire catalogo, rami operativi, nomi dei generatori, indicatori documentali e comportamento consolidato;
- le specifiche e gli XSD pubblicati dal Ministero della Giustizia determinano struttura, namespace, sequenza, cardinalità e validità del `DatiAtto.xml`.

In caso di contrasto prevale sempre la fonte ministeriale vigente. Il confronto con il software di riferimento non sostituisce gli XSD e non viene mai citato nella UI rivolta all'avvocato.

## Fonti effettivamente utilizzate

- Catalogo estratto dal decompilato: `pct/data/cataloghi/quickorganizer_depositi_studio_telematico.json`.
- Matrice leggibile del catalogo: `artifacts/react-migration/catalogo-quickorganizer-depositi.md`.
- Specifiche SICI attive pubblicate il 12 maggio 2026: `docs/specs/ministero/xsd/2026-05-12-sici/`.
- Schemi SIGP v3: `docs/specs/ministero/schema/sigp_v3/`.
- Schemi Corte di Cassazione v13: `docs/specs/ministero/parte/parte_v13/`.
- Pacchetto SICI dell'11 giugno 2026 trattato soltanto come anteprima e non come fonte attiva: `docs/specs/ministero/xsd/2026-06-11-sici-preview/`.
- Pagina PST di pubblicazione delle specifiche: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4871`.
- Campione storico di deposito reale accettato, conservato dall'utente: `C:/Users/antmm/Downloads/pec_00119fb0a3713fdb69faaf7d.eml`.
- Audit eseguibile: `scripts/audit_deposito_catalogo_end_to_end.py`.
- Esito macchina: `artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-12.json`.

## Copertura ottenuta

L'audit del 12 luglio 2026 termina con `ok=true` e i seguenti numeri:

- 270 tipi complessivi nel catalogo;
- 252 tipi PCT con generazione `DatiAtto.xml` eseguita;
- 252 tipi PCT attesi, quindi copertura generatore 252/252;
- 0 rami PCT sospesi;
- 18 rami UNEP separati dal deposito PCT;
- 67 rami contributo unificato/esenzione verificati;
- 122 prove negative sui campi obbligatori esposti in UI;
- 593 codici ufficio PCT operativi confrontati;
- 0 codici mancanti, 0 PEC mancanti, 0 difformità PEC e 0 errori del resolver React.

Per ogni tipo PCT lo script controlla mappatura catalogo, classe generatore, radice, dati richiesti, generazione XML, validazione XSD, contributo, ufficio, codice, PEC e stato di invio. L'audit fallisce se un campo obbligatorio non è esposto all'avvocato oppure se il generatore accetta la sua assenza.

## Generatori e campi specifici

Sono stati aggiunti descrittori UI e generatori per i rami che richiedono dati ulteriori, tra cui:

- citazioni, appelli, riassunzioni e opposizioni a decreto ingiuntivo;
- separazione, divorzio, successioni, minori e immigrazione;
- SIGP e opposizioni a sanzione;
- esecuzioni, credito, opposizioni, delegati, beni, titolo, custode e più terzi pignorati;
- procedure concorsuali;
- Corte di Cassazione, con provvedimento impugnato, materia, motivi e contromotivi.

Il generatore non inventa più dati anagrafici, catastali, indirizzi, custodi, diritti, tipi di separazione o altri valori mancanti. Prima della firma, ogni XML viene validato contro lo schema ministeriale attivo pertinente.

## Regole operative della UI

- Il tipo di deposito non viene scelto automaticamente nei casi nuovi.
- I documenti non vengono selezionati automaticamente nei casi nuovi.
- Le scelte già salvate restano invariate.
- Il software mostra candidati e controlli; l'avvocato sceglie tipo, documenti e ruoli.
- Solo tipo deposito, atto principale, ufficio/PEC/codice e dati indispensabili alla radice ministeriale bloccano la preparazione.
- Procura, allegati e altre voci non indispensabili allo schema restano avvisi quando la scelta dell'avvocato è già salvata.
- La prova senza invio e la simulazione restano disponibili per individuare subito i requisiti mancanti.
- Dopo una prova riuscita, e solo se firma, indice, pacchetto protetto, destinatario e controlli sono completi, `Invia deposito reale` si abilita.
- L'invio PEC legale parte sempre dal PC dell'avvocato tramite il servizio locale; il server non invia PEC operative.

## Caso reale `795C50AC`

Verifica visibile eseguita su `https://app.iusentra.it/fascicoli/795C50AC/deposito/prepara`:

- fascicolo `RG 1084/2026`, Tribunale di Vicenza;
- ufficio risolto automaticamente con PEC `tribunale.vicenza@civile.ptel.giustiziacert.it` e codice ministeriale disponibile;
- `Ricorso.pdf.p7m` salvato come unico documento in busta e ruolo `Atto principale`;
- gli altri documenti restano non selezionati finché l'avvocato non li include;
- la Procura è mostrata come avviso da verificare e non spegne i comandi di prova;
- il tipo oggi salvato è `Opposizione a decreto ingiuntivo (mediante ricorso)`.

Quest'ultimo dato deve essere confermato dall'avvocato. Se il deposito è davvero un'opposizione mediante ricorso, le fonti confrontate richiedono almeno numero, anno e data del decreto ingiuntivo; numero e anno della causa collegata restano facoltativi. Se non è un'opposizione, l'avvocato deve scegliere il tipo corretto e i campi non pertinenti scompaiono.

## Difetto trovato con click reale e correzione

Il primo click reale su `Prova senza invio reale` ha restituito `HTTP 500` perché il generatore rilevava il numero del decreto mancante dopo l'avvio della rotta. La causa non era un errore dell'avvocato, ma una gestione incompleta del requisito.

Correzione applicata:

- il frontend rileva prima numero, anno e data mancanti;
- il messaggio elenca i campi per nome;
- il pulsante `Completa dati deposito` apre direttamente il pannello corretto;
- confermando la prova, la finestra si chiude e il pannello dei campi si apre automaticamente;
- il backend intercetta comunque il dato mancante e restituisce JSON controllato con stato 400, mai una pagina 500;
- nessuna PEC viene inviata durante questa verifica.

## Prove eseguite

- `python scripts/audit_deposito_catalogo_end_to_end.py --output artifacts/react-migration/audit-deposito-catalogo-end-to-end-2026-07-12.json`;
- `python -m pytest -q tests/test_deposito_telematico_catalogo.py tests/test_busta.py tests/test_deposito_anagrafica_ministeriale.py tests/test_regia_ui_react.py tests/test_deposito.py::test_deposito_invia_pec_dato_ministeriale_mancante_restituisce_json_controllato` -> 64 test superati;
- `python -m pytest -q tests/test_react_shell.py` -> 152 test superati, inclusi caricamento paginato, attività udienza, ricevute EML, contributo unificato, navigazione e Local Signer;
- `python tools/codex_harness/run_codex_quality_gate.py --mode code` -> tutti i controlli superati;
- generazione e verifica dei contratti API/OpenAPI, smoke applicativo, baseline Python, `compileall`, Ruff, Flake8 e sincronizzazione pacchetto -> superati;
- `pnpm --filter @iusentra/studio typecheck`;
- `pnpm --filter @iusentra/studio build`;
- prova visibile in produzione con click su `Completa dati deposito`, cambio macroarea senza salvataggio, controllo del placeholder `Scegli il tipo di deposito`, ripristino tramite ricaricamento e doppio click reale su `Prova senza invio reale`;
- prova visibile locale sulla copia Docker reale `127.0.0.1:8080`, versione applicativa corrente `2.256.0`, fascicolo controllato `A1FB22FE`: fase Documenti con zero scelte automatiche, cambio macroarea senza selezione implicita del tipo, scelta temporanea dell'opposizione, comparsa dei cinque campi pertinenti e click su `Completa dati deposito`;
- click reale finale sulla fase `Busta e indice`: ufficio, PEC e codice risolti automaticamente; blocco nominativo su atto principale; elenco separato dei tre dati obbligatori del decreto; `Completa dati deposito` ha riaperto i cinque campi corretti; i tre comandi sono rimasti disabilitati perché il fascicolo locale non contiene documenti, senza simulare un esito positivo;
- scroll e controllo responsive locale a `1440x900`, `1024x768` e `390x844`, inclusi focus del primo campo, hover del salvataggio, correzione e riprova della sovrapposizione tra assistente e pulsante `Firma` su tablet e pulsanti di fase a tutta larghezza su mobile;
- ricaricamento finale del caso locale: tipo tornato su `Scegli il tipo di deposito`, `0 selezionati`, nessun dato di prova salvato e nessuna PEC inviata;
- verifica locale: un solo container `iusentra-app`, stato healthy e `/api/pronto` `2.256.0` sul sorgente finale senza bump dei file protetti.

Il gate di governo finale ha inizialmente fermato il rilascio perché la rotta deposito aveva superato il limite di 1.000 righe e due messaggi del generatore contenevano caratteri corrotti. La costruzione dei metadati busta e la risposta controllata ai dati mancanti sono state spostate nei servizi dedicati, i messaggi sono stati corretti in UTF-8 e i guardrail sono stati aggiornati per verificare la delega reale. Dopo la modifica: rotta a 1.000 righe, governance superata, 64 test deposito superati, 152 test shell React superati e audit 252/252 nuovamente superato.

## Limite residuo che impedisce una garanzia assoluta

La conformità strutturale dei generatori e dei campi è coperta dall'audit, ma non è professionalmente corretto garantire l'accettazione di ogni deposito futuro al 100% senza il caso concreto. L'accettazione dipende anche da correttezza della scelta dell'avvocato, contenuto degli atti, firma fisica valida, certificato dell'ufficio, cifratura, PEC locale, ricevute e controlli della cancelleria.

Sul caso `795C50AC` non è stato eseguito un nuovo invio PEC reale. La prova completa del pacchetto resta subordinata alla presenza del dispositivo di firma fisico e del Local Signer pronto. Nessun invio deve essere dichiarato accettabile finché la prova senza invio del caso concreto non termina e `Invia deposito reale` non si abilita con motivazione verificabile.

## Stato anti-regressione

Ogni modifica futura al deposito deve rilanciare l'audit 252/252, i test mirati, typecheck/build, prova visibile locale su `127.0.0.1:8080` e prova server. Un esito automatico verde non sostituisce i click reali. La selezione automatica di tipo o documenti, un errore HTTP generico, PEC server-side o campi inventati sono regressioni bloccanti.

Al 12/07/2026 restano da registrare sullo stesso SHA finale commit, push dei branch gemelli, tutti i check GitHub/CodeQL e il deploy Hetzner definitivo; tali passaggi non modificano l'esito della prova locale ma sono necessari per la chiusura del rilascio.
