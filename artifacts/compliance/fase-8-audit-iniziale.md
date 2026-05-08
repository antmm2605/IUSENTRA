# Fase 8 - Audit compliance iniziale

## 1-25. Aree verificate

Tariffario, Preventivi, Conferimenti, Parcelle/Fatture, Documenti, Firma, PDF/A, OCR, Deposito telematico, PST/PolisWeb, PDP, PAT/SIGA, PTT/SIGIT, SIGP, PEC/Comunicazioni, Fascicoli, Agenda/Scadenziario, Lex AI, Legal Intelligence, Template atti, Privacy/Sicurezza, Multi-tenant, Audit log, Permessi, Storage dati.

## Fonti gia presenti

Repository e documentazione citano Normattiva, Gazzetta Ufficiale, Ministero Giustizia/PST, specifiche ministeriali in `docs/specs/ministero/`, Lex source policy e connettori fonti ufficiali.

## Fonti mancanti o da review

Le fonti PAT/SIGA, PTT/SIGIT, SIGP, specifiche PCT applicabili per singola release e GDPR sono registrate come `manual_review_required` quando non esiste connettore o validazione automatica puntuale.

## Controlli implementati

Gate anti-mascheramento React, divieto mock full React, contratti `writes=none` per console read-only, registry fonti ufficiali, report compliance per tariffario/documenti/telematico/Lex/sicurezza.

## Controlli mancanti

Validazione normativa puntuale per ogni deposito, XSD per ogni DatiAtto applicabile, prova PEC reale, test multi-tenant completi su tutti i documenti, verifica tariffario per ogni area/scaglione.

## Fallback e rischi

Fallback non nascosti: route legacy ad alto rischio restano dichiarate. Rischi residui: falsa conformita, fonti non aggiornate, portali non autorizzati, dati sensibili in log, calcoli tariffari parziali.
