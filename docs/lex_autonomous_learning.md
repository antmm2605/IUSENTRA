# Lex — Ciclo di apprendimento autonomo governato

Aggiornato: 2026-07-02.

## Cos'è

Lex non aspetta solo input umano: quando analizza testi legali capisce **cosa non sa**,
trasforma le lacune in domande di ricerca, cerca fonti **ufficiali**, ne valuta
l'affidabilità, legge i documenti ammessi, estrae citazioni e concetti, aggiorna una
memoria locale ispezionabile e **propone** miglioramenti verificabili. È la base
dell'"autonomia governata": Lex impara e propone da sola, ma non inventa diritto, non
scrive codice e non tocca la produzione senza revisione umana.

Tutta la fondazione è **deterministica** (nessun LLM): regex, cataloghi versionati,
policy fonti governate. Ogni output è tracciabile alle sue evidenze (record della memoria).

## Il ciclo

```
non so abbastanza su un tema
→ formulo una domanda di ricerca          (gap_detector + research_planner)
→ genero query verso fonti ufficiali      (query_builder: site: dai tier governati)
→ cerco fonti                             (discovery: provider offline o web governato)
→ valuto se sono affidabili               (lex/sources/trust + Source Policy System)
→ leggo il contenuto con cortesia         (PoliteFetcher: robots.txt + rate-limit)
→ estraggo norme, citazioni e concetti    (lex/learning: estrattore pct + estensione UE/GDPR)
→ aggiorno memoria e grafo dei concetti   (lex/knowledge: JSONL + concept_graph)
→ misuro cosa ho imparato                 (lex/evaluation/learning_metrics)
→ propongo miglioramenti verificabili     (improvement_proposer, SEMPRE in revisione umana)
→ riparto, finché una stop condition non ferma il ciclo
```

Stop conditions (la prima vince): `max_cycles`, `max_queries`, `max_sources`,
`max_runtime_seconds`, `no_new_information` (il ciclo non ha appreso nulla di nuovo).
Nessun loop infinito: i limiti hanno tetti rigidi non aggirabili
(`lex/autonomy/safety.py::HARD_LIMITS`) e valori oltre soglia sono un errore di
configurazione, mai un clamp silenzioso.

## Autonomia ammessa e vietata

Ammessa: formulare query; cercare su fonti ufficiali; leggere pagine pubbliche;
analizzare documenti; aggiornare la memoria locale; generare nuove domande; proporre
miglioramenti; produrre report; dichiarare cosa manca.

Vietata (invarianti in `lex/autonomy/safety.py`): auto-deploy; modifiche a codice o
produzione; commit/push/PR; credenziali; bypass di paywall o robots.txt; scraping
aggressivo; blog/forum/social come fonti autoritative; inventare norme o sentenze;
consulenza legale definitiva senza fonti; dati personali nei test; LLM esterni in
questa fondazione. L'unica funzione di "applicazione" esposta (`refuse_apply`) solleva
SEMPRE `AutonomyViolation`: le `ImprovementProposal` si applicano solo a mano.

**Apprendimento ≠ consulenza legale**: il ciclo costruisce conoscenza interna con
evidenze; le risposte agli utenti restano governate dai workflow Lex esistenti
(guardie, contratti di risposta, astensione).

## Architettura (riuso, non duplicazione)

| Package | Ruolo | Riusa |
|---|---|---|
| `lex/learning/` | citazioni + termini + profilo linguistico | `pct/legal_reference_extractor` (estrattore di produzione) + estensione GDPR/atti nominati locale |
| `lex/knowledge/` | memoria JSONL, grafo concetti, ontologia seed | — (nuovo, dati ispezionabili) |
| `lex/sources/` (esteso) | `polite_fetcher` (robots+rate-limit), `trust` | `OfficialSourceHttpClient`, `extractors`, Source Policy System, registro fonti |
| `lex/evaluation/` (esteso) | `learning_metrics` | pesi/soglie del Source Policy System |
| `lex/autonomy/` | gap → domande → query → ciclo → proposte + safety | `pct/legal_context_questions`, `case_law_reference_parser`, `official_web` (ricerca governata, import pigro) |

