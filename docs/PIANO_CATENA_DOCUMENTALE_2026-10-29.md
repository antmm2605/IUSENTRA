# Piano di miglioramento della catena documentale (29/10/2026)

Analisi dell'intera catena: acquisizione → OCR → catalogazione → identità del cliente → contributo unificato ed economia → notifiche → scadenze → agenda e calendari. Prima l'analisi, poi il piano, poi i test che dimostrano il miglioramento. **Nessuna modifica al codice è stata fatta: si implementa solo dopo il via dell'utente.**

Vincoli che il piano rispetta:

- Fonti certe: ogni comportamento nasce da una norma o da una specifica ministeriale.
- Il flusso deposito/firma/PEC è congelato dal 09/09/2026: `pct/busta.py`, la firma e l'invio PEC non si toccano senza un'istruzione esplicita dell'utente. I punti del piano che lo sfiorano sono segnati con ❄.
- Nessuna dipendenza ML/GPU nel gestionale (AGENTS.md, «Autoresearch-lite»): l'addestramento avviene fuori dal prodotto, che riceve solo il risultato da misurare.
- I documenti dello studio non escono dal server se non per scelta esplicita dell'avvocato.

---

## 1. Come funziona oggi: la catena reale

```
INGRESSO (upload, portale, PEC, editor)
  ├─ coda OCR (pct/ocr_worker.py) ─────────────► testo in ocr_cache (IndiceRicerca)
  ├─ indicizzazione DocumentAI ────────────────► SECONDA estrazione → testo SQL
  └─ legal_document_ingestion (API forense) ───► TERZA estrazione, ramo isolato
        │
        ▼ evento nel registro letture (pct/registro_letture)
CICLO DI LETTURA (archivio_letture_runtime.leggi_fascicolo, ogni minuto)
  motore documenti ─┐  (classificatore proprio: natura_documentale)
  motore PEC ───────┼─► fatti con collaudo ─► presìdi (scadenziario, agenda, parti, giudice)
                    │
  catalogo a REGOLE (144 regole di titolo + resolver) ─► obblighi di notifica, identità cliente
        │
        ▼ (asincrono, 2 documenti ogni 2 minuti)
SECONDA LETTURA Spark-X2.5 4B (catalog_lex.py) → solo proposte incerte (<90)
        └─► FINE: nessun evento a valle
```

In parallelo scrivono su scadenziario e agenda altri cinque percorsi: pipeline PEC, presidio documentale PEC, obblighi di notifica, presidio notifiche PEC, Polisweb. A questi si aggiunge la sincronizzazione dei calendari esterni. Ognuno usa un proprio marcatore e nessuno vede quelli degli altri.

## 2. Che cosa non va: diagnosi per area

### 2.1 Difetti giuridici (verificati sul codice)

| # | Difetto | Dove | Effetto |
|---|---|---|---|
| G1 | Le memorie 171-ter n. 1/2/3 sono calcolate **dopo** l'udienza (+40/+20/+10 giorni) invece che **prima** | `pct/scadenziario.py:549-551`. `calcola_termine` e `ProfiloTermine` non hanno il verso a ritroso | Termine perentorio sbagliato e memoria tardiva |
| G2 | Una relata letta non chiude mai l'obbligo di notifica | `pct/obblighi_notifica.py:311` richiede `atto_documento_id/verificata/destinatari_completi`, mentre `obblighi_notifica_runtime.py:87` produce `documento_id/data/atto` | Scadenze di notifica sempre aperte, falsi allarmi |
| G3 | Il motore PEC dell'archivio legge giorno e ora in UTC | `pct/archivio_letture/motore_pec.py:245,261` | Una PEC delle 00:30 italiane risulta del giorno prima: decorrenze spostate |
| G4 | «Oggi» calcolato con `date.today()` (ora del server) in una decina di punti | `consegna_presidi_runtime`, `obblighi_notifica*`, `presidi.py`, `scadenziario.py`, `polisweb_fascicolo_sync` | Viola la regola Europe/Rome fra mezzanotte e le 2 |
| G5 | Il calcolatore dello scadenziario non aggiunge il giorno «libero» né agosto nei termini a mesi; esistono due motori divergenti (`scadenziario` e `termini_processuali`) | `pct/scadenziario.py:207` | Termini diversi a seconda del percorso |
| G6 | Appello breve (art. 325, 30 giorni dalla notifica) assente negli obblighi; proposta di opposizione 127-ter senza presidio | `obblighi_notifica.py:148` | Termini non presidiati |
| G7 | Calendario Microsoft: orario italiano inviato come UTC; in lettura UTC trattato come ora italiana | `calendar_providers/microsoft.py:114` | Udienze spostate di 1-2 ore |

