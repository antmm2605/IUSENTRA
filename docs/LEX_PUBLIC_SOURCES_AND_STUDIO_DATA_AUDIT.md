# LEX — Audit: Fonti Pubbliche e Dati Studio (v2.201.0)

Documento di audit tecnico sul comportamento attuale di Lex nella gestione delle fonti pubbliche (sentenze, normativa, giurisprudenza) e dei dati interni dello studio (clienti, fascicoli, anagrafica).

---

## Aggiornamento operativo 2.245.8 - 2026-05-17

Lex non tratta più una richiesta redazionale con cliente, ad esempio
`scrivi diffida per il cliente Marco Moscato`, come semplice ricerca
anagrafica. Il profilo `bozza_lettera` forza il workflow redazionale,
poi il contesto studio autorizzato viene usato per compilare intestazione,
avvocato e cliente quando disponibili.

Le richieste operative su dati studio sono state verificate con test reali su
`/api/assistente/context` e `/api/assistente/chat`: dati cliente, recapiti,
PEC, telefono e ultime udienze vengono letti dagli archivi tenant-aware invece
di rispondere con base documentale insufficiente.

Le bozze Lex vengono restituite senza appendici `Fonti consultate` non
pertinenti quando il workflow è una lettera/diffida. Il widget rende la
risposta come documento leggibile: titoli, grassetto, corsivo, separatori,
elenchi e blocco documento. Se una bozza arriva già schiacciata in una riga,
la UI la normalizza prima del rendering.

È stato aggiunto il presidio UTF-8 `utf8-integrity`: CLI, servizio e job
notturno rilevano mojibake, caratteri sostitutivi e testi con accenti italiani
rotti. Le guardie Lex riparano l'output prima di mostrarlo all'utente.

## Aggiornamento operativo 2.245.5 - 2026-05-17

Il presidio creato per fonti, agenti notturni, archivi ufficiali e funzioni AI
avanzate e' ora esposto anche nelle pagine usate dallo studio:
`/ricerca-legale` e `/giurisprudenza/`. Non rimane confinato alle console
amministrative.

`/ricerca-legale` mostra una sezione `Presidio Lex AI` con agenti controllati,
ricerca completa su fonti ufficiali e allegati pubblici quando disponibili,
archivi Normattiva/Gazzetta locali e stato delle funzioni MTP, LLM Wiki,
GLM-OCR e Gemini Embedding 2 come presidi misurabili o da autorizzare.

`/giurisprudenza/` mostra `Citazioni verificate` e `Presidio Lex
giurisprudenza`: conteggio delle schede citabili, stato Cassazione, agenti
collegati, archivi ufficiali e allegati fonte letti se presenti. Le modalita'
di accesso sono rese in linguaggio operativo per l'avvocato, non con codici
interni.

## Aggiornamento operativo 2.243.5 - 2026-05-16

Aggiornamento 2.245.3: IUSENTRA ha ora micro-agenti Lex interni collegati
alla console pianificazioni e al job notturno `lex_operational_agents_nightly`.
Gli agenti non sono sub-processi liberi o comandi shell: derivano dai template
autorizzati, leggono solo archivi tenant-aware e salvano un inventario in
`lex_operational_agents.json`. La copertura include anagrafiche, fascicoli,
agenda/scadenze, preventivi/parcelle, PEC, posta ordinaria, documenti,
editor Lex, Cassazione, PCT, SDI/pagamenti, portale cliente, GDPR/AML, AI
locale/RAG e integrazioni. Se manca un archivio, un indice o una fonte
verificabile, l'esito resta `Da verificare` con chiavi mancanti e controllo
supervisore, invece di essere mostrato come completato.

Lo stesso aggiornamento estende il presidio pubblico: i codici fondamentali
su Normattiva (civile, procedura civile, penale, procedura penale, processo
amministrativo e strada) sono censiti come fonti di classe A, insieme al
presidio Cassazione per citazioni verificabili. Lex non deve pubblicare
massime, sezione, numero o data se non trova riscontro nel corpus ufficiale o
in una fonte ufficiale governata.

