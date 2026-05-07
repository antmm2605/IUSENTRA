# Parte 12A - Report anti-mascheramento React

Generato: 2026-05-07

## Premessa

La migrazione precedente era progressiva: molte route erano renderizzate da
React ma continuavano a delegare il flusso principale a template Flask, link
`?_legacy=1`, `LegacyPostForm` o POST legacy. Da questa tranche il manifest non
puo' piu' dichiarare piena operativita React quando il comportamento reale e'
solo shell, bridge o fallback legacy.

## Route realmente operative React

- Manifest `react_operational_full`: `/utenti/nuovo`.
- Audit tecnico con potenziale operativo pieno ma non promosso in questa
  tranche: `/preventivi`, `/preventivi/nuovo`, `/preventivi/wizard`.
  Restano non sbloccate come full per scelta prudente: la Parte 12A non
  promuove altre route oltre al pilota.

## Route solo shell/bridge

- `react_bridge`: `/profili`, `/studio`, `/amministrazione`, `/backup`,
  `/sito-studio`, `/sito-studio/contatti`, `/fatturazione`,
  `/fatturazione/nuova`, `/incassi-pagamenti`, `/preventivi`,
  `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`,
  `/compensi-forensi`, `/template-atti`, `/template-atti/catalogo`,
  `/redazione-atti`, `/giurisprudenza`, `/legal-intelligence`,
  `/legal-intelligence/news`, `/legal-intelligence/mediazione`,
  `/ricerca-legale`.
- `react_operational_partial`: `/utenti`, `/audit`, `/registro-attivita`,
  `/statistiche`, `/preventivi/wizard`, `/tariffario`.

## Route ancora mascherate

- L'audit rileva 249 link `?_legacy=1`, 14 `LegacyPostForm`, 33 bridge con
  `writes: "legacy_routes"` e 6 API JSON di salvataggio mancanti.
- Le route con legacy primario restano `react_bridge`,
  `react_operational_partial` o `legacy_operational`, non
  `react_operational_full`.

## Route declassate nel manifest

- Tutti gli stati `react_full` sono stati rimossi.
- Le superfici precedentemente presentate come full ma ancora dipendenti da
  legacy sono state riclassificate con status esplicito:
  `react_bridge`, `react_operational_partial` o `legacy_operational`.

## Primo modulo convertito

- `/utenti/nuovo` e' convertito a React operativo reale.
- Il form principale non usa `LegacyPostForm`.
- Il salvataggio usa `apiPostJson` e endpoint JSON same-origin.
- La password non viene salvata in localStorage/sessionStorage e viene svuotata
  dopo submit.

## Endpoint JSON creati

- `POST /api/v1/ui/utenti/nuovo`.
- Protezioni: `_richiedi_auth`, CSRF/sessione, permesso `utenti.scrivi`,
  guard multi-tenant SUPERADMIN, validazione campi, manager utenti esistente,
  audit `utenti.crea`.
- La risposta JSON include `ok`, `message`, `errors` e `item` senza password o
  altri dati sensibili.

## LegacyPostForm rimossi dal flusso principale

- Rimosso da `/utenti/nuovo`.
- Gli altri `LegacyPostForm` restano censiti e non vengono nascosti: sono nel
  report `artifacts/react-migration/anti-mascheramento-audit.md`.

## Link `?_legacy=1` rimasti

- Restano come rollback tecnici o per route non ancora operative.
- Non sono CTA primarie per `/utenti/nuovo`.
- Ogni presenza e' tracciata nell'audit anti-mascheramento.

## Rischi residui

- Molte superfici React sono ancora bridge/shell e richiedono API JSON dedicate
  prima di ulteriori promozioni.
- I report 10A e le modifiche runtime gia presenti nella working tree restano
  fuori dallo scope della Parte 12A salvo file condivisi necessari ai gate.
- I dati runtime locali modificati dai test non devono essere confusi con il
  perimetro della release.

## Prossimo modulo consigliato

- `/profili`, per vicinanza funzionale a utenti e rischio medio/basso.
- Alternativa successiva: `/backup`, solo dopo definizione precisa delle API
  amministrative e delle policy di sicurezza.

## Test eseguiti

- `node scripts/react-migration/audit-anti-mascheramento.mjs`
- `node scripts/react-migration/check-no-fake-react-full.mjs`
- `node scripts/react-migration/check-anti-mascheramento-pilot.mjs`
- `python -m pytest tests/test_react_shell.py::test_react_api_utenti_nuovo_crea_utente_json_senza_password tests/test_react_shell.py::test_react_api_utenti_nuovo_valida_campi_e_permesso -q`
- `cd frontend && npm run test`
- `cd frontend && npm run typecheck`
- `cd frontend && npm run build`

## Rollback

- Ripristinare i file toccati dalla Parte 12A dal commit precedente.
- Il fallback tecnico `/utenti/nuovo?_legacy=1` resta disponibile per ripristino
  immediato del percorso legacy durante verifica o incidente.
- Non cancellare template legacy in questa fase.
