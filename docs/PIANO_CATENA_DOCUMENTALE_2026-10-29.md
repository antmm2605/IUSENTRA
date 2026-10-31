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

---

## 6. Modelli e addestramento: risposte dell'avvocato e piano (29/10/2026)

Decisioni ricevute: GPU **RTX 3060 12 GB**, addestramento **sul PC dell'avvocato**. Il modello grande da 35B (MoE, `llama.cpp` sul PC, ponte Tailscale `deploy/private-lex/`) resta sul PC; il suo addestramento può avvenire su GPU noleggiata a ore. Il file `Revisione_avvocato_Lex.docx` (SHA-256 `786b85011af3a8bc98a0950835f1a68f6cf5aee30a2068df878190870509f654`) è dichiarato dall'avvocato **approvato in tutte le scelte**. Contiene:

- Parte A, 10 schede del banco v7: V7A_01, V7A_04, V7A_17, V7A_19, V7B_04, V7B_14, V7B_16, V7C_09, V7C_10, V7C_12;
- Parte B, 12 casi del materiale D4, uno per materia: da D4_1_01 a D4_1_12, dal civile ordinario al penale.

Nota di audit: nel file le caselle dell'esito sono vuote. L'approvazione va quindi registrata come dichiarazione dell'avvocato legata all'impronta del file. Per la regola già in vigore (`lex/procedura_atti/impronte.py`), l'approvazione vale solo per quel testo esatto e decade se scheda o norme cambiano.

### 6.1 Esistono modelli già addestrati sul diritto italiano?

Ricerca del 29/10/2026:

- **Modelli generativi:** nessun modello aperto addestrato sul diritto italiano risulta pubblicato e mantenuto. Esistono solo lavori metodologici: Llama-3.1-8B adattato su Normattiva, senza pesi rilasciati. Nelle valutazioni 2026 su compiti giuridici multilingue l'italiano è la lingua in cui i modelli aperti rendono peggio. La base migliore resta un modello generale forte (la famiglia Qwen3.5 già in uso) con fonti e schede, completato dal nostro addestramento.
- **Classificatori:** esiste **Italian-Legal-BERT** (`dlicari/Italian-Legal-BERT`, Apache 2.0, 110 milioni di parametri). È un BERT italiano preaddestrato su 3,7 GB di sentenze dell'Archivio giurisprudenziale nazionale. Non è un classificatore pronto, ma una base da specializzare sulle nostre voci; si addestra in pochi minuti sulla RTX 3060.
- **Modelli italiani generali** (Minerva 7B della Sapienza, LLaMAntino): nessuna specializzazione giuridica e prestazioni inferiori a Qwen3.5 di pari taglia. Non conviene partire da loro.

### 6.2 Quale modello per quale compito

