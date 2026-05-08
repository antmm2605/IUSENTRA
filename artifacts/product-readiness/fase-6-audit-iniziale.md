# Fase 6 - Audit prodotto iniziale

## Route controllate

Regia/Dashboard, Fascicoli, Fascicolo quadro, Clienti, Soggetti, Agenda, Scadenziario, Documenti, Telematico, Email PEC, Messaggi, Lex AI, Ricerca legale, Legal Intelligence, Template atti, Redazione atti, Tariffario, Preventivi, Fatturazione, Amministrazione/Impostazioni dove React.

## Esito UX

- Titoli/sottotitoli: adeguati nelle nuove console React; route legacy non modificate.
- Azioni primarie: corrette nelle route promosse; rimosse CTA `?_legacy=1` primarie.
- Loading/empty/error: presenti nelle pagine esistenti e rafforzati con componenti condivisi.
- Badge/icone: aggiunto registry centralizzato `frontend/src/design/icons.tsx`.
- Responsive/accessibilita: componenti nuovi hanno stati e breakpoint minimi; serve verifica browser finale.
- Testo tecnico: sostituiti riferimenti visibili "legacy" con "percorso dedicato/governato" nelle route promosse.
- Mock/demo: 0 nelle route full secondo gate.

## Gap iniziali

- 25 route restano legacy per rischio tecnico.
- 130 template Jinja restano UI primaria.
- Browser visuale end-to-end non ancora eseguito su tutte le route.
- Performance misurata solo tramite build/typecheck/gate, non tramite Lighthouse o profiler.