### 2.2 Catalogazione e classificatore

- **Sei classificatori** con tassonomie diverse:
  - il catalogo SQL;
  - il classificatore storico `fascicolo_document_catalog`;
  - `pertinenza_documentale` dell'archivio;
  - `legal_document_ingestion`;
  - `pec_pipeline.classify_attachment`;
  - `pec_legal_workflow`.
- **Le etichette certe non vengono usate quando c'è il testo.** Il tipo atto del portale PST (`tipo_atto_portale`, `classificazione_portale`), il tipo atto di DatiAtto della busta, l'oggetto di `Comunicazione.xml`, le RT pagoPA, le fatture SdI e i `.p7m` vengono letti, ma il catalogo li consulta solo quando il testo manca.
- **Le decisioni dell'avvocato si perdono in parte:**
  - la correzione riscrive la riga;
  - l'audit registra solo i nomi dei campi, senza il valore prima e dopo;
  - un nuovo giro del resolver cancella `lex_lettura`;
  - la conferma massiva attesta prove mai lette, quindi non è un'etichetta affidabile.
- **Nessun banco di prova versionato del catalogo.** Il confronto Spark/qwen è stato fatto su 19 documenti fuori dal repository e mancano metriche per voce e matrice di confusione.
- **Spark:** circa 117 secondi a documento, 2 documenti ogni 2 minuti. Sceglie fra circa 160 voci in un elenco piatto e legge solo i primi 4000 caratteri. Il suo esito non propaga: gli obblighi di notifica restano calcolati sull'etichetta vecchia.
- **Voci mancanti nel catalogo:** ricevuta del contributo unificato, dichiarazione di esenzione, dichiarazione di valore (art. 14), autocertificazione reddituale, tessera sanitaria/tesserino del codice fiscale.

### 2.3 OCR e orchestrazione

- Lo stesso file subisce l'OCR fino a 3 volte, senza testo condiviso.
- Un caricamento produce almeno 2 giri completi di lettura del fascicolo.
- Il testo nativo viene ricalcolato (decifratura + pdfplumber + fitz) a ogni rilettura.
- Ollama non ha regia: embedding RAG, Spark e manutenzione girano in concorrenza senza semaforo. Se il RAG supera i 60 secondi fa fallire l'intero evento dopo 3 tentativi, anche quando fatti e presìdi erano già consegnati.
- I presìdi notifiche ed economico rileggono i documenti ogni 15 minuti invece di consultare l'archivio, come prevede la regola del progetto.
- Il collaudo OCR notturno è solo informativo.

### 2.4 Documenti d'identità e anagrafica

- La pipeline principale (`document_intelligence/service.py:379`) non passa il cliente. I nuovi documenti d'identità restano senza collegamento alla cartella cliente.
- L'abbinamento al cliente avviene solo per nome. Codice fiscale e data di nascita sono controllati solo da uno script straordinario: viola la direttiva «identità congiunta».
- La scadenza:
  - segnala solo «scaduto», senza preavviso;
  - non crea voci nello scadenziario;
  - è salvata due volte (scheda cliente e scheda antiriciclaggio) senza allineamento;
  - con una data malformata solleva `ValueError`.
- Il documento caricato in compilazione anagrafica viene letto e poi scartato. Il portale cliente non passa dal lettore.
- Privacy:
  - documenti d'identità marcati come candidati al deposito (possono finire nella busta);
  - nessun audit della lettura dei dati identificativi;
  - nessuna regola di conservazione.
- Controllo degli atti limitato a nome e codice fiscale della parte assistita; data e luogo di nascita e residenza non vengono confrontati.

### 2.5 Contributo unificato ed economia del fascicolo

- **Stato del CU in quattro posti, scritto da sei percorsi:** `fascicolo.pagamenti`, fatti dell'archivio, eventi SQL della sentenza, memoria React. Il fascicolo può dire «pagato verificato» mentre il deposito dice «da definire».
- **Quattro calcoli del dovuto non coincidenti.** Il dovuto non viene mai salvato né confrontato con il pagato (la busta confronta il pagato col pagato ❄).
- **La stessa RT è letta in due modi:** totale contro quota CU. I 27 € dell'art. 30 producono un falso «importo difforme».
- **Riconoscimenti fragili:**
  - esenzione dal solo nome del file (`fascicolo_esenzione_cu.py`);
  - esenzione dalla sola stringa «dpr 115» (`deposito_semantic_helpers.py`);
  - il promemoria pagoPA vale come pagamento, contro la policy PST.
