# Fase 1 — Audit del Registro di verità delle capability

**Data:** 23/08/2026 — Europe/Rome
**Release candidata:** `2.278.67`
**Stato al momento del commit:** accettazione locale della Fase 1 completata; push gemello e deploy Hetzner da eseguire sul medesimo commit prima dell'avvio della Fase 2.

## Esito e confine esatto

È stato introdotto il registro di verità del prodotto, accessibile in **Amministrazione → Prontezza prodotto**, senza presentare come funzionante alcun flusso P0 non ancora provato materialmente.

Il catalogo contiene esattamente 17 capability P0: autenticazione e cambio studio, apertura cliente, conflitto, preventivo, incarico, fascicolo, attività, documenti e lettore, PEC, scadenze, deposito telematico, ricevute, fattura, pagamento, portale cliente, audit e chiusura fascicolo. Tutte risultano correttamente `Da verificare`: 0/17 verificate e 17/17 da verificare. L'evidenza mostrata nel dettaglio distingue CI, browser e provider; nessuna prova assente viene convertita in esito positivo.

Questo è un risultato della Fase 1, non la certificazione delle 17 operazioni. La loro prova guidata e la promozione controllata restano oggetto delle fasi successive.

## Architettura e sicurezza

- Fonte unica, in sola lettura: `pct/capability_truth_registry.py`; nessuna scansione runtime, chiamata provider, segreto o scrittura su tenant.
- API JSON: `GET /api/v1/react/amministrazione/prontezza-prodotto`, autenticata e protetta dal permesso `utenti.leggi`; errore controllato per sessione o permesso mancanti.
- UI: pagina React `AmministrazionePage`, tab `prontezza-prodotto`, stati loading/errore/vuoto e dettagli espandibili. Il client della nuova API è isolato in `frontend/src/productReadinessData.ts` per non superare il limite di dimensione del client amministrativo esistente.
- Dati, SQLite e PostgreSQL: non applicabili. La Fase 1 non crea né modifica dati strutturati, tabelle, indici, mirror JSON o repository tenant.
- Versionamento: `2.278.67` sincronizzato in pacchetti, Docker, Railway, frontend e OpenAPI.

## Controlli automatici eseguiti

| Controllo | Esito |
| --- | --- |
| `py -3.12 -m pytest tests/test_capability_truth_registry.py tests/test_product_readiness_react_api.py -q` | PASS — 6 test |
| `py -3.12 -m pytest tests/test_security_redaction.py tests/test_product_governance_surface.py -q` | PASS — 6 test |
| `npm --prefix frontend run typecheck` | PASS |
| `npm --prefix frontend run build` | PASS |
| `python scripts/validate_openapi.py` | PASS |
| `python scripts/verify_openapi_provider.py` | PASS — auth-error=311, public-safe=15, success=29, backend-security=1 |
| `python scripts/react-migration/generate_capability_truth_registry.py --check` | PASS |
| `python scripts/react-migration/generate_app_v2_test_docs.py` e `pytest tests/test_app_v2_test_plan_phase10.py -q` | PASS — 3 test |
| `python tools/sync_packaging_files.py --check` | PASS |
| `py -3.12 -m pytest tests/test_utf8_integrity.py -q` | PASS — 4 test |
| `git diff --check` | PASS |

Il gate di qualità per UI/codice ha segnalato prima del commit un conflitto di perimetro, non un difetto del prodotto: la sua regola vieta modifiche ai file di versione richiesti dalla release (`Dockerfile`, `pct/__init__.py`, `railway.toml`, `setup.py`) e classifica il solo incremento versione in `setup.py` come dipendenza runtime. Il conflitto è registrato apertamente; i controlli funzionali e di sicurezza elencati sopra sono quelli applicabili alla modifica. Dopo il commit il gate verrà rieseguito sul worktree pulito.

## Prova reale locale e verifica visiva

La copia reale Docker `http://127.0.0.1:8080` è stata ricostruita senza cache, ricreando `iusentra-app`, `iusentra-ocr` e `iusentra-scheduler`; tutti i container necessari erano healthy. `/api/pronto` ha restituito `ok`, fuso `Europe/Rome` e versione `2.278.67`.

