# Audit Montagnese PEC e presidi notifiche - 21/07/2026

Tenant produzione: `studio-legale-giuseppe-montagnese`  
Registry produzione: `/data/tenants.json`  
Storage produzione: `/data/tenants/studio-legale-giuseppe-montagnese`  
Esecuzione: server Hetzner, container `iusentra-app`, tenant Studio Legale Giuseppe Montagnese.

## Esito sintetico

Il controllo reale non deve considerare già notificata una sentenza solo perché è arrivata tramite PEC di cancelleria. La comunicazione di cancelleria alimenta l'esame del provvedimento; la notifica dell'avvocato richiede prova distinta: relata, PEC inviata dal PC locale, RAC, RdAC completa e deposito/collegamento della prova nel fascicolo.

Al 21/07/2026 il tenant produzione ha copertura V2 completa delle PEC acquisite: nessuna PEC resta senza evento legale strutturato.

## Source of truth

- Fascicoli, appuntamenti e scadenze strutturate: `/data/tenants/studio-legale-giuseppe-montagnese/studio.db`.
- PEC, eventi legali V2 e presidi notifiche: `/data/tenants/studio-legale-giuseppe-montagnese/email/pec_audit.sqlite`.
- Topbar/Web Push: `/data/tenants/studio-legale-giuseppe-montagnese/notifications/notifications.db`.
- JSON tenant-aware: mirror/storico o supporto compatibile, non fonte conclusiva quando esiste SQL.

## Conteggi produzione

| Area | Conteggio |
| --- | ---: |
| Fascicoli totali SQL | 334 |
| Fascicoli non archiviati | 302 |
| Fascicoli archiviati | 32 |
| Appuntamenti SQL | 870 |
| Scadenze SQL | 780 |
| Scadenze con marker PEC/notifica | 176 |
| PEC acquisite | 1.369 |
| Eventi legali V2 | 1.371 |
| PEC senza evento V2 | 0 |
| Presidi notifica totali/storici | 32 |
| Presidi attivi | 5 |

Distribuzione presidi:

- `NEEDS_REVIEW` / `judgment_to_notify_review`: 4;
- `NOTIFICATION_CONFIRMED` / `judgment_to_notify_review`: 1;
- `NOT_REQUIRED`: 5;
- `CANCELLED`: 6;
- `LEGACY_ASSUMED_HANDLED`: 16.

## Presidi attivi da mostrare all'avvocato

| Fascicolo | RG | Tribunale | PEC sorgente | Stato presidio | Esito audit |
| --- | --- | --- | --- | --- | --- |
| Romeo Maria c. MIM (`2026/320`) | 1428/2026 | Tribunale di Palmi | 17/07/2026 13:46 | `NOTIFICATION_CONFIRMED` | Notifica confermata, ma presidio da mantenere finché prova/ricevute/deposito non sono chiusi. |
| Alfano Giuseppe c. MIM (`2026/307`) | 1100/2026 | Tribunale di Padova | 16/07/2026 13:01 | `NEEDS_REVIEW` | Sentenza ex art. 429 da valutare/preparare per notifica; nessuna prova completa post-sorgente nel fascicolo. |
| Monea Mariano II c. MIM (`2026/311`) | 1394/2026 | Tribunale di Palmi | 14/07/2026 13:05 | `NEEDS_REVIEW` | Sentenza a verbale da valutare/preparare per notifica; nessuna prova completa post-sorgente nel fascicolo. |
| Speranza II c. MIM (`2026/322`) | 1480/2026 | Tribunale di Palmi | 14/07/2026 13:01 | `NEEDS_REVIEW` | Sentenza a verbale da valutare/preparare per notifica; nessuna prova completa post-sorgente nel fascicolo. |
| Calabrò II ricorso c. MIM (`2026/250`) | 3571/2025 | Tribunale di Locri | 13/07/2026 09:47 | `NEEDS_REVIEW` | Sentenza/attestazione presenti, ma nessuna prova completa post-sorgente nel fascicolo. |

Nota: lo stato `NOTIFICATION_CONFIRMED` non va mostrato come “da preparare” se l'avvocato ha confermato la notifica; va però mantenuto nel presidio operativo fino alla chiusura documentale della catena.

## Differenza locale/produzione

La copia locale attuale non contiene lo stesso tenant:

- locale: tenant registry `studio-montagnese`, id `tenant-local-studio-montagnese`, storage `tenant-8bf98719c459`, `10` fascicoli SQL;
- produzione: tenant registry `studio-legale-giuseppe-montagnese`, id `0ab0a3ca-7b66-4c84-ab5d-7690fcc62f03`, storage `studio-legale-giuseppe-montagnese`, `334` fascicoli SQL.

Per la prova finale locale non basta quindi avviare `127.0.0.1:8080`: va prima riallineato in modo sicuro lo snapshot tenant produzione.

## Prestazioni

La logica implementata non scansiona 1.369 PEC o centinaia di fascicoli durante il caricamento pagina. I record operativi vengono materializzati durante validazione/refresh PEC e letti da tabelle indicizzate. La pagina Notifiche/Agenda/Scadenziario deve limitarsi a leggere presidi, marker e link fonte già indicizzati.

## Da verificare prima della chiusura

- Prova reale browser produzione su `/notifiche-legali`, Agenda/Scadenziario e topbar per i 5 presidi attivi.
- Verifica visuale del caso Alfano: testo corretto `Sentenza da valutare per la notifica`, fonte PEC/documento apribile, nessuna falsa `Opposizione alla trattazione scritta`.
- Riallineamento sicuro copia locale con snapshot tenant produzione e prova su `127.0.0.1:8080`.
- Gate mirati/completi, commit, push branch gemelli e deploy finale da commit.