- **Casi mancanti:**
  - esenzioni per materia (art. 10 D.P.R. 115/2002);
  - prenotazione a debito per il patrocinio a spese dello Stato (art. 131);
  - lettura della dichiarazione di valore (art. 14);
  - versamento forfettario (art. 30) come voce distinta;
  - pagamento frazionato;
  - richiamo all'art. 16 per il CU insufficiente.
- **La sentenza è letta da due motori.** La proforma usa il CU letto nella sentenza invece di quello pagato.
- **Preventivi e parcelle non vedono CU, esborsi e liquidazione** (`economico_context.py`).

### 2.6 Agenda, scadenziario e doppioni

Restano possibili doppioni in almeno 8 casi:

- la stessa udienza da due PEC diverse;
- PEC + lettura dei documenti;
- agenda manuale + archivio;
- obbligo di notifica da documento + presidio notifiche PEC;
- Polisweb;
- calendari esterni;
- identificativo canonico che cambia;
- titolo libero.

Regole sull'ora incoerenti: la consegna rifiuta l'udienza senza ora, la pipeline PEC mette le 09:00. Costi O(N·M) nelle scansioni delle scadenze e mirror JSON rigenerato a ogni rettifica.

---

## 3. Il piano

Le fasi sono in ordine di dipendenza. Ogni fase si chiude con i suoi test (sezione 4) e con il gate locale `scripts/ci_local_gate.sh`.

### Fase 0: correzioni giuridiche urgenti (G1-G7)

Si fanno per prime perché sono errori che oggi producono termini sbagliati, indipendentemente da qualsiasi modello.

1. **G1.** Verso a ritroso in `ProfiloTermine` (`direzione: avanti|ritroso`) e nei preset 171-ter e 183. Il calcolo passa a `termini_processuali` (che lo conosce già), con l'art. 155 applicato a ritroso: se l'ultimo giorno è festivo si anticipa. Le scadenze 171-ter già salvate si riconvalidano: si ricalcolano e si mostra la differenza, senza toccare le date modificate a mano.
2. **G2.** `raccogli` produce prove con `atto_documento_id`, ricavato dal collegamento relata → atto notificato. `verificata` arriva dal collaudo del fatto; `destinatari_completi` arriva dalla matrice RAC/RdAC per destinatario (`notification_proof_matrix.py`).
3. **G3/G4.** Conversione in Europe/Rome nel motore PEC e `oggi_roma()` condiviso al posto di `date.today()`. Regressione con datetime aware e naive mescolati, come prescrive CLAUDE.md.
4. **G5.** Un solo motore dei termini (`termini_processuali`); `scadenziario.calcola_termine` diventa un adattatore.
5. **G6.** Art. 325 negli obblighi, che parte dalla notifica della sentenza letta. Presidio per la proposta di opposizione 127-ter.
6. **G7.** Fuso orario corretto nei provider Microsoft e Google.

### Fase 1: verità certificate e banco di prova (prerequisito di qualsiasi addestramento)

Senza questa fase non si può dire se un modello addestrato migliora qualcosa.

1. **Registro delle etichette certe** (`pct/document_intelligence/verita/`). Per ogni documento si registrano l'etichetta, la fonte, la forza della prova e la data.
   - **Livello A, certificate:**
     - tipo atto dal portale PST;
     - DatiAtto della busta depositata;
     - oggetto e tipo di `Comunicazione.xml` da `giustiziacert`;
     - esiti e ricevute PCT;
     - RT pagoPA con causale;
     - FatturaPA e notifiche SdI con provenienza verificata;
     - `.p7m` con firma verificata.
   - **Livello B, decisioni dell'avvocato:** correzione manuale e conferma singola con prova letta.
   - **Esclusi:** la conferma massiva, che non è un'etichetta.