| Compito | Dove gira | Modello proposto | Addestramento |
|---|---|---|---|
| Catalogazione documenti (sezione e voce) | Server Hetzner CPX42: 8 vCPU, niente GPU | **A:** vettori `embeddinggemma:300m` + testa lineare `numpy` (nessuna nuova dipendenza). **A+:** Italian-Legal-BERT specializzato, solo se batte A in modo netto (richiederebbe `onnxruntime` nel prodotto: decisione dell'avvocato) | Sul PC (3060): minuti |
| Seconda lettura con citazione (casi incerti) | Server | Spark-X2.5 4B attuale, oppure **Qwen3.5-4B con LoRA** sulle decisioni del catalogo | Sul PC (3060): QLoRA 4B in 1-3 ore |
| Ricevute, esenzioni, identità (campi) | Server | Regole + parser certificati (XML, MRZ, RT); nessun modello generativo per i dati che decidono | — |
| Ragionamento e stesura degli atti (schede, bozze) | **PC dell'avvocato**, via Tailscale | 35B MoE attuale (Qwen3.5-35B-A3B o equivalente: da confermare sul PC) | GPU cloud 80 GB |
| Chat generale di Lex | Server | `qwen3.5:9b` attuale | Nessuno per ora |

Regola di sicurezza: il server non dipende mai dal PC. Se il PC è spento, la stesura con il 35B si astiene con un messaggio chiaro, mentre catalogo, presìdi e scadenze continuano a funzionare.

### 6.3 Il modello grande: ragionare come l'avvocato

Obiettivo: davanti a un caso dell'avvocato, il 35B deve arrivare alle **stesse decisioni** delle schede approvate (rimedio, giudice, evento iniziale dei termini, norma applicata, imputazione dei pagamenti, conclusioni) e scrivere la bozza con la stessa struttura e lo stesso tono.

Punto di partenza misurato:

- CHANGELOG 2.449.0, banco v7 da 60 casi: con la scheda decisa dal codice gli esiti sbagliati scendono da circa 35 a 5-10 su 60.
- Il precedente addestramento «Lex v4» è stato provato e **non adottato**: non migliorava.

La lezione è che il modello va addestrato **a decidere la scheda**, non solo a scrivere, e che 22 casi approvati sono troppo pochi per un addestramento (insegnerebbero a memoria quei 22 testi).

Percorso in quattro passi, ognuno misurato prima di passare al successivo:

1. **Subito, senza addestramento: casi approvati come esempi.**
   - I 12 casi D4 approvati entrano in una biblioteca dei «casi risolti dallo studio».
   - Per ogni nuova richiesta Lex riceve il caso approvato della stessa materia come esempio di ragionamento, cioè scheda e bozza.
   - Le 10 schede V7 approvate diventano il **banco congelato**: mai usate come esempio né per addestrare, servono solo a misurare.
   - Misura: errori sul banco v7, prima e dopo.
2. **Moltiplicare i casi approvati: obiettivo 300-500.**
   - Il generatore D4 (casi inventati, nessun dato di clienti) produce schede e bozze per materia. Il codice calcola termini e importi (`lex/procedura_atti`); il 35B propone rimedio e ragionamento.
   - L'avvocato li rivede nello stesso formato del file appena approvato.
   - Per non spendere 60 ore di revisione, si rivedono **prima i casi in cui il 35B e il codice non sono d'accordo**, o in cui due stesure del modello divergono. Quelli concordi si campionano: uno su cinque, e se il campione ha errori si rivede tutto il lotto.
   - Le correzioni dell'avvocato valgono doppio: insegnano proprio dove il modello sbaglia.
   - Essendo casi inventati, per proporre le prime stesure si può usare anche un modello più grande in cloud, ma solo con l'autorizzazione dell'avvocato.
3. **Addestramento del 35B su GPU cloud.**
   - LoRA in bf16 su **una GPU da 80 GB** (A100 o H100). Per questo modello MoE la quantizzazione a 4 bit durante l'addestramento è sconsigliata dagli strumenti di riferimento (Unsloth). Indicativamente servono poche ore per 500-1000 esempi; le tariffe pubbliche partono da circa 1-3 $/ora per un A100 da 80 GB.
   - Sul cloud vanno **solo i casi inventati approvati**, mai dati dello studio.
   - Il formato degli esempi è quello già usato da `lex/dataset/llama_factory.py`: domanda, fatti, Fonti → scheda decisa → bozza. Per ogni scelta si conserva il ragionamento con la norma; le date non si chiedono al modello, le calcola il software.
   - Si esporta in GGUF e si carica sul PC accanto al modello attuale, con nome versionato.
4. **Adozione solo se migliora.**
   - Confronto sul banco congelato (10 schede approvate) e sulla parte di prova del banco v7.
   - Si mettono a confronto: 35B base + scheda, + esempi approvati, + LoRA.
   - Si adotta solo se ha **meno esiti sbagliati** e **nessuna regressione** sui casi approvati.
   - Anche dopo l'adozione restano attive le guardie esistenti: fonti obbligatorie, astensione «non determinabile con le fonti disponibili», date dal calcolo, revisione indipendente.

### 6.4 I modelli piccoli sul PC (RTX 3060 12 GB)

| Modello | Uso | Tempo indicativo sulla 3060 |
|---|---|---|
| Testa lineare su `embeddinggemma` | catalogo | pochi minuti, anche senza GPU |
| Italian-Legal-BERT specializzato | catalogo (alternativa A+) | 10-30 minuti |
| Qwen3.5-4B QLoRA | seconda lettura con citazione | 1-3 ore |
| Qwen3.5-9B QLoRA (opzionale) | chat di Lex sul server | 3-8 ore, al limite dei 12 GB |

Lo script di addestramento sta in `tools/addestramento/` (fuori dal gestionale, con dipendenze proprie). Legge un'esportazione pseudonimizzata: nomi, codici fiscali, indirizzi e importi identificativi sostituiti, con i documenti reali che non lasciano lo studio. Restituisce un file di pesi con impronta, versione e misure sul banco. Il server lo adotta solo se il banco della Fase 1 conferma il miglioramento.

### 6.5 Cosa serve dall'avvocato

1. Confermare il nome esatto del modello 35B sul PC: file GGUF e quantizzazione.
2. Indicare dove si trova sul PC il materiale D4 completo (i 12 casi sono un campione) e quanti casi contiene.
3. Indicare quante ore di revisione può dedicare: ogni 50 casi rivisti servono circa 10 ore. È il fattore che limita la qualità del modello grande.
4. Scegliere il fornitore della GPU cloud: si sceglie quando i casi approvati superano i 300; prima l'addestramento non conviene.

---

## 7. Addestramento del 35B: piano per risultati eccellenti (29/10/2026)

### 7.1 Dati ricevuti

- **Modello in uso:** `Qwen3.6-35B-A3B-UD-Q4_K_M.gguf` in WSL Ubuntu 24.04 sul PC (RTX 3060 12 GB, llama.cpp, ponte Tailscale verso il server).
- **Materiale D4:** 120 casi distinti (15 materie × 8) e 1.039 esempi derivati dagli stessi casi, circa 8,7 per caso. Gli esempi derivati non sono casi indipendenti.
- **Approvati dall'avvocato:** 12 casi D4 e 10 schede del banco v7 (60 casi in tutto).

### 7.2 Perché l'addestramento v4 non ha migliorato (cause da verificare sui file)

1. **Etichette non validate.** 108 casi su 120 non erano stati rivisti. Un errore in un caso si moltiplica per circa 8,7 esempi derivati: il modello impara l'errore con più forza della regola.
2. **Prova e addestramento possono condividere lo stesso caso.** Se gli esempi derivati vengono divisi per esempio e non per caso, la misura risulta falsata. La divisione corretta è per caso, e per materia nella prova finale.
3. **Poca varietà di decisioni.** 8 casi per materia non coprono le scelte che contano (rimedio, giudice, evento iniziale, norma, imputazione dei pagamenti). Il modello impara lo stile, non le distinzioni.
4. **Formato diverso da quello in uso.** L'esempio di addestramento deve avere lo stesso modello di messaggio, le stesse Fonti numerate e la stessa scheda che Lex riceve in produzione. Il ragionamento va scritto in una sezione fissa, non improvvisato.
5. **Si misura il modello che si usa.** L'addestramento avviene sui pesi bf16 originali, ma si misura il modello quantizzato UD-Q4_K_M che gira sul PC. La quantizzazione può cancellare parte del guadagno.

### 7.3 Che cosa garantisce la correttezza, oltre all'addestramento

Nessun addestramento rende un modello infallibile. La correttezza viene da tre livelli che restano tutti attivi:

1. **Il software decide ciò che è calcolabile:** termini (art. 155 c.p.c., L. 742/1969), importi, imputazione dei pagamenti, requisiti dell'atto (`lex/procedura_atti`). Il modello non calcola date né importi.
2. **Il modello decide ciò che richiede ragionamento giuridico**, cioè rimedio, giudice, norma, conclusioni e motivazione. Lo fa solo con le Fonti trasmesse e cita la Fonte di ogni scelta. Se la norma manca, la risposta è «non determinabile con le fonti disponibili».
3. **La revisione indipendente controlla la bozza contro la scheda** prima della consegna: date ed importi identici, conclusioni complete, Fonti citate esistenti.

L'addestramento migliora il secondo livello. Il risultato si misura sul banco approvato, campo per campo.

### 7.4 Ore di revisione: la risposta

Obiettivo misurabile: sul banco congelato (60 casi v7 approvati e 15 casi D4 tenuti da parte, uno per materia) **zero errori sulle decisioni** (rimedio, giudice, evento iniziale, norma applicata, conclusioni), **zero date o importi diversi dal calcolo** e **astensione corretta** quando la norma manca. Per raggiungerlo e dimostrarlo servono:

| Passo | Casi | Minuti per caso | Ore |
|---|---|---|---|
| A. Completare il banco v7 (servono tutte le 60 schede approvate per misurare) | 50 | 10 (sola scheda) | ~8 |
| B. Completare i casi D4 (scheda + bozza) | 108 | 12 | ~22 |
| C. Nuovi casi mirati alle decisioni sbagliate dal modello, 15 materie × circa 14 casi | ~210 | 8 in media* | ~28 |
| D. Revisione delle risposte sbagliate dopo ogni addestramento (2-3 giri) | ~60 | 10 | ~10 |
| **Totale** | | | **circa 68 ore** |

\* Il software prepara ogni caso e lo verifica da solo prima della revisione:
- controlla la scheda (`verifica_scheda`), le Fonti e i calcoli;
- confronta due stesure indipendenti.

L'avvocato riceve per primi i casi con disaccordi (circa 60%, revisione completa di 12 minuti). Gli altri li vede in forma ridotta (circa 4 minuti): solo i punti di decisione da spuntare, non tutta la bozza.

Distribuzione consigliata:

- **Prima tappa: A + B, circa 30 ore.** Al termine c'è una misura certa di quanto rende il modello base con scheda ed esempi approvati e di quanto aggiunge l'addestramento. Senza questa tappa non si può dire che il modello risponde correttamente.
- **Seconda tappa: C + D, circa 38 ore**, solo sulle materie e sulle decisioni dove la prima tappa mostra errori. Se una materia è già a zero errori, i suoi casi nuovi si riducono.

Le correzioni dell'avvocato diventano coppie «risposta sbagliata / risposta corretta» per l'addestramento a preferenza (DPO). Sono gli esempi che correggono di più, perché insegnano proprio dove il modello sbagliava.

### 7.5 Metodo di addestramento

1. **Base:** `Qwen/Qwen3.6-35B-A3B` in bf16 (gli stessi pesi da cui deriva il GGUF in uso).
2. **Primo stadio (SFT):** LoRA bf16 su una GPU cloud da 80 GB (H100 o A100). Ogni esempio contiene fatti, Fonti numerate e richiesta, seguiti da scheda con motivazione per punto e da bozza. Il formato è identico a quello di produzione.
3. **Secondo stadio (DPO):** le correzioni dell'avvocato e le risposte del modello scartate dalla revisione indipendente.
4. **Esportazione:** unione LoRA, conversione in GGUF UD-Q4_K_M (stessa quantizzazione), caricamento sul PC accanto al modello attuale con nome versionato.
5. **Misura sul modello quantizzato.** Si confrontano il 35B base con scheda, il base con esempi approvati recuperati per materia e il modello addestrato. Si adotta solo se, rispetto al base, ha meno errori e nessuna regressione sui casi approvati.
6. **Costo indicativo:** 3-5 corse di addestramento da 1-3 ore su una sola GPU da 80 GB, circa 10-15 ore GPU in tutto. Sul cloud vanno solo casi inventati e approvati.

### 7.6 Che cosa serve per partire

- Copiare in questa sessione, o in una cartella del repository riservata ai dati inventati, `casi_v4.jsonl`, `dataset_v4.zip` e il file del banco v7 (60 casi). Servono a verificare formato, divisione per caso ed errori del v4 prima di scrivere il generatore dei casi nuovi e lo strumento di revisione.
- Confermare se nel PC c'è anche il file della corsa v4 (configurazione, LoRA, risultati): permette di capire con certezza perché non è stata adottata.

### 7.7 Il software aiuta il modello: normativa e giurisprudenza già presenti

Osservazione dell'avvocato del 29/10/2026: il 35B deve lavorare insieme agli archivi del software, non da solo. Stato attuale:

- **Normativa: già collegata.** La stesura riceve come Fonti il testo vigente degli articoli della scheda, letto dalla biblioteca «Codici e leggi», con impronta e provenienza (`lex/procedura_atti/fonti_scheda.py`).
- **Ricerca normativa ibrida: già pronta, non ancora nella stesura.** Unisce l'indice lessicale e quello vettoriale (`lex/ricerca_giuridica/`) e trova articoli pertinenti oltre a quelli elencati nella scheda.
- **Giurisprudenza: presente ma non usata nella stesura.** L'archivio esiste (`lex/retrieval/sources/giurisprudenza.py`, ricerca OpenGA, sentenze dello studio), con le guardie su ECLI, URL ufficiale e classe di affidabilità A.

Piano:

1. **Fonti allargate e controllate.** Alle Fonti della scheda si aggiungono:
   - fino a 3-5 articoli trovati dalla ricerca ibrida, marcati «da verificare», mai al posto di quelli della scheda;
   - fino a 3 decisioni dell'archivio, solo se il testo integrale è verificato e ha ECLI o URL ufficiale.
   
   Tutto resta numerato e citabile; ciò che non è nelle Fonti non si cita (guardie esistenti `citation_guard` e `hallucination_guard`).
2. **Addestramento sullo stesso contesto.** Gli esempi di addestramento contengono le stesse Fonti allargate che il modello riceverà in produzione. Includono anche Fonti pertinenti ma inutili per il caso, così il modello impara a scegliere la norma giusta e a ignorare le altre: è il metodo detto RAFT, addestramento con documenti di disturbo. Così il modello impara a usare gli archivi, non a ricordarne il contenuto a memoria.
3. **Quattro configurazioni sullo stesso banco:** 35B con sola scheda; con Fonti allargate; con Fonti allargate ed esempi approvati della stessa materia; addestrato con Fonti allargate. Si adotta la combinazione con meno errori. Se le Fonti allargate peggiorano una materia (per esempio perché introducono una giurisprudenza non pertinente), per quella materia restano spente.
4. **Il controllo di ogni citazione resta attivo:** articolo vigente alla data del fatto, decisione con riferimento completo, nessuna massima senza testo verificato.

---

## 8. Requisiti dell'avvocato del 31/10/2026 (vincolanti)

Riassunto dettato dall'avvocato perché nessuna sessione lo perda. Ogni lavoro su catalogo, modelli e presìdi parte da qui e dal piano sopra; la sola catalogazione non basta.

**Classificatore dei documenti del fascicolo (Spark-X2.5 4B oggi), addestrato in locale sul PC dell'avvocato**, per riconoscere meglio:
- la catalogazione degli atti;
- i documenti d'identità dei clienti presenti nel fascicolo;
- il contributo unificato e la sua ricevuta, l'autocertificazione del contributo, la certificazione di esenzione, anche da documenti letti con OCR.

**Documenti d'identità**
- assegnazione automatica del documento d'identità presente nel fascicolo alla cartella del cliente, con controllo della scadenza;
- in compilazione anagrafica, lettura del documento e compilazione automatica dei campi;
- controllo degli atti: i dati delle parti negli atti devono essere corretti rispetto al documento e alla scheda.

**Presidio notifiche**: deve sapere quali atti vanno notificati, a chi e entro quando, e seguirne la prova.

**Presidio scadenze**: controlla le scadenze in base alle normative vigenti; lo scadenziario si calcola secondo le norme e le scadenze da controllare.

**Agenda e calendari** popolati automaticamente dal motore PEC e dal motore di lettura dei fascicoli, con controlli contro i doppioni.

**Economia del fascicolo**: in tutti i fascicoli la vista economica (contributo, spese ed esborsi, liquidazione, parcella) è sincronizzata e collabora con il contesto economico del fascicolo.

**Trasversale**: tutti i processi vanno analizzati e migliorati per essere veloci, conformi a tutte le norme e intuitivi per l'avvocato. Motori, modelli e acquisizione OCR dei documenti devono essere sincronizzati e collaborare.

**AI locale e documenti grandi** (aggiunto il 31/10/2026): l'AI locale non deve bloccarsi né leggere un documento a metà. Se il documento supera il contesto del modello, il software lo divide da solo in parti (chunk) entro il budget del contesto, le fa leggere tutte nell'ordine e unisce i risultati; nessun taglio silenzioso del testo. Se una parte non si legge, il documento risulta letto in parte, con l'indicazione di quale parte manca, mai come letto per intero.

**Ciò che ancora manca**: un classificatore addestrato sulle etichette certificate (XML di ricevute ed esiti, `Comunicazione.xml`, pagoPA, SdI, tipo atto PST) e sulle decisioni già prese dall'avvocato. Si misura contro le regole, sui dati reali, sul server, e si adotta solo dove riduce gli errori.

**Metodo richiesto**: prima l'analisi di tutta la catena e dei percorsi esistenti, poi un piano di miglioramento su tutto, poi i test che dimostrano un miglioramento significativo. Si implementa solo dopo il via dell'avvocato.

---

## 9. Stato reale al 31/10/2026 e piano operativo aggiornato

Verifica in sola lettura sul codice al commit `93e70dc18` (cinque analisi, una per catena). Fatto = verificato nel codice; nessuna prova funzionale sui dati reali è ancora stata eseguita.

### 9.1 Stato per fase del piano

| Fase | Stato | Note principali |
|---|---|---|
| 0 Correzioni giuridiche | G1, G3, G6, G7 fatti; G2, G4, G5 parziali | Quattro motori dei termini ancora attivi (anche `lex/workflows/termini_processuali_workflow.py:166`, senza art. 155 né sospensione feriale); `date.today()` residuo in presidio documentale e operativo, Polisweb, PTT, modifica termini PEC |
| 1 Verità certificate e banco | Parziale | Arrivano solo tipo atto PST e tipo atto della busta, e solo nel censimento; `Comunicazione.xml`, RT, SdI, `.p7m` non diventano etichette; il confronto «regole» è falsato (usa l'etichetta già corretta); nessun banco sul server; prova divisa per documento, non per fascicolo |
| 2 Classificatore addestrato | Avviato sul PC (Qwen QLoRA) | Addestrato su proposte delle regole ≥96, non sul livello A: impara a copiare le regole |
| 3 Un solo flusso | Non fatto | Sei classificatori; tre OCR per file; presìdi serviti prima del catalogo; RAG lento fa fallire l'evento; nessun evento dopo Spark o la correzione dell'avvocato |
| 4 Identità e anagrafica | Non avviata | Pipeline principale senza cliente; abbinamento dal solo nome; documento d'identità candidato al deposito; scadenza in due copie senza preavvisi; file della compilazione anagrafica scartato; controllo degli atti solo su nome e CF dell'assistito |
| 5 Contributo ed economia | Non fatto | Stato del CU in 7 posti scritti da 6 percorsi; RT letta come totale o come quota; RT frazionate che si sovrascrivono; patrocinio letto come esenzione invece di prenotazione a debito; promemoria pagoPA come pagamento; proforma con il CU della sentenza; preventivi con importi fissi errati |
| 6 Notifiche, scadenze, agenda | Parziale | Le notifiche **ricevute** non aprono termini (artt. 641, 325, 480/615); direzione L. 53 non distinta; obblighi non chiusi per destinatario dalle RAC/RdAC; niente ReGIndE/INI-PEC negli obblighi; fascia 21-7 non applicata; art. 327 non proposto; eventi di cancelleria generici; allegati PEC non catalogati; nessuna scadenza dedotta dall'udienza; rinvio che non sposta i termini; otto casi di doppione |
| 7 Intuitività | Non avviata | — |

### 9.2 Ordine di lavoro proposto (per rischio giuridico)

1. **Termini e notifiche** (rischio di termini persi): un solo motore dei termini, anche per Lex; notifiche ricevute → termini; direzione L. 53; chiusura per destinatario; fascia 21-7; art. 327; eventi di cancelleria specifici da `Comunicazione.xml`; allegati PEC catalogati nel fascicolo; scadenze dall'udienza e rinvio.
2. **Contributo ed economia**: registro unico del CU con quote (CU, art. 30, bollo), frazionato, prenotazione a debito, esenzioni art. 10 e 9 c. 1-bis, art. 14 e art. 16; proforma, preventivi e parcelle dal registro; un solo motore della sentenza. Il confronto nella busta resta ❄ (serve l'autorizzazione dell'avvocato).
3. **Identità e anagrafica**: Fase 4 per intero.
4. **Agenda senza doppioni**: registro unico degli eventi con fonti multiple, chiusura degli otto casi.
5. **Catalogo e classificatore**: confronto corretto con la proposta originale delle regole; livello A (PST, busta, `Comunicazione.xml`, RT, SdI) in esportazione e misura; etichetta certificata prevalente; storia delle decisioni conservata; evento `catalogo.cambiato` che ricalcola obblighi, identità ed economia; banco sul server diviso per fascicolo; poi riaddestramento e adozione per voce.
6. **Orchestrazione e velocità**: un solo OCR per file, regia di Ollama, RAG che non fa fallire l'evento, query O(K) invece di riletture complete.

### 9.3 Test di accettazione (aggiunti a quelli della sezione 4)

| Area | Test | Criterio |
|---|---|---|
| Termini | griglia di 2.000 casi sui quattro motori | 0 differenze; nessun `date.today()` nei moduli dei termini |
| Notifiche ricevute | 20 PEC L. 53 ricevute (decreti, sentenze, precetti) | tipo e termine giusti in ≥19/20; 0 proposte «notificare entro 60 giorni» su decreti ricevuti |
| Direzione | 10 PEC inviate e 10 ricevute | 20/20; nessuna attesa di RdAC su PEC ricevute |
| Chiusura per destinatario | due destinatari, una RdAC e una mancata consegna | obbligo «parziale» con il destinatario nominato; chiusura alla seconda RdAC |
| Fascia oraria e art. 327 | RdAC alle 22:10 del 31/07; sentenza depositata il 15/03 | decorrenza dalle 7:00 dell'01/08 con sospensione feriale; scadenza art. 327 al 16/10 (15/09 + 31 giorni di agosto) |
| Comunicazioni di cancelleria | 50 `Comunicazione.xml` reali | evento specifico ≥90%; provvedimento allegato catalogato ≥95% |
| Scadenze dall'udienza | udienza verificata e rinvio di 30 giorni | 3 memorie 171-ter e costituzione in bozza; 4/4 spostate, tranne le modifiche manuali |
| CU | RT 518 + 27; due RT da 259; patrocinio; promemoria; RT prima dell'RG | CU 518 e art. 30 27 in tutti i percorsi; 518 col frazionato; patrocinio `prenotato_a_debito`; 0 promemoria «pagati»; stato «pagato» senza RG |
| Fonte unica CU | 50 fascicoli reali | 0 differenze fra deposito, scheda, proforma e presidio |
| Identità | 30 documenti d'identità reali | ≥95% collegati al cliente giusto; 0 collegamenti a omonimi con CF o data di nascita diversi; 0 candidati al deposito |
| Scadenza documento | data malformata; scadenza a 59 giorni | cruscotto senza eccezioni; preavviso a 60 e 30 giorni, una sola data |
| Controllo atti | atti con data, luogo, residenza diversi, anche della controparte | una discordanza per campo; 0 falsi positivi su 20 atti corretti |
| Doppioni | gli otto casi con 2-3 fonti | 1 riga e N fonti; secondo giro con 0 scritture |
| Catalogo | documenti corretti dall'avvocato | «regole» misurate sulla proposta originale; 0 fascicoli sia in addestramento sia in prova; 0 etichette del catalogo contro un livello A |
| Propagazione | correzione da «Sentenza» ad «Allegato» | entro il giro successivo 0 scadenze aperte di quell'obbligo |
| Velocità | caricamento di un PDF scansionato; RAG oltre 60 s; 10.000 scadenze + 50 nuove | 1 OCR e 1 giro; evento riuscito con RAG rimandato; nessuna rilettura completa della tabella |

### 9.4 Decisioni che servono all'avvocato

1. Via libera all'ordine della sezione 9.2 (o un ordine diverso).
2. Flusso congelato ❄: il confronto del CU nella busta e lo stato del patrocinio nel DatiAtto si correggono dentro la busta o solo a monte nel presidio?
3. ReGIndE e INI-PEC: consultazione automatica degli elenchi pubblici dal server (con data di consultazione) oppure solo indirizzo inserito dall'avvocato?
4. Corpus di verifica sui dati reali: autorizzazione a usare sul server, senza che nulla esca, PEC e documenti dello studio per i test di accettazione (20 notifiche ricevute, 50 comunicazioni di cancelleria, 30 documenti d'identità, 50 fascicoli per il CU).

### 9.5 Avanzamento del punto 1 (31/10/2026)

Fatto, con test (copertura righe e rami 100% sui moduli nuovi):

- Lex calcola i termini col motore unico e la tabella normativa è una sola (art. 166 a 70 giorni prima, art. 92 c.p.a., art. 617, art. 307 a 3 mesi; nessun termine inventato); `oggi_roma()` nei presìdi, PolisWeb, PTT e modifica termini PEC.
- Notifiche ricevute dalla controparte (`pct/notifiche_ricevute.py`, `pct/notifiche_ricevute_pec.py`): direzione dalla casella che riceve, perfezionamento per il destinatario (art. 147 c.p.c., consegna dopo le 21 → giorno dopo), termini di opposizione a decreto ingiuntivo, precetto, controricorso, appello o cassazione dalla sentenza notificata, costituzione del convenuto e dell'appellato a ritroso; nessun presidio in attesa di RAC/RdAC; torre di controllo con la categoria «Atto notificato dalla controparte».
- Termine lungo di impugnazione (art. 327): decorre **solo dalla data di deposito** della sentenza (art. 133 c.p.c.), mai dalla comunicazione di cancelleria, che non fa decorrere alcun termine. La data si legge nell'ordine: testo della comunicazione, timbro di pubblicazione della sentenza allegata, documenti del fascicolo già letti dall'archivio delle letture (solo se univoca; col numero della sentenza quando la comunicazione lo indica). Senza data resta un promemoria senza data. Il giro periodico (`web/services/termine_lungo_runtime.py`, regola in `pct/termine_lungo_sentenza.py`) propone la bozza in scadenziario; il termine breve resta escluso dalla sola comunicazione.
- Eventi di cancelleria specifici da `Comunicazione.xml` (decreto ingiuntivo emesso, rigettato, esecutivo; cancellazione dal ruolo; interruzione; riserva sciolta) e termini di riassunzione (artt. 305 e 307).
- Memorie 171-ter proposte dalla prima udienza in agenda e ricalcolate al rinvio (`pct/scadenze_da_udienza.py`), nel giro periodico delle notifiche.
- Presidio notifiche: riconciliazione mirata per identità intera (il presidio «P-1» non tocca più «P-12»).

Da progettare a sé: chiusura dell'obbligo di notifica **per destinatario** con le ricevute PEC. Serve un collegamento certo fra la PEC di notifica inviata (impronta SHA-256 dell'atto allegato, indirizzo di ciascun destinatario), le RdAC separate e l'atto catalogato; un collegamento per somiglianza di nomi chiuderebbe obblighi per errore. Fino ad allora l'obbligo resta aperto con il motivo (comportamento prudente attuale). ReGIndE e INI-PEC: in attesa della decisione dell'avvocato (sezione 9.4, punto 3).

### 9.6 AI locale a parti: dove oggi il documento non arriva intero (censimento del 31/10/2026)

Contesto del modello: `lex/settings.py` (`num_ctx` 8192, risposta 700 token). Tagli che oggi impediscono all'AI di leggere il documento per intero:

| Percorso | Taglio | Compito dell'AI |
|---|---|---|
| Estrattore `lex/tools/_doc_extractor.py` | 12.000 caratteri e **solo le prime 15 pagine** (anche OCR) | alimenta Lex e gli strumenti |
| Ricerca documenti di Lex `lex/retrieval/documenti.py` | 1.200 caratteri di testa (Docling escluso) | rispondere alle domande |
| Strumenti operativi `lex/operational_knowledge/tools.py` | 1.200 caratteri di testa | prove per la risposta |
| Contesto documento `lex/context/document_context.py` | 2.400 caratteri | contesto della risposta |
| Budget del prompt `lex/providers/prompt_budget.py` | 12 prove da 1.600 caratteri, le altre escluse | tutte le risposte di Lex |
| «Chiedi al fascicolo» / lettura del fascicolo `pct/local_ai.py` | nessun budget: oltre 8192 token **Ollama taglia in silenzio** | risposta e sintesi |
| Bozza dell'editor `pct/editor_ai/` | testo intero senza budget: **taglio silenzioso** | stesura dell'atto |
| Seconda lettura del catalogo `catalog_lex.py` | 4.000 caratteri (voluto: intestazione e titolo) | classificazione |

Soluzione (punto 6): un solo lettore a parti, sul modello di `lex/procedura_atti/lettura_fonti.prepara_letture` (che misura il prompt reale, legge parti contigue, registra l'impronta di ogni parte e non taglia mai): se il testo sta nel contesto passa intero; altrimenti si divide in parti contigue senza perdite (`bounded_text_chunks`), ciascuna letta dal modello entro il budget, e i risultati si uniscono con la parte di provenienza. L'estrattore non si ferma più a 15 pagine. Una parte non letta lascia il documento «letto in parte» con l'indicazione della parte mancante. La classificazione resta sull'intestazione (scelta voluta). Nessun prompt supera più il contesto senza saperlo.