Aggiornamento 2.245.2: per Giustizia Amministrativa il canale HTML
istituzionale diretto e' stato messo in osservazione, perche' puo' fallire in
modo instabile durante crawler/SSL. Il presidio automatico principale passa a
OpenGA ufficiale (`openga_giustizia_amministrativa` e cartelle `openga_*`),
che espone dataset CKAN per sentenze, ordinanze, decreti, pareri,
provvedimenti, ricorsi e calendario udienze. Gli agenti fonte non marcano piu'
come completata una scansione che contiene errori interni: l'esito diventa
`failed`/da verificare e registra anche la soluzione alternativa applicata.
La stessa normalizzazione vale per gli esiti gia' salvati: un vecchio record
`completed` con errore dentro `payload_json.reports[].error` viene riletto come
`Da verificare`, cosi' la console non conserva stati falsamente positivi.
La pagina React `Archivio Giurisprudenza` traduce gli stati tecnici in esiti
operativi: `Da verificare`, `Aggiornata` o `Recupero assistito`; per la fonte
diretta amministrativa espone la nota di risoluzione verso OpenGA invece di
lasciare un errore non governato.
Lo stesso criterio e' applicato alle altre fonti giurisprudenziali: Cassazione
ha come canale automatico la pagina ufficiale delle ultime sentenze e ordinanze,
Corte costituzionale tenta direttamente lo ZIP open data se la pagina indice
fallisce, CURIA usa il feed RSS ufficiale e HUDOC espone il fallback RSS per
ricerche salvate.

Aggiornamento 2.245.0: le fonti legali sono governate anche come agenti
separati. Il batch con timeout resta il percorso notturno principale, ma ogni
fonte registra una run autonoma in `source_agent_runs` con stato, durata,
timeout, documenti trovati, documenti lavorati, invariati e messaggio di
errore. `/admin/aggiornamenti-legali/fonti` mostra l'ultimo esito agente per
canale e `/admin/pianificazioni` crea job `legal_source_<codice>` avviabili
manualmente o schedulabili dal superadmin, sempre da catalogo autorizzato e
senza comandi shell.

Aggiornamento 2.243.9: `/admin/aggiornamenti-legali/fonti` espone il
catalogo professionale delle fonti con famiglie, stato per canale,
conteggi reali, ciclo giornaliero e regole incrementali. Oltre alle fonti
richieste sono stati aggiunti presidi ufficiali scelti per gli studi legali:
INPS circolari/messaggi/sentenze, Curia CGUE, ISTAT prezzi, MIMIT incentivi,
AGCM, AGCOM e Banca d'Italia. INAIL e' censita come fonte in osservazione ma
non entra nel ciclo automatico finche' il canale pubblico non sara' leggibile
con stabilita' dal worker.

Aggiornamento 2.243.8: gli archivi locali ufficiali non restano piu'
separati dalla UI. La Ricerca Legale e la console admin Aggiornamenti legali
mostrano i conteggi reali di Normattiva/Gazzetta e, quando l'utente cerca, il
backend interroga prima `legal_updates.db`, poi `/data/normativa/normattiva.sqlite`
e `/data/fonti_ufficiali/lex_sources.sqlite`; solo se le evidenze locali non
bastano viene tentata la ricerca web governata. Questo rende visibili i
189.851 documenti, 800.757 articoli e 639.273 chunk Normattiva gia' presenti
sul volume Hetzner.

Lo scheduler 2.243.8 governa il ciclo quotidiano richiesto: alle 23:00 esegue
sincronizzazione degli archivi ufficiali, alle 23:10/23:15 passa a Update
Intelligence con timeout per fonte/pubblicazione. La sincronizzazione
Normattiva confronta il catalogo Open Data remoto con lo stato locale e non
riscarica ZIP gia' presenti e invariati; quando una collezione cambia mantiene
una sola copia per collezione/formato/vigenza. OpenGA viene trattata come fonte
ufficiale CKAN nelle cartelle Calendario Udienze, Decreti, Ordinanze, Pareri,
Provvedimenti pubblicati, Ricorsi definiti, Ricorsi pendenti, Ricorsi pervenuti
e Sentenze. La verifica pubblica legge anche contesto pagina e allegati
ufficiali collegati, cosi' Lex riceve evidenze testuali e non solo link.
Sono stati aggiunti anche presidi ufficiali ad alto valore per studi legali:
interpelli del Ministero del Lavoro, newsletter/provvedimenti del Garante
Privacy, atti ANAC e download tecnici del PST Giustizia.

