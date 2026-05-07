# Tranche 13A - Audit profili e permessi

Generato: 2026-05-07

## Route legacy /profili

- Route pubblica: `/profili`
- Rollback tecnico: `/profili?_legacy=1`
- Stato manifest prima della tranche: `react_bridge`
- Gate React: `/profili` gia' presente tra le route sbloccate, con esclusione delle sottoroute `/profili/*`.

## Handler Flask

- Handler legacy: `web/bootstrap/auth_management_routes.py`, funzione `profili()`.
- Handler override legacy: `web/bootstrap/auth_management_routes.py`, funzione `permessi_utente(id_utente)`.
- Endpoint React GET gia' esistente prima della tranche: `GET /api/v1/ui/profili` in `web/blueprints/api_v1_react.py`.

## Template legacy

- Matrice profili: `web/templates/auth/profili.html`.
- Form override utente: `web/templates/auth/permessi_utente.html`.

## Permessi richiesti

- Lettura `/profili`: `utenti.leggi`.
- Scrittura override `/utenti/<id_utente>/permessi`: `utenti.scrivi`.
- SUPERADMIN viene escluso dalla gestione profili studio e resta gestito dal pannello piattaforma.

## POST legacy esistenti

- `/profili` non espone un POST proprio.
- La scrittura collegata al flusso profili e' `POST /utenti/<id_utente>/permessi`.
- Campi POST legacy:
  - `_csrf_token`
  - `permessi_extra`
  - `permessi_negati`

## Struttura ruoli/profili

- Ruoli reali: `pct.auth.RuoloUtente`.
- Descrizioni: `pct.auth.DESCRIZIONI_RUOLI`.
- Ruoli gestibili nel tenant: tutti i ruoli tranne `SUPERADMIN`.
- Utenti per ruolo: `GestioneUtenti.per_ruolo(ruolo)`.

## Struttura permessi

- Catalogo permessi: `pct.auth.TUTTI_PERMESSI`, tuple `(categoria, chiave, etichetta)`.
- Matrice base: `pct.auth.PERMESSI`, mappa `RuoloUtente -> lista permessi`.
- Permessi effettivi utente: `Utente.ha_permesso()` e `Utente.permessi_effettivi`.

## Override utente

- Campi dati reali:
  - `permessi_extra`
  - `permessi_negati`
  - `ha_override`
- Il template legacy mostra gli utenti con override e rimanda alla pagina dedicata di modifica.
- Il form legacy consente di aggiungere permessi non inclusi nel ruolo e rimuovere permessi inclusi nel ruolo.

## Audit legacy

- Azione audit legacy: `utenti.aggiorna_permessi`.
- Risorsa: `utente`.
- Dettaglio: `extra=[...] negati=[...]`.
- Runtime audit: `GestioneUtenti.registra_evento`.

## API gia' esistenti

- `GET /api/v1/ui/profili` leggeva ruoli, permessi e override reali tramite `web/services/react_profili_bridge.py`.
- Gap iniziale: il bridge dichiarava `writes=legacy_routes` e la UI usava `LegacyPostForm` per ripristini override.

## Gap per react_operational_full

- Aggiungere `POST /api/v1/ui/profili` con sessione, CSRF, permesso `utenti.scrivi`, validazione payload e audit.
- Convertire `react_profili_bridge.py` da descrittivo/read-only a operativo con `writes=json_api`.
- Rimuovere `LegacyPostForm` dal flusso principale React.
- Tenere `/profili?_legacy=1` solo come rollback tecnico, non come CTA primaria.
- Aggiornare `profiliData.ts` per usare `apiPostJson`.
- Aggiornare `ProfiliPage.tsx` con loading, saving, success, error, validation, permission denied, empty state.
- Aggiornare manifest e guardrail anti-mascheramento.
