# Observability e log

Aggiornato: 2026-05-14, fase 12 `fasereact`.

## Eventi da osservare

| Evento | Quando | Dato ammesso | Dato vietato |
| --- | --- | --- | --- |
| `policy_denied` | RBAC, feature flag, backend security | categoria, risorsa, ruolo, request id | password, token, payload completo, documenti |
| `feature_flag_denied` | route/App V2 con flag spento | flag, path, tenant corrente redatto | token, query sensibile |
| `feature_flag_toggled` | cambio flag da funzione governata | flag, vecchio/nuovo valore, attore | segreti env |
| `cross_tenant_denied` | tentativo o mismatch tenant | tenant corrente redatto, tipo risorsa | identificativi altro tenant se non necessari |
| `access_log` | richieste HTTP | metodo, path, status, durata, request id | body, allegati, segreti |
| `audit` | azioni sensibili | utente, tenant, azione, hash/proof se previsto | password, private key, token |
| `error` | eccezioni controllate | request id, modulo, codice errore | stack trace visibile utente, PII non necessaria |

## Metriche rollout

Da monitorare durante ogni rollout App V2:

- `/api/pronto` 200 e versione attesa;
- error rate 4xx/5xx per endpoint App V2;
- p95 bootstrap React e API P0/P1;
- conteggio `policy_denied`, `feature_flag_denied`, `cross_tenant_denied`;
- 401/403/404 rispetto al ruolo atteso;
- errori frontend console su pagine rappresentative;
- smoke post-deploy security/routing/workflows.

Non esiste in questa fase una dashboard unica obbligatoria nel repository: le metriche sopra sono da collegare al sistema di osservabilita disponibile nell'ambiente.

## Log e PII

Non loggare:

- password, token, API key, private key, PIN o segreti provider;
- contenuto integrale di documenti, PEC, allegati o atti;
- codici fiscali, IBAN, dati sanitari o dati cliente non necessari;
- path filesystem interni quando il messaggio e' visibile all'utente;
- payload JSON completi di form amministrativi o impostazioni.

Preferire:

- `request_id` o correlation id se disponibile;
- codice errore controllato;
- identificativo risorsa redatto o hash;
- ruolo/permesso richiesto;
- tenant corrente senza esporre dati di altri tenant.

## Durante incidente

Raccogliere:

- commit SHA e versione `/api/pronto`;
- workflow run o comando locale;
- base URL e ambiente;
- path/endpoint impattato;
- request id;
- stato feature flag;
- ruolo e permesso atteso;
- tenant impattato in forma redatta;
- log container pertinenti senza dati sensibili.

## Collegamenti

- [SECURITY](../SECURITY.md)
- [ci-cd-gates](ci-cd-gates.md)
- [release-rollout](release-rollout.md)
- [risk-register](risk-register.md)