Update Intelligence non pubblica piu' automaticamente una proposta strutturale solo per confidenza AI: prima dell'autopublish viene eseguita una verifica pubblica governata su archivio fonti ufficiali, Normattiva, Gazzetta e ricerca web allowlist. Per normativa, prassi e giurisprudenza servono almeno una fonte primaria e una seconda conferma coerente; in caso contrario la proposta resta in coda revisioni con una nota operativa.

Aggiornamento 2.243.6: lo staging non usa piu' la coda revisione come stato primario del documento grezzo. All'apertura di `/admin/aggiornamenti-legali/staging` viene tentata la riconciliazione automatica: duplicati chiusi, cataloghi open data archiviati come non pubblicabili, contenuti ufficiali utili ma non strutturali pubblicati come news informativa quando superano la verifica fonte.

I path di Normattiva e Gazzetta sono ora collegati ai volumi runtime (`/data/normativa` e `/data/fonti_ufficiali`) tramite variabili ambiente e fallback container-aware, cosi' Lex e il motore aggiornamenti usano gli archivi generati in produzione invece dei soli file smoke locali.

Verifica infrastrutturale del 2026-05-16: i database canonici Normattiva/Gazzetta non erano presenti su Railway ne' su Hetzner. Su Hetzner sono stati ricreati nel volume attivo: Gazzetta (`lex_sources.sqlite` 32.129.024 byte, JSONL 20.342.735 byte, 28 documenti e 3.911 chunk) e Normattiva (`normattiva.sqlite` 2.868.604.928 byte, JSONL 1.093.268.667 byte, 19 ZIP raw validi, 189.851 documenti, 800.757 articoli e 639.273 chunk). Il manifest ufficiale Normattiva letto da `https://dati.normattiva.it/assets/come_fare_per/Normattiva%20OpenData.html` espone 23 collezioni: 19 hanno restituito ZIP validi, mentre `Regolamenti di delegificazione`, `Regolamenti governativi`, `Regolamenti ministeriali` e `Testi Unici` hanno restituito stream vuoto `application/octet-stream` e sono tracciate nel manifest tentativi. Railway ha il volume `/data` al 100% (1.8 GB usati su 1.8 GB, con circa 1.3 GB in allegati email) e non puo' ospitare l'indice Normattiva completo finche' non viene aumentato o liberato spazio senza cancellare dati di studio.

Aggiornamento 2.243.7: il lotto notturno `legal_updates_batch`, la console admin e il comando CLI possono eseguire la scansione massiva come job isolati per fonte/pubblicazione con timeout per elemento (`IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS`, default 180s). Le verifiche web esterne restano attive, ma un elemento lento non blocca l'intero processo.

---

## Aggiornamento operativo 2.243.4 - 2026-05-16

Lex AI legge ora anche il registro mediazione interno popolato dai tre elenchi ufficiali del Ministero della Giustizia: Registro Organismi, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le evidenze sono marcate come fonte ufficiale di classe A e includono sezione, numero registro, denominazione o nominativo, stato, natura/tipo docente, territorio, codice fiscale, partita IVA, email e sito quando presenti.

La pagina `/ricerca-legale/mediazione` usa gli stessi dati acquisiti: non e' piu' un elenco di collegamenti, ma un archivio consultabile in IUSENTRA con ricerca e filtri. Lex riceve il contesto dal repository interno `normative_tables`, mentre il collegamento ministeriale resta riferimento di verifica.

La verifica API autenticata restituisce 3.038 schede: 3.035 record ministeriali piu' i tre accessi ufficiali. Il bridge usa l'identita' della riga importata e non l'URL ministeriale, cosi' i dati non vengono ridotti a una sola scheda per fonte.

OpenGA Giustizia Amministrativa e il gruppo `calendario-udienze` sono stati aggiunti al presidio Update Intelligence come fonti CKAN JSON; le risorse JSON disponibili vengono acquisite come testo consultabile per ricerca e Lex.

---

## Aggiornamento operativo 2.239.2 - 2026-05-16

La pagina React `Registro Mediazione` non dipende piu' dalla sola notizia di ripristino: espone tre schede di accesso ufficiale separate verso Registro Organismi di Mediazione, Elenco Enti per la Mediazione ed Elenco Formatori per la Mediazione. Le schede sono disponibili anche nella Ricerca Legale per query su mediazione, enti e formatori, senza leggere dati privati dello studio e senza avviare una ricerca esterna.