2. **Storia delle decisioni.** L'audit di correzione registra il valore prima e dopo. Un nuovo giro del resolver conserva `lex_lettura` e i candidati precedenti. Così per ogni documento resta la tripla regola / Spark / avvocato.
3. **Una tassonomia sola.** Le voci strutturali e delle ricevute entrano nel catalogo di Spark. Le nature della correzione manuale si allineano alle circa 40 del resolver. `Documento.tipo` si deriva dal catalogo. Si aggiungono le voci mancanti: ricevuta CU, esenzione CU, dichiarazione di valore, autocertificazione reddituale, tessera sanitaria.
4. **Banco di prova versionato** (`pct/collaudo_ai/catalogo/` + `scripts/collaudo_catalogo.py`):
   - gira **sul server**, sui dati reali, e produce solo metriche anonime (nessun testo esce);
   - misura accuratezza per voce e per sezione, matrice di confusione, tasso di proposte sbagliate applicate, copertura e tempo per documento;
   - confronta regole, regole + Spark, e i candidati addestrati;
   - una parte di prova congelata (20%, scelta per fascicolo, mai usata per addestrare) evita di misurare su ciò che il modello ha già visto.

### Fase 2: classificatore addestrato

Due strade, misurate entrambe sul banco della Fase 1. Si adotta solo quella che riduce gli errori, e solo sulle voci dove li riduce.

**Strada A (raccomandata): classificatore leggero sopra `embeddinggemma`**
- Vettori del documento (titolo, prime righe, prima pagina) calcolati con `embeddinggemma:300m`, già presente su Ollama.
- Modello lineare (regressione logistica multiclasse), addestrato in due livelli: prima la sezione, poi la voce dentro la sezione.
- L'addestramento è uno script fuori dal gestionale (`tools/addestramento_catalogo/`), eseguibile sul tuo PC o sul server. Il prodotto riceve un file di pesi JSON versionato con impronta, e l'inferenza usa solo `numpy`, già fra le dipendenze.
- Tempo atteso: millisecondi a documento invece di circa 117 secondi. Funziona anche senza GPU.

**Strada B: riaddestramento LoRA di Spark-X2.5 4B sul tuo PC**
- Si usa LLaMA-Factory, già previsto da `lex/dataset/llama_factory.py`, oppure Unsloth, **fuori dal gestionale**. Si esporta in GGUF Q4_K_M e si carica su Ollama come `spark-catalogo-iusentra:<versione>`.
- Richiede una GPU NVIDIA con almeno 12-16 GB di VRAM (QLoRA). Con meno memoria l'addestramento è impraticabile.
- Mantiene la citazione verificata, ma resta lento: circa un minuto a documento sul server a 2-4 core.

**Regole di adozione (per voce, non globali)**
1. Prima si fa girare in ombra per almeno 2 settimane: il modello propone, si registra, non cambia nulla.
2. Si adotta su una voce solo se sulla parte di prova ha **meno errori delle regole**, almeno 30 esempi e **nessun errore** sui documenti con etichetta certificata (livello A).
3. L'etichetta certificata prevale sempre su regole e modelli. Il modello interviene dove oggi interviene Spark (regole incerte) e come terzo parere quando regole e Spark discordano.
4. Spark resta come lettore con citazione per i casi che il classificatore leggero dichiara incerti.
5. Riaddestramento periodico solo sulle nuove decisioni di livello A e B, con confronto automatico col modello in uso. Se peggiora non si adotta.

### Fase 3: un solo flusso, sincronizzato

1. **Un testo per documento.** Il worker OCR scrive direttamente il testo SQL di DocumentAI; l'indicizzazione e `legal_document_ingestion` lo riusano (impronta SHA-256). Un caricamento produce un solo giro di lettura.
2. **Catalogo prima dei presìdi.** Ordine fisso: catalogo → motori → presìdi. Il motore documenti usa la natura del catalogo e non una propria (si eliminano i classificatori 2-5 della sezione 2.2, che diventano adattatori).
3. **Propagazione.** Un esito di Spark o del classificatore e ogni conferma o correzione dell'avvocato generano un evento: si ricalcolano obblighi di notifica, identità del cliente ed economia, e si invalida la cache di lettura.
4. **Regia di Ollama.** Semaforo condiviso fra embedding, catalogo e manutenzione, con priorità: catalogo prima del RAG. Un RAG oltre budget rimanda solo il RAG, non fa fallire l'evento.
5. **Presìdi notifiche ed economico solo in consultazione dell'archivio:** niente scansioni proprie ogni 15 minuti.
6. **Un identificativo di tenant solo** (`tenant_corrente`) per catalogo, RAG e registro.

### Fase 4: documenti d'identità e anagrafica

1. La pipeline principale riceve cliente e parti del fascicolo. L'abbinamento richiede l'**identità congiunta**:
   - codice fiscale valido e concordante (letto dalla MRZ, dal codice a barre della CIE o dal testo);
   - nome e cognome;
   - data di nascita.
   Un dato discordante lascia la verifica aperta con il motivo.
