# Observability Guidelines

## Obiettivo
Rendere ogni problema ricostruibile e ogni regressione visibile.

## Eventi minimi da tracciare
- login riuscito / fallito
- import fascicolo
- sync PST/PDP/PAT/PTT
- bootstrap Local Signer
- chiamata AI locale
- fallback AI
- export / import repository
- errori critici storage

## Campi raccomandati
- timestamp
- level
- event_name
- request_id
- tenant_id
- user_id
- pratica_id
- module
- outcome
- duration_ms
- error_code
- error_message_minimized

## Regole
- niente segreti nei log
- niente PIN o password
- minimizzare dati cliente
- masking obbligatorio
