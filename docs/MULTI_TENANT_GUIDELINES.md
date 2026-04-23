# Multi-tenant Guidelines

## Obiettivo
Scalare più studi senza contaminazione dati.

## Principi
- isolamento dati per tenant
- config per tenant
- audit per tenant
- chiavi e secret separabili
- metriche segmentabili

## Minimo richiesto
- `tenant_id` propagato nei log e negli eventi
- configurazioni non globali dove evitabile
- storage chiaramente attribuibile al tenant

## Errori da evitare
- fallback su tenant implicito
- condivisione cache non scoped
- path disco condivisi senza namespace