2. Collegamento automatico nella cartella cliente (nessuna copia del file: metadato SQL, come oggi), con aggiornamento in tempo reale.
3. **Scadenza:**
   - una sola data, quella della scheda cliente, letta anche dall'antiriciclaggio;
   - aggiornamento automatico quando il documento letto è più recente;
   - preavviso a 60 e 30 giorni nello scadenziario e nella top bar;
   - nessuna eccezione su date malformate.
   - Base normativa: D.Lgs. 231/2007, artt. 18-19 (adeguata verifica con documento valido).
4. **Compilazione anagrafica:**
   - il documento caricato viene **conservato** nella cartella cliente;
   - anche il portale cliente passa dal lettore;
   - l'unico parser MRZ è quello Python con le cifre di controllo (si elimina quello TypeScript).
5. **Privacy:**
   - documento d'identità **non** candidato al deposito, salvo scelta dell'avvocato;
   - audit di ogni lettura;
   - permesso `clienti.scrivi`;
   - conservazione dichiarata in `pct/privacy.py`.
6. **Controllo degli atti:** data e luogo di nascita, residenza e codice fiscale delle parti negli atti confrontati con la scheda e con il documento d'identità, anche per le controparti. Le discordanze vanno nel pannello «Letture e verifiche».

### Fase 5: contributo unificato ed economia del fascicolo

1. **Fonte unica: «Registro del contributo»** del fascicolo (SQL, tenant-aware) con:
   - `dovuto`: calcolo da valore, categoria e grado, solo con `strumenti_legali`;
   - `pagato`: solo quote CU delle RT, F23 o F24 Elide;
   - `forfettario_art30`, `marca_bollo`;
   - `esenzione`: art. 10 per materia, art. 9 c. 1-bis reddituale, attestazione;
   - `prenotazione_a_debito` (art. 131);
   - `differenza` (art. 16);
   - prove con documento e passaggio.
   I quattro posti attuali diventano proiezioni lette da questo registro.
2. **Riconoscimento:**
   - ricevuta CU, autocertificazione e dichiarazione di esenzione come voci del catalogo, che addestra la Fase 2;
   - lettura della dichiarazione di valore dall'atto introduttivo;
   - eliminazione dell'esenzione «da nome file» e dell'euristica «dpr 115»;
   - il promemoria pagoPA non vale come pagamento;
   - OCR: il fatto resta plausibile e chiede conferma solo se cambia lo stato del deposito.