Nel browser reale integrato, con sessione autenticata di Amministratore Studio, sono state svolte azioni materiali:

1. apertura di **Amministrazione**, scroll fino al collegamento e click reale su **Apri prontezza prodotto**;
2. attesa del caricamento e controllo del titolo, delle tre metriche (`17`, `0`, `17`) e dei 17 dettagli;
3. verifica che la data visibile sia italiana (`23/08/2026 17:00`) e che non compaiano stringhe ISO raw;
4. click reale sul primo dettaglio, verifica di rotta, evidenza browser mancante e stato `Da verificare`;
5. passaggio reale del mouse e focus tramite tastiera Tab sul controllo espandibile;
6. scroll dall'inizio alla fine della pagina desktop, senza overflow orizzontale e con l'ultima card `Chiusura fascicolo` leggibile;
7. ripetizione materiale su tablet `768×1024` e mobile `390×844`, con 17 dettagli, assenza di overflow e card finali leggibili.

La prova è stata ripetuta dopo la ricostruzione Docker senza cache che include anche la correzione del redattore JSON; al termine il viewport è stato ripristinato alla vista desktop.

È stato inoltre corretto durante la fase un timestamp ISO precedentemente visibile nel pannello contratti: ora passa dall'helper condiviso `formatDateTimeIt`; un test statico anti-regressione ne protegge l'uso.

Il gate ha inoltre individuato e la fase ha corretto una redazione JSON eccessiva: lo slug tenant lecito `studio-sqlite` veniva oscurato solo perché conteneva la parola `sqlite`. La redazione continua a bloccare i dettagli di errore SQLite (`sqlite3.OperationalError`), ma conserva gli identificativi funzionali; il controllo è protetto in `tests/test_security_redaction.py` e dalla prova della superficie governance.

## Prestazioni e non-regressione

Il controllo finale a caldo `python tools/performance_smoke.py --strict --repeat 5` sulla copia Docker reale ha superato tutte le soglie. Un primo campione immediatamente dopo la ricostruzione senza cache ha avuto mediana di avvio `2172,76 ms`; è stato trattato come possibile regressione, non ignorato, e una seconda campagna di cinque rilevazioni ha stabilizzato il valore a `1588,95 ms`. Il secondo campione è l'evidenza di confronto perché elimina l'effetto di inizializzazione post-ricreazione; tutte le cinque richieste hanno restituito HTTP 200.

| Metrica | Baseline Fase 0 | Fase 1 finale | Valutazione |
| --- | ---: | ---: | --- |
| Avvio mediano | 1894,72 ms | 1588,95 ms | miglioramento di 305,77 ms |
| Login mediano | 9,34 ms | 9,65 ms | variazione di 0,31 ms, entro la variabilità del probe |
| Health mediano | 0,82 ms | 0,78 ms | miglioramento di 0,04 ms |
| Metriche runtime mediana | 80,85 ms | 82,70 ms | variazione di 1,85 ms, entro la variabilità del probe |

Nessuna regressione di soglia è emersa. Il log locale conserva un avviso preesistente di compatibilità del volume host con l'utente applicativo e l'esecuzione esplicita come root nel runtime locale; l'app resta healthy. Non è stato introdotto da questa Fase 1 e richiede un hardening separato, senza falsare l'esito del registro.

## Evidenze generate e rollback

- Dossier generati dalla stessa fonte: `capability-truth-registry.json`, `capability-truth-registry.md`, `capability-truth-release-matrix.md`, `capability-truth-changelog.md`.
- Test e contratti: `tests/test_capability_truth_registry.py`, `tests/test_product_readiness_react_api.py`.
- Rollback: ripristinare il commit immediatamente precedente alla release; non esistono migrazioni o dati da annullare.
- Incidenti: nessun incidente applicativo aperto dalla Fase 1; il registro espone l'assenza di prove P0 invece di mascherarla.

## Vincoli residui prima della fase successiva

La Fase 2 non può iniziare finché non risultano verificati: commit della release, entrambi i branch remoti allo stesso SHA, deploy Hetzner sullo SHA, singolo container `iusentra-app` healthy, endpoint pubblico `https://app.iusentra.it/api/pronto` coerente e pulizia cache Docker/snapshot remoti.
