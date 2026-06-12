# LEX — Tool Registry (v2.200.0)

Registro dei 25+ tool disponibili in `lex/tools/legal_studio_tools.py`.

Il registry runtime `lex/tools/registry.py` espone anche il tool governato
`operational_knowledge`, attivo di default e disattivabile solo con
`LEX_OPERATIONAL_KNOWLEDGE_ENABLED=0`. Questo tool non sostituisce i tool
storici: li completa con un layer unico tenant-aware, RBAC-aware e auditabile
per interrogare dati reali dello studio.

## Aggiornamento 2.245.64 - Template Atti da Lex

Il workflow `atto_da_template` non è redazione libera: è un percorso deterministico che usa il catalogo atti reale e il compilatore esistente. Lex può cercare modelli, precompilare un payload, validare i campi e proporre azioni, ma la scrittura nell'editor professionale resta una mutation confermata.

Servizio applicativo: `pct.template_atti_lex_service`.

Funzioni esposte:

- `resolve_template_for_query(query, context)`;
- `resolve_act_context(tenant_id, user_id, client_id, fascicolo_id, query)`;
- `build_prefill(model_code, fascicolo, cliente, utente, config, parti)`;
- `validate_template_payload(model_code, payload)`;
- `render_template_act(model_code, payload)`;
- `create_editor_draft(model_code, payload, fascicolo_id, user_id)`.

Azioni strutturate ammesse: `open_template_catalog`, `open_template_compiler`, `complete_missing_fields`, `create_editor_draft`, `open_created_document`, `open_case`, `open_client`. `create_editor_draft` richiede conferma, salvo comando esplicito dell'avvocato.

## Aggiornamento 2.245.33 - Registro governato Lex

La Fase 4 porta dentro Lex il pattern Tool Registry richiesto: non basta più
avere un dizionario di oggetti Python. Ogni strumento è ora accompagnato da un
descrittore deterministico con:

- schema `iusentra.lex_tool_registry.v1`;
- categoria funzionale (`fascicolo`, `fonti_pubbliche`, `redazione`, `studio`,
  `telematico`, `economico`, `governance`);
- livello di accesso `read_only` oppure `write`;
- trasporto applicativo `in_process`;
- permessi richiesti;
- flag `mutates_state`;
- flag `allowed_in_free_web`;
- descrizione operativa.

La compatibilità resta invariata: `LexToolRegistry().tools["nome_tool"]`
continua a funzionare. In più sono disponibili:

- `list_tools()` per inventario governato;
- `descriptor(tool_name)` per leggere la scheda di uno strumento;
- `validate_tool_call(...)` per verificare modalità, permessi e scrittura;
- `run_tool(...)` per eseguire solo dopo validazione.

Regola web libero: la chat dell'avvocato non viene bloccata da allowlist
ufficiali quando il flag web libero è attivo. Il registro strumenti impedisce
solo che strumenti riservati dello studio, come fascicoli e documenti interni,
vengano trattati come strumenti web pubblici. Gli strumenti su fonti pubbliche
(`giurisprudenza`, `legal_intelligence`) restano utilizzabili in modalità web
libero.

Regola scrittura: strumenti come `generate_editor_draft`,
`propose_editor_edits` ed `export_editor_document` sono marcati come `write` e
`mutates_state=true`; non possono essere eseguiti da una chiamata generica
senza canale applicativo autorizzato. Questo mantiene il comportamento richiesto
per l'editor professionale: Lex prepara bozze e modifiche nel flusso corretto,
non produce atti lunghi e non tracciati in chat.

## Dispatcher

```python
from lex.tools.legal_studio_tools import dispatch_tool, list_tools

# Lista tutti i tool disponibili
tools = list_tools()

# Esegui un tool per nome
result = dispatch_tool("calculate_tariffario", valore_causa=50000, fasi=["studio", "istr", "dec"])
```

## Tool per categoria

### Tariffario forense (DM 55/2014)

| Tool | Parametri | Output |
|------|-----------|--------|
| `calculate_tariffario` | `valore_causa`, `fasi`, `riduzione_pct`, `aumento_pct` | scaglione, totale, rimborso 15% |
| `list_scaglioni` | — | tabella 8 scaglioni con range e importi medi |
| `list_fasi` | — | lista fasi (studio, intro, istr, dec) con descrizione |

### Termini processuali

| Tool | Parametri | Output |
|------|-----------|--------|
| `calculate_deadline` | `tipo_termine`, `data_decorrenza`, `giorni_personalizzati` | scadenza ISO, giorni restanti, flag urgente |
| `list_termini` | — | 16 tipi termine con norma e giorni |
| `check_feriale_agosto` | `data_iso` | bool: la data cade nel periodo feriale agosto |

### Deposito telematico

| Tool | Parametri | Output |
|------|-----------|--------|
| `build_deposito_checklist` | `portale` (PST/PDP/PAT/PTT) | checklist markdown con normativa |
| `diagnosi_errore_pst` | `messaggio_errore` | diagnosi + soluzione |
| `get_portale_info` | `portale` | URL, autenticazione, normativa |

### Fascicolo e documenti

| Tool | Parametri | Output |
|------|-----------|--------|
| `get_fascicolo_summary` | `fascicolo_id` | riepilogo strutturato fascicolo |
| `list_scadenze_fascicolo` | `fascicolo_id` | scadenze ordinate per urgenza |
| `search_fascicoli` | `query`, `limite` | lista fascicoli corrispondenti |

### Giurisprudenza e normativa