---

## Aggiornamento operativo 2.238.2 - 2026-05-15

Le richieste Lex su sentenze specifiche con numero e date multiple, ad esempio `Sentenza n. 14575 ud. 15/04/2026 - deposito del 21/04/2026`, non cadono piu' sul metadata `SourceScope.reason`: il campo e' compatibile con i payload debug e il workflow `giurisprudenza_specifica` continua a produrre risposta governata.

Per i riferimenti Cassazione esatti, Lex prioritizza `cassazione` tra le fonti ufficiali e, se la ricerca generica non e' necessaria, legge la pagina pubblica `Giurisprudenza Penale` della Corte. La query sopra individua la scheda ufficiale `https://www.cortedicassazione.it/it/penale_dettaglio.page?contentId=SZP50042`; la risposta indica cosa e' certo e resta `needs_review` finche' mancano testo integrale, motivazione e dispositivo.

Il widget Lex non mostra piu' pagine HTML di errore dentro la conversazione. Se `/api/assistente/chat` fallisce prima dello stream, l'endpoint risponde con JSON controllato e la UI mostra un messaggio operativo breve, lasciando il dettaglio tecnico ai log applicativi.

---

## Aggiornamento operativo 2.238.0 - 2026-05-15

`/ricerca-legale` non e' piu' una vista con filtro locale sulle sole schede gia' caricate. La query viene passata a `/api/v1/ui/ricerca-legale?q=...`, cercata nel repository giuridico SQL tenant-aware e arricchita con fallback ufficiale governato quando non ci sono almeno due fonti ufficiali con estratto testuale sufficiente.

La notizia PST `NWS4865` sul ripristino dei registri mediazione e' presente come fonte ufficiale stabile in News e Ricerca Legale, con link al Portale dei Servizi Telematici, data 2026-05-11 e contesto del ripristino dal 22/04/2026.

---

## Aggiornamento operativo 2.237.9 - 2026-05-15

Lex Operational Knowledge e' ora attivo di default nel bounded workflow: le domande su clienti, fascicoli, agenda, scadenze, preventivi, conferimenti, fatturazione, messaggi, documenti e template passano dal layer deterministico tenant-aware senza richiedere `LEX_OPERATIONAL_KNOWLEDGE_ENABLED=1`.

La ricerca giuridica pubblica resta separata: richieste su sentenze specifiche, giurisprudenza, normativa, Normattiva, Gazzetta, Cassazione o fonti ufficiali vengono deferite al workflow pubblico/web governato e non sono intercettate dal layer dei dati di studio. Restano sempre attivi RBAC, isolamento tenant, blocco azioni dispositive e protezione dei dati riservati.

Il fallback web legale non viene piu' bloccato dalla sola presenza di contesto interno: per `ricerca_legale`, giurisprudenza, normativa e fonti ufficiali, se il contesto locale non basta a rispondere, il payload Lex abilita `allow_external_research` e richiede fonti ufficiali governate. Le risposte strict includono il contesto testuale delle fonti effettivamente usate; se una fonte e' solo nominata ma non porta un estratto, Lex degrada la risposta a `needs_review`.

---

## 1. Come Lex decide oggi se usare contesto interno

Il contesto studio viene costruito da `web/services/assistente_studio_context.py` tramite `build_lex_studio_context()`. La decisione avviene in due step:

### Step A — Selezione sezioni per keyword (`_select_detail_sections`)
Le sezioni vengono incluse in base a match testuale sulla domanda. Threshold: top 5 sezioni per punteggio.

| Sezione | Keyword trigger |
|---------|----------------|
| Clienti | "cliente", "clienti", "assistito", "anagrafica" |
| Fascicoli | "fascicolo", "fascicoli", "rg", "pratica", "causa" |
| Agenda | "agenda", "appuntamento", "udienza" |
| Scadenziario | "scadenza", "termine", "scadenze" |
| Fatturazione | "fattura", "parcella", "onorario" |

**Problema**: se la domanda è "dammi i dati del cliente Mario Rossi" ma il nome del cliente è in minuscolo e la sezione non viene triggerata per via di normalizzazioni, Lex non carica il contesto cliente.

