# Tranche 27a - Audit Sito Studio

Generato: 2026-05-08

## Route legacy /sito-studio

- Manifest prima tranche: `react_bridge`.
- Shell React esistente: `frontend/src/App.tsx` serve `SitoStudioPage` su `/sito-studio`.
- Data client esistente: `frontend/src/sitoStudioData.ts` leggeva `GET /api/v1/ui/sito-studio`.
- Bridge precedente: `web/services/react_sito_studio_bridge.py` dichiarava `writes=legacy_routes`.
- CTA legacy primaria precedente: builder/dashboard legacy.

## Route legacy /sito-studio/contatti

- Manifest prima tranche: `react_bridge`.
- Shell React esistente: `SitoStudioPage`.
- Data client esistente: `GET /api/v1/ui/sito-studio/contatti`.
- Flusso precedente: record con `LegacyPostForm` verso POST legacy.

## Route legacy /sito-studio/builder

- Manifest: `legacy_operational`.
- Gate: `/sito-studio/*` resta legacy/protetto tranne `/sito-studio/contatti`.
- Builder/editor/pubblicazione avanzata non vengono sbloccati.

## Handler Flask

- `web/blueprints/api_v1_react.py`: endpoint React GET già presenti per dashboard e contatti.
- `web/blueprints/studio_site.py`:
  - `GET /sito-studio/contatti`
  - `POST /sito-studio/contatti/<id>/crea-cliente`
  - `POST /sito-studio/prenotazioni/<id>/approva`
  - `POST /sito-studio/prenotazioni/<id>/rifiuta`

## Template legacy

- `studio_site/contact_submissions.html` per contatti legacy.
- Builder/editor/pubblicazione restano template legacy protetti.

## Permessi richiesti

- Le superfici sito richiedono autenticazione.
- Il runtime legacy usa `site_admin_identity_or_403()` e permesso `admin.configura`.
- Le azioni JSON mantengono sessione, CSRF e permesso backend.

## POST legacy esistenti

- Crea cliente potenziale da richiesta contatto.
- Approva prenotazione e sincronizza agenda secondo flusso legacy.
- Rifiuta prenotazione.

## Campi form legacy

- I POST legacy supportati non richiedono campi form aggiuntivi per crea-cliente/approva/rifiuta.
- Il nuovo JSON accetta solo payload stretti per `cliente_id`/`mode` e `status`.

## Struttura pagina/contenuto sito

- Sito corrente, pagine, articoli, servizi, professionisti, sedi, regole prenotazione, richieste contatto e prenotazioni arrivano da `build_studio_site_dashboard_payload()`.

## Struttura richiesta contatto

- Campi repository: `id`, `full_name`, `email`, `phone`, `subject`, `message`, `privacy_accepted`, `lead_cliente_id`, `created_at`.
- Non esistono campi legacy per stato mutabile, archiviazione, nota interna, assegnazione o fascicolo.

## Struttura prenotazione

- Campi repository: cliente, email, telefono, data/ora richiesta, oggetto, note, sede, stato, agenda event, reviewer e timestamp revisione.
- Stati legacy supportati: `pending`, `approved`, `rejected`.

## Stati richiesta

- Contatto: `nuovo` oppure `cliente_collegato`, derivati da `lead_cliente_id`.
- Prenotazione: `pending`, `approved`, `rejected`.

## Azioni legacy

- Cambia stato contatto: non supportato dal backend legacy.
- Archivia contatto: non supportato dal backend legacy.
- Nota interna contatto: non supportata dal backend legacy.
- Assegna: non supportato dal backend legacy.
- Collega cliente: supportato come crea cliente potenziale o collegamento cliente esistente.
- Collega fascicolo: non supportato dal backend legacy.
- Pubblica/builder: legacy protetto, non sbloccato.

## Audit legacy

- `sito_studio.crea_lead_cliente`.
- `sito_studio.collega_cliente`.
- `sito_studio.approva_prenotazione`.
- `sito_studio.rifiuta_prenotazione`.

## API già esistenti

- `GET /api/v1/ui/sito-studio`.
- `GET /api/v1/ui/sito-studio/contatti`.

## Gap per react_operational_full

- Rimuovere `LegacyPostForm` dal flusso principale.
- Esporre payload GET con contratti operativi e senza segreti.
- Aggiungere POST JSON solo per azioni legacy realmente supportate.
- Mostrare azioni non supportate come disabled con motivazione.
- Mantenere builder e pubblicazione come legacy protetti/rollback tecnico.