| Tool | Parametri | Output |
|------|-----------|--------|
| `search_giurisprudenza` | `query`, `limite` | sentenze rilevanti |
| `get_normativa` | `articolo`, `codice` | testo normativo |
| `get_massima` | `numero_sentenza` | massima + riferimento |

### Redazione

| Tool | Parametri | Output |
|------|-----------|--------|
| `build_diffida_template` | `context` | bozza diffida messa in mora |
| `build_sollecito_template` | `context` | bozza sollecito pagamento |
| `build_pec_template` | `context` | bozza PEC formale |
| `build_lettera_template` | `context` | bozza lettera al cliente |
| `build_contestazione_template` | `context` | bozza contestazione fattura |

### Studio e agenda

| Tool | Parametri | Output |
|------|-----------|--------|
| `get_agenda_oggi` | — | appuntamenti del giorno |
| `get_prossime_scadenze` | `giorni` | scadenze nei prossimi N giorni |
| `get_statistiche_studio` | — | statistiche generali studio |

### Operational Knowledge

| Tool | Parametri | Output |
|------|-----------|--------|
| `operational_knowledge` | `question`, `user`, `studio`, `tenant_id`, `metadata` | risposta deterministica con fonti interne, oggetti letti, confidence, coverage gap, permessi applicati e audit event |

Sorgenti operative coperte dal layer:

- clienti, soggetti e fascicoli;
- agenda e scadenziario;
- preventivi, conferimenti, tariffario, parcelle/fatturazione e timesheet;
- documenti fascicolo e document intelligence;
- messaggi, PEC/email e notifiche;
- portali/telematico in sola lettura;
- template atti;
- legal intelligence, update intelligence e Legal Source Engine.

Regole:

- nessun web per dati cliente/studio;
- nessun path filesystem, segreto o dato di tenant diverso in output;
- risposta con fonti e coverage gap;
- blocco delle azioni dispositive come invio PEC, deposito, firma, pagamento o cancellazione.

## Scaglioni DM 55/2014

| Scaglione | Da | A | Fase studio | Fase intro | Fase istr | Fase dec |
|-----------|-----|---|-------------|------------|-----------|---------|
| 1 | 0 | 1.100 | 270 | 170 | 340 | 340 |
| 2 | 1.101 | 5.200 | 630 | 400 | 790 | 790 |
| 3 | 5.201 | 26.000 | 1.080 | 670 | 1.350 | 1.350 |
| 4 | 26.001 | 52.000 | 2.430 | 1.530 | 3.020 | 3.020 |
| 5 | 52.001 | 260.000 | 4.000 | 2.500 | 5.000 | 5.000 |
| 6 | 260.001 | 520.000 | 6.600 | 4.100 | 8.200 | 8.200 |
| 7 | 520.001 | 2.600.000 | 13.000 | 8.200 | 16.400 | 16.400 |
| 8 | > 2.600.000 | ∞ | 22.000 | 13.500 | 27.000 | 27.000 |

## Termini processuali disponibili (16 tipi)

| Tipo | Giorni | Norma |
|------|--------|-------|
| `opposizione_decreto_ingiuntivo` | 40 | art. 641-645 c.p.c. |
| `appello_sentenza_civile` | 30 | art. 325 c.p.c. |
| `appello_breve` | 15 | art. 325 c.p.c. |
| `ricorso_cassazione` | 60 | art. 325 c.p.c. |
| `opposizione_esecuzione` | 20 | art. 617 c.p.c. |
| `reclamo_cautelare` | 15 | art. 669-terdecies c.p.c. |
| `risposta_citazione` | 20 | art. 167 c.p.c. |
| `memoria_ex_183` | 30 | art. 183 c.p.c. |
| `ricorso_tar` | 60 | art. 29 c.p.a. |
| `ricorso_tar_silenzio` | 365 | art. 31 c.p.a. |
| `appello_consiglio_stato` | 30 | art. 92 c.p.a. |
| `impugnazione_penale` | 15 | art. 585 c.p.p. |
| `ricorso_cassazione_penale` | 45 | art. 585 c.p.p. |
| `querela` | 90 | art. 124 c.p. |
| `prescrizione_ordinaria` | 3650 | art. 2946 c.c. |
| `prescrizione_breve` | 1825 | art. 2948-2955 c.c. |


## Tool Procedure Completion Engine

Cinque tool governati (categoria `governance`, transport `in_process`, mai web
libero) collegati a `pct/procedure_completion/` — dettagli in
[PROCEDURE_COMPLETION_ENGINE](PROCEDURE_COMPLETION_ENGINE.md):

| Tool | Permesso RBAC | Output |
|---|---|---|
| `procedure_completion_preview` | `procedure_completion.esegui` | card draft, fonti, gap, confidence |
| `procedure_completion_search` | `procedure_completion.leggi` | schede esistenti con stato e confidence |
| `procedure_completion_explain_article` | `procedure_completion.leggi` | sintesi documentale solo dalle citazioni collegate |
| `procedure_completion_suggest_template` | `procedure_completion.leggi` | template candidates con motivi e gap |
| `procedure_completion_list_gaps` | `procedure_completion.leggi` | coda gap con azioni successive |

Risposte sempre nel contratto governato (`official_sources`, `citations`,
`compared_sources`, `coverage_gaps`, `confidence`, `answer_mode`,
`needs_review`, `next_actions`); con fonti insufficienti il tool risponde
`needs_review` con next actions, mai con contenuti inventati.