### Step B — Caricamento dati (`_clienti_lines`)
```python
selected = matches[:4] if matches else all_rows[:4]
```
**Limite critico**: massimo 4 clienti. Se ci sono omonimi o la ricerca restituisce molti risultati, i dati dettagliati vengono tagliati. Il testo restituito è solo `nome_completo + stato + referente` — mancano CF, PEC, email, telefono, fascicoli.

---

## 2. Come Lex decide oggi se usare il web

La funzione `_should_force_web_fallback()` in `assistente_studio_context.py` forza ricerca web se:
- NON è una query solo operativa (agenda/fascicolo/cliente senza termini legali)
- NON c'è contesto locale specifico (`_has_specific_local_context` = False)
- Almeno un token legale è presente: norma, normativa, legge, decreto, sentenza, cassazione, tar, giurisprudenza, etc.

**Problema critico**: `_has_specific_local_context` restituisce True se ci sono fonti `cliente:*` o `fascicolo:*` nei sources, **bloccando la ricerca web anche per sentenze specifiche**. Se la domanda è "nel fascicolo Rossi trova la Sentenza n. 7919" → contesto fascicolo viene caricato → `_has_specific_local_context = True` → web bloccato → Lex usa solo il DB locale che non contiene quella sentenza.

---

## 3. Perché una sentenza specifica non forza ricerca web

Il router classifica correttamente "Sentenza n. 7919 del 31/03/2026" come `giurisprudenza_specifica` (priorità 7 in `lex/router.py`). Ma il retrieval layer non ha un meccanismo di "exact reference override": anche per `giurisprudenza_specifica`, se esiste qualsiasi fonte locale (anche solo `studio:default` o agenda), `_has_specific_local_context` può restituire True e bloccare il web.

Non esiste `case_law_reference_parser.py` che estragga numero+data da una query e forzi `public_web_forced=True`. Il sistema non distingue "dimmi delle sentenze sulla prescrizione" (generico) da "trovami la Sentenza n. 7919 del 31/03/2026" (riferimento esatto).

---

## 4. Perché vengono mostrate fonti correlate non richieste

Il motore di retrieval (`lex/retrieval/orchestrator.py`, `lex/research/public_legal_research_gateway.py`) non ha un "exact match guard". Quando cerca sul web governato, restituisce tutti i risultati rilevanti per il query semantico, non filtrati per numero/data sentenza. L'`answer_builder.py` non distingue tra "fonte esatta richiesta" e "fonti correlate non richieste".

Risultato: per "Sentenza n. 7919/2026" vengono mostrate le prime 5-12 sentenze che contengono termini simili, nessuna delle quali è necessariamente la 7919.

---

## 5. Perché confidence diventa media anche se manca testo integrale/dispositivo

In `lex/formatting/answer_builder.py`, la confidence viene calcolata su:
- numero di evidenze
- presenza di fonti ufficiali
- freshness score
- post-guard risk

Non considera se il testo integrale o il dispositivo della sentenza specifica è effettivamente nelle evidenze. Quindi: 3 sentenze correlate → confidence media (0.6-0.7) anche se nessuna è la sentenza richiesta e nessuna ha il testo integrale.

---

## 6. Perché il cliente presente nello studio può non essere letto

Cinque cause distinte:

1. **Keyword mismatch**: la sezione "Clienti" si attiva solo se la domanda contiene "cliente/assistito/anagrafica". "dammi i dati di Mario Rossi" → nessun trigger → sezione non caricata.
2. **Limite 4 risultati**: `_clienti_lines` ritorna max 4 clienti, testo ridotto a nome+stato.
3. **Cache stale**: TTL 90s — se i dati del cliente sono stati modificati di recente, la cache restituisce dati vecchi.
4. **Testo fonte insufficiente**: il campo `text` nella source è solo "Tipo: X. Stato: Y. Referente: Z." — mancano email, PEC, CF, fascicoli, note.
5. **No entity extraction**: la domanda non viene analizzata per estrarre nome proprio, CF, PIVA, email → la ricerca `gestore.cerca(question)` può non trovare il cliente se la domanda ha molte parole estranee.

---

## 7. Sezioni del contesto studio caricate

Le sezioni vengono selezionate da `_select_detail_sections_for_chat()` (chat mode) o `_select_detail_sections()` (default), massimo 4-5 sezioni per richiesta:

