# Fortificazione Multi-Studio

Questo layer rende l'accesso ai dati di studio fail-closed in modalita multi-tenant: se il runtime non risolve con certezza lo studio della richiesta, l'accesso viene bloccato prima che i repository leggano path globali.

## Regola primaria

In ambiente multi-tenant non esiste accesso a dati operativi senza contesto studio valido.

Sono dati tenant-sensitive clienti, fascicoli, documenti, archivio, agenda, scadenziario, messaggi, PEC, email ordinaria, fatturazione, preventivi, privacy, audit, utenti tenant, backup, ricerca, template, intelligence e telematico.

## PEC audit-grade

La pipeline PEC audit-grade usa esclusivamente path risolti nel tenant corrente. In multi-tenant il database `pec_audit.sqlite`, i riferimenti a `EMAIL_CASELLA_DB`, `FASCICOLI_DB`, `FASCICOLI_DOCS` e `SCADENZIARIO_DB` devono passare da `tenant_data_path(..., require_tenant=True)`.

Le API `/api/pec/*` non accettano override di tenant dal payload, non espongono credenziali IMAP, non restituiscono path assoluti e non serializzano il MIME originale nel JSON. Il MIME originale è scaricabile solo da endpoint autenticato dedicato; ogni fetch, parsing, validazione, quick action e digest produce evento in `pec_audit_log` append-only con hash-chain.

Lex accede alla sorgente `pec_audit` solo con `messaggi.leggi`, vede il controllo strutturato e deve distinguere dato certo, confidence, scadenza operativa automatica e decisione dell'avvocato. Non può inviare, depositare o assumere termini legali conclusivi senza validazione dell'avvocato.

## API key

In single-tenant resta compatibile `PCT_API_KEY`, esposta internamente come `API_KEY`.

In multi-tenant la chiave globale non autorizza accesso ai dati di studio. Le API private devono ricevere una chiave dello studio e uno slug esplicito:

```bash
curl \
  -H "X-API-Key: <studio.api_key>" \
  -H "X-Tenant-Slug: studio-rossi" \
  https://app.iusentra.it/api/v1/clienti
```

`X-Studio-Slug` e' accettato come alias. Se entrambi gli header sono presenti devono coincidere.

La chiave deve combaciare con `StudioLegale.api_key` e lo studio deve essere `ATTIVO` o `TRIAL`. Le chiavi non vengono loggate ne restituite nei payload.

## Sessioni web

Per utenti non `SUPERADMIN`, il tenant in sessione, l'ambito di autenticazione e il `tenant_slug` dell'utente devono essere coerenti. Se manca il contesto o lo studio non coincide, la richiesta viene bloccata o la sessione viene riportata al login.

Il `SUPERADMIN` resta confinato alle superfici piattaforma. Per leggere dati di studio serve un contesto governato di impersonazione o una sessione tenant coerente.

## Path guard

`assert_tenant_data_path()` verifica che ogni path sensibile risolto da `g.data_paths` resti sotto la root dello studio. In multi-tenant i fallback ai path globali dell'app sono bloccati per i repository tenant-sensitive.

## Errori principali

- `authentication_required`: sessione o API key mancante.
- `tenant_context_required`: contesto studio mancante o header tenant incoerenti.
- `global_api_key_not_allowed`: chiave globale usata in multi-tenant.
- `tenant_api_key_invalid`: chiave non corrispondente allo studio.
- `tenant_api_slug_mismatch`: API key valida usata contro uno slug diverso.
- `user_tenant_mismatch`: utente e contesto studio non coincidono.
- `tenant_path_forbidden`: path dati fuori dalla root dello studio.

I payload utente non includono path filesystem, chiavi API o dettagli interni.

## Verifica manuale minima

1. Chiamare `/api/v1/clienti` con `PCT_API_KEY` globale in multi-tenant: deve rispondere `401` o `403`.
2. Chiamare `/api/v1/clienti` con `X-API-Key` dello studio A e `X-Tenant-Slug: studio-a`: deve rispondere con i soli dati dello studio A.
3. Ripetere con chiave dello studio A e `X-Tenant-Slug: studio-b`: deve essere bloccato.
4. Verificare login, logout, healthcheck, asset statici e service worker: devono restare raggiungibili.
5. Forzare un path fuori root tenant in `g.data_paths` in un test: `assert_tenant_data_path()` deve bloccarlo senza esporre path assoluti.