## Memoria locale (ispezionabile a mano)

Default runtime: `{PCT_DATA_ROOT|IUSENTRA_DATA_DIR}/intelligence/lex_memory/`;
in locale `--memory-dir data/lex_memory` (gitignorata). File JSONL append-only con
dedup per `record_id` (`schema_version` per collezione):
`legal_terms`, `citations`, `source_readings`, `source_profiles`, `unknown_concepts`,
`research_questions`, `learning_signals`, `improvement_proposals`, `trust_assessments`
+ `concept_graph.json` (nodi/archi ordinati, salvataggio byte-stabile) +
`cycle_reports/cycle_<n>.json`.

## Come eseguire il ciclo offline (zero rete)

```bash
python scripts/lex_autonomous_cycle.py \
  --config examples/lex_autonomous_config.json \
  --samples examples/legal_samples.json \
  --memory-dir data/lex_memory --report text
```

Exit code: 0 successo · 1 configurazione/input · 2 errore fonti · 3 errore ciclo.
`--dry-run` esegue senza scrivere nulla. In offline il provider è
`StaticSearchProvider` sui risultati precotti `offline_results` del config
(estratti didattici di fonti ufficiali): nessuna chiamata di rete, mai.

## Come abilitare la modalità web (default OFF)

**Verificata in produzione il 2026-07-04** (workflow "Lex ciclo web" run #1 sul container
Hetzner): 10 fonti ufficiali lette in fase di ricerca governata + 10/11 letture dirette
seminate (Cartabia, GU, Cassazione, Consulta, G.A., EUR-Lex/GDPR, Garante, Agenzia
Entrate, INPS), 548 citazioni e 488 termini in memoria, 0 violazioni di policy.
Report completo: `docs/reports/lex_web_cycle_2026-07.md`.

Nel config: `"mode": "web"`, `"allow_web": true` e una `allowlist` di domini non
vuota; `politeness.min_interval_seconds >= 1.0` e `respect_robots: true` sono
obbligatori. La ricerca passa dal motore governato esistente
(`lex/retrieval/official_web`: allowlist + guardia SSRF) e ogni fetch dal
`PoliteFetcher`. Le query nascono SOLO da campi strutturati (norma normalizzata,
termine, area): mai dal testo libero dei campioni, quindi niente PII per costruzione.

## Proposte di miglioramento (P1-P5)

`improvement_proposer` genera proposte con evidenze, modulo bersaglio e test
suggerito — mai applicate in automatico: P1 pattern di citazione non riconosciuto;
P2 dominio ufficiale fuori dai tier dell'area; P3 keyword d'area mancanti;
P4 concetto ricorrente da aggiungere all'ontologia; P5 dominio tier_1 bloccato da
robots.txt (serve un connettore dedicato). L'upstreaming dell'estensione GDPR dentro
`pct/legal_reference_extractor.py` è esso stesso una proposta tracciata (il modulo pct
serve il presidio PEC in produzione e si tocca solo con regressioni dedicate).

## Job notturno delegato (default OFF)

Dal 2026-07-04 esiste il job `lex_autonomous_learning_nightly` (cron 02:40):
template registrato nella console Pianificazioni con `enabled=False` — il job
APScheduler nasce **in pausa** e si attiva solo dalla console. Doppia cintura
fail-closed nel runner (`lex/autonomy/nightly.py`): senza riga di registro
abilitata il ciclo NON parte. Quando attivo: modalità web con la config
governata committata, budget notturni prudenti (2 cicli, 10 query, 5 fonti,
240s), memoria durevole in `{PCT_DATA_ROOT}/intelligence/lex_memory` che si
accumula notte dopo notte (dedup → convergenza `no_new_information`).

## Prossimi passi (fuori da questa fondazione)

- Feature flag `lex.autonomousLearning` quando nascerà una superficie web.
- Fonti aggiuntive tramite connettori dedicati in `lex/sources/connectors`
  (es. articolo singolo Normattiva oltre l'URN `!vig=`, dettagli sentenze).