| Sezione | TTL cache | Contenuto |
|---------|-----------|-----------|
| Fascicoli | 90s | Titolo, RG, tribunale, oggetto — massimo 4 |
| Clienti | 90s | Nome, stato, referente — massimo 4 |
| Agenda | 60s | Appuntamenti prossimi 21 giorni — massimo 4 |
| Scadenziario | 60s | Scadenze imminenti — massimo 4 |
| Fatturazione | 120s | Parcelle recenti — massimo 4 |
| Template atti | 120s | Template disponibili — massimo 4 |
| Tariffario | 300s | Scaglioni DM 55 |
| Ricerca legale | 180s | Motori ricerca legale |
| Archivio sentenze | 120s | Sentenze indicizzate localmente |

---

## 8. Limiti di `_clienti_lines`

```python
def _clienti_lines(question: str) -> tuple[list[str], list[dict[str, Any]]]:
    gestore = get_clienti()
    all_rows = gestore.tutti()
    stats = gestore.statistiche()
    matches = gestore.cerca(question) if _clean_spaces(question) else []
    selected = matches[:4] if matches else all_rows[:4]      # ← MAX 4
    sources = [_source(...)  for row in selected]           # ← solo nome+stato+referente
```

Limiti:
- Ritorna massimo 4 clienti
- Non include email, PEC, CF, PIVA, telefono, indirizzo
- Non include fascicoli collegati
- Non include documenti, note, tag
- Non fa entity extraction prima di chiamare `gestore.cerca()`
- Se `question` ha molte parole inutili, `cerca()` può non trovare il match

---

## 9. Limiti di `_select_detail_sections`

```python
def _select_detail_sections(question: str) -> set[str]:
    # Punteggio per keyword → top 5 sezioni
    return set(selected[:5])
```

Limiti:
- Nessuna entity extraction (nomi propri, CF, PIVA non triggerano sezioni)
- Massimo 5 sezioni → può scartare sezioni rilevanti se competono con altre
- Non distingue tra "cliente con dati anagrafici" e "cliente nel contesto di un fascicolo"
- Nessun meccanismo di force-include per intent specifici

---

## 10. Limiti di `_should_force_web_fallback`

```python
if _has_specific_local_context(local_sources):
    return False          # ← blocca web se c'è QUALSIASI fonte locale specifica
```

Limiti critici:
- Blocca ricerca web anche per `giurisprudenza_specifica` se c'è un fascicolo in contesto
- Non distingue exact reference (sentenza specifica) da query generica
- Non considera il workflow corrente (giurisprudenza_specifica dovrebbe sempre usare web)
- Nessun parametro `exact_reference` o `force_public_web`

---

## 11. Limiti di `official_web.search_recognized_official_web`

In `lex/retrieval/official_web.py`:
- Usa DuckDuckGo come motore di ricerca su domini allowlisted
- Non ha query optimizer per sentenze specifiche (no "site:cortedicassazione.it N. XXXX")
- Non fa exact match verification sui risultati: restituisce i primi N risultati per query semantica
- Nessun filtro per numero/anno sentenza
- Non distingue tra "trovato documento esatto" e "trovato documento correlato"
- Cache TTL 900s — query per "Sentenza 7919/2026" può restituire risultati cached per query diverse

---

## 12. Cosa va corretto (piano di azione)

| Problema | Soluzione | Fase |
|----------|-----------|------|
| Sentenza specifica non forza web | `case_law_reference_parser.py` + `exact_legal_reference_guard.py` | 4, 5 |
| `_has_specific_local_context` blocca web per sentenze specifiche | Modifica `_should_force_web_fallback` per bypassare se exact reference | 6 |
| Clienti non letti (keyword mismatch) | Entity extraction + intent `cliente_anagrafica` | 9, 10 |
| Max 4 clienti con dati ridotti | `studio_data_gateway.py` con dati completi | 8 |
| Risultati correlati presentati come fonte | `exact_legal_reference_guard.py` filtro post-retrieval | 5 |
| Confidence media senza testo integrale | Confidence cap in `exact_legal_reference_guard.py` | 5 |
| Nessuna classificazione public/private scope | `source_scope_policy.py` | 2 |
| Debug insufficiente | Aggiornamento `debug_payload_builder.py` | 12 |