3. **Identità della ricevuta:** la RT pagata prima dell'iscrizione a ruolo si abbina tramite IUV, causale e codice fiscale del ricorrente, senza attendere l'RG.
4. **Vista economica sincronizzata:**
   - contributo, spese ed esborsi, liquidazione e parcella in un unico contesto, letto da preventivi, parcelle, proforma e cruscotto;
   - la proforma usa il CU pagato;
   - un solo motore per la sentenza (i fatti dell'archivio);
   - `react_fascicoli_bridge.py` cede la parte economica a un bridge dedicato `react_fascicolo_economia_bridge.py`.
5. ❄ Il confronto della busta (`pct/busta.py`, `pagamenti_giustizia.verifica_rt_per_deposito`) userebbe la sola quota CU e il dovuto. **Richiede la tua autorizzazione esplicita** perché tocca il flusso congelato. In alternativa il controllo si fa a monte nel presidio, senza toccare la busta.

### Fase 6: notifiche, scadenze e agenda senza doppioni

1. **Registro unico degli eventi.**
   - Ogni udienza, termine o obbligo ha un'identità giuridica (fascicolo + tipo + data e ora + istituto) e un elenco di fonti (PEC, documento, portale, manuale, calendario).
   - I sei scrittori passano tutti da qui. Una fonte nuova aggiunge una prova all'evento esistente, invece di creare una voce.
   - Si estende `EventiUniciRepository`, che oggi interviene solo dopo la riunione manuale.
2. **Presidio notifiche «chi, cosa, entro quando»:**
   - per ogni obbligo: destinatario (con PEC da ReGIndE o INI-PEC), atto, termine, norma e stato della prova per destinatario;
   - si chiude da solo con RAC e RdAC complete;
   - fascia oraria 21-7 (art. 147 c.p.c. e Corte Cost. 75/2019) applicata alle date delle ricevute.
3. **Scadenze derivate dall'udienza:**
   - un'udienza di prima comparizione verificata propone le tre memorie 171-ter e la costituzione (art. 166), calcolate a ritroso;
   - un rinvio sposta i termini collegati;
   - si chiede conferma solo per i termini futuri (`da_confermare_ora`).
4. **Calendari esterni:** confronto di contenuto (data, ora e RG nel titolo) prima di creare un elemento locale.
5. **Prestazioni:**
   - indici per fascicolo e data al posto delle scansioni O(N·M);
   - mirror JSON aggiornato una volta per giro;
   - le udienze senza ora non si ritentano a ogni ciclo, ma restano «ora da confermare» con una sola richiesta.

### Fase 7: intuitività per l'avvocato

- Un pannello «Da decidere» per fascicolo, con le sole decisioni che cambiano agenda, scadenziario, deposito o economia. Ogni voce mostra la prova (passaggio del documento), la norma e un'azione (Conferma / Correggi).
- Le conferme e correzioni alimentano il registro delle etichette della Fase 1: ogni decisione migliora il modello successivo.
- Testi in italiano, date `gg/mm/aaaa`, nessuna sigla tecnica (UTC, RAG, LoRA) visibile.

---

## 4. Test che dimostrano il miglioramento

Ogni test misura un difetto reale e ha un criterio keep/discard. I test sintetici stanno nel repository; le misure sui dati reali girano sul server e producono solo numeri.

| Area | Test | Misura | Criterio di accettazione |
|---|---|---|---|
| G1 | `test_termini_171ter_ritroso.py`: udienza nota, attese calcolate a mano anche a cavallo di agosto, Natale e domeniche | data della memoria | 100% uguali alla norma; regressione sul bug attuale (oggi fallisce) |
| G2 | relata verificata + RdAC complete → obbligo `notificato`; RdAC mancante per un destinatario → resta aperto | stato dell'obbligo | oggi 0% chiusi → 100% chiusi solo con prova completa |
| G3/G4 | PEC 23:30 UTC = 00:30 Roma; job alle 00:30 Roma | giorno della decorrenza | giorno italiano corretto, casi naive e aware |
| Catalogo | banco versionato (Fase 1) su dati reali | accuratezza per voce, proposte sbagliate applicate, secondi a documento | adozione per voce solo con meno errori delle regole, ≥30 esempi, 0 errori sul livello A |
| Classificatore | stesso banco: regole vs regole+Spark vs Strada A vs Strada B | idem | si adotta la strada con meno errori; a parità, la più veloce |
| Propagazione | correzione dell'avvocato → obblighi e identità ricalcolati entro il giro successivo | latenza e coerenza | 0 obblighi calcolati su etichette superate |
| OCR | un caricamento → numero di estrazioni e di giri di lettura | contatori | da 2-3 estrazioni a 1; da ≥2 giri a 1 |
| Identità | casi di omonimia (stesso nome, CF diverso), CF assente, documento scaduto o in scadenza | abbinamenti sbagliati, preavvisi | 0 abbinamenti con CF discordante; preavviso a 60 e 30 giorni |
| CU | RT con quota CU + art. 30; esenzione per materia; patrocinio; promemoria pagoPA; dichiarazione di valore | stato e importo del registro | 0 falsi «difforme»; stato uguale in fascicolo, deposito e proforma |
| Doppioni | stessa udienza da PEC + documento + Polisweb + calendario Google | voci in agenda | sempre 1 voce con 4 fonti |
| Velocità | tempo del giro di lettura e della Panoramica su un fascicolo di 200 documenti, prima e dopo | secondi | nessun peggioramento; obiettivo −50% sul giro di lettura |

---

## 5. Decisioni che spettano all'avvocato prima del via

1. **Hardware per l'addestramento.** Che GPU ha il PC dove vuoi addestrare (modello e GB di VRAM)? Senza una GPU NVIDIA da almeno 12 GB la Strada B non è praticabile; la Strada A funziona comunque.
2. **Dove stanno i dati di addestramento.** Le etichette e i testi vengono dai documenti reali dello studio. Possono restare sul server (si addestra lì la Strada A) oppure essere esportati sul tuo PC per la Strada B. L'esportazione sarebbe pseudonimizzata, con codici fiscali, nomi e indirizzi sostituiti.
3. **Flusso congelato ❄.** Autorizzi la modifica del confronto CU nella busta (Fase 5.5), oppure il controllo resta solo nel presidio?
4. **Ordine.** Proposta: Fase 0 subito (errori giuridici), poi 1 → 2 → 3 in parallelo con 4-6.
