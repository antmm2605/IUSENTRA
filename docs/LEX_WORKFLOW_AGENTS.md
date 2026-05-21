# Lex Workflow Agents / Regia Agentica Studio

## Scopo

Lex Workflow Agents aggiunge a IUSENTRA una regia agentica governata per ridurre il lavoro operativo ripetitivo dello studio. Non è una chat separata: usa Lex, il registry tool esistente, i repository tenant-aware e la coda approvazioni per trasformare letture reali in proposte operative.

La regola centrale è semplice: le letture possono avvenire in preview, ogni scrittura resta ferma finché un umano abilitato non la approva.

## Architettura

- Package backend: `lex/agents`.
- Ricette governate: `lex/agents/recipes`.
- Tool registry: `lex/tools/registry.py`, con adapter mutanti controllati in `lex/tools/workflow_agent_tools.py`.
- Bridge API React: `web/services/react_workflow_agents_bridge.py`.
- Endpoint UI: `/api/v1/ui/workflow-agents`.
- UI React: `frontend/src/pages/workflow-agents`.
- Storage tenant-aware: `WORKFLOW_AGENTS_RUNS_DB`, `WORKFLOW_AGENTS_METRICS_DB`, `WORKFLOW_AGENTS_ACTIONS_DB`.

Il planner non inventa piani liberi: carica solo ricette registrate. L'executor esegue in preview gli step read-only e trasforma gli step mutanti in `AgentProposal`. La fase approve riesegue solo gli step selezionati, dopo RBAC, tenant context, feature flag e audit.

## Workflow disponibili

| Codice | Obiettivo operativo | Scritture possibili solo dopo approvazione |
| --- | --- | --- |
| `triage_giornaliero` | Fascicoli, agenda, scadenze e segnali recenti in ordine di priorità. | Attività operative, promemoria/scadenze. |
| `redazione_atto` | Template, contesto fascicolo, campi mancanti e bozza documento. | Bozza editor/documento. |
| `billing_monthly` | Consuntivo mese, timesheet, voci economiche e parcella in bozza. | Voce timesheet, parcella bozza. |
| `nuovo_incarico` | Apertura pratica, controllo conflitto, cliente potenziale e checklist. | Cliente potenziale, fascicolo iniziale, checklist. |
| `predeposito` | Verifica atto principale, allegati, checklist e ricevute disponibili. | Checklist correttiva, attività anomalie. |
| `legal_research` | Ricerca preliminare su fonti interne/governate e archivio giurisprudenza. | Memo di ricerca in bozza. |

## Feature flag

| Flag | Default | Effetto |
| --- | --- | --- |
| `lex.workflowAgents.enabled` | acceso | Abilita preview read-only e consultazione run. È acceso perché la superficie è governata e non scrive senza approvazione. |
| `lex.workflowAgents.writeActions` | spento | Abilita l'esecuzione delle scritture approvate. In assenza del flag, approve risponde `feature_disabled`. |
| `lex.workflowAgents.scheduledRuns` | spento | Riservato a esecuzioni programmate, oggi non avviate automaticamente. |
| `routes.appV2.workflowAgents.home` | acceso | Espone la pagina Regia Agentica in App V2. |
| `routes.appV2.workflowAgents.reviewQueue` | acceso | Espone dettaglio run e coda approvazioni. |

## API

Tutti gli endpoint vivono sotto `/api/v1/ui/workflow-agents`, usano auth/sessione o API key già governate, e non accettano `tenant_id`, `studio_id`, `user_id`, token o path dal client.

- `GET /api/v1/ui/workflow-agents`: workflow disponibili, stato funzioni, ultimi run e metriche sintetiche.
- `POST /api/v1/ui/workflow-agents/preview`: crea piano, esegue sole letture, salva run e proposte.
- `GET /api/v1/ui/workflow-agents/runs/<run_id>`: dettaglio tenant-safe del run.
- `GET /api/v1/ui/workflow-agents/approvals`: proposte in attesa.
- `POST /api/v1/ui/workflow-agents/runs/<run_id>/approve`: esegue solo step approvati, se il flag scritture è attivo.
- `POST /api/v1/ui/workflow-agents/runs/<run_id>/reject`: rifiuta proposte e aggiorna metriche.
- `GET /api/v1/ui/workflow-agents/metrics`: KPI aggregati.

## Sicurezza

Presidi applicati:

- tenant isolation fail-closed tramite `tenant_data_path` e scope server-side;
- RBAC con permessi reali (`agenda.scrivi`, `scadenziario.scrivi`, `fascicoli.scrivi`, `clienti.scrivi`, `fatturazione.scrivi`, `messaggi.scrivi`, `telematico.valida`, `ai.usa`, `legal_skills.*`);
- nessun parametro di controllo accettato dal client;
- nessun path filesystem, token, email, PEC, IBAN o codice fiscale nei payload pubblici/audit;
- nessuna PEC inviata, nessun deposito, nessuna firma e nessuna cancellazione automatica;
- provider esterni vietati per dati fascicolo/cliente nelle ricette agentiche.

## Approval queue

Gli step con `mutates_state=True` diventano `AgentProposal`. La UI mostra titolo, impatto, rischio e dettaglio run. L'approvazione richiede:

1. utente o API key autorizzata;
2. permesso `legal_skills.approva`;
3. permessi specifici del tool mutante;
4. `lex.workflowAgents.writeActions=true`;
5. contesto studio valido.

## Metriche 80%

Ogni run salva una metrica calcolata, non forzata:

```text
saving_percentage = ((baseline_minutes - review_minutes - correction_minutes) / baseline_minutes) * 100
```

`target_80_met` è vero solo quando la percentuale è almeno `80`. I test coprono sia il caso `100, 15, 5 => 80%` sia `100, 30, 10 => 60%`.

## Cosa l'agente non può fare

- inviare PEC;
- depositare atti;
- firmare digitalmente;
- cancellare fascicoli, clienti o documenti;
- modificare utenti, ruoli o permessi;
- esportare documenti sensibili verso provider esterni;
- usare dati cliente/fascicolo in ricerca web libera.

## Comandi test

```powershell
python -m pytest -q tests/test_lex_workflow_agents_models.py
python -m pytest -q tests/test_lex_workflow_agents_planner.py
python -m pytest -q tests/test_lex_workflow_agents_executor.py
python -m pytest -q tests/test_lex_workflow_agents_policies.py
python -m pytest -q tests/test_lex_workflow_agents_api.py
python -m pytest -q tests/test_lex_workflow_agents_metrics.py
python -m pytest -q tests/test_lex_workflow_agents_security.py
```

