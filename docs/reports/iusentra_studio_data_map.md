# Mappa dati studio IUSENTRA per Template Atti

Aggiornato: 2026-05-12.

| Modulo | Repository/classe/funzione | Campi disponibili | Sensibili | Accesso | Permessi | Tenant-aware | Usata dal prefill |
|---|---|---|---|---|---|---|---|
| Timbro studio | `pct.studio_timbro` | studio, professionista, CF/PIVA, PEC, email, indirizzo | si | `STUDIO_TIMBRO_DB` | configurazione studio | si | si |
| Configurazione studio | `pct.config_studio` / app config | studio, PEC, SMTP, dati fiscali | si | `CONFIG_STUDIO_DB` | amministratore/configuratore | si | si |
| Utenti/professionisti | `pct.auth`, `web.helpers.get_utenti` | id, username, nome, ruolo | si | `AUTH_DB` | sessione | si | si |
| Clienti | `web.helpers.get_clienti` | nome, CF/PIVA, indirizzo, recapiti | si | `CLIENTI_DB` | sessione | si | si |
| Soggetti e parti | `web.helpers.get_soggetti`, parti fascicolo | assistito, controparte, ruoli | si | `SOGGETTI_DB`, `SOGGETTI_PARTI_DB` | sessione | si | si |
| Fascicoli | `web.helpers.get_fascicoli` | id, titolo, oggetto, RG, ufficio, valore, documenti | si | `FASCICOLI_DB` | sessione | si | si |
| Documenti fascicolo | fascicolo/documentale | allegati, classificazioni, slot | si | `FASCICOLI_DOCS`, documentale tenant | sessione | si | si |
| Preventivi/incarichi | repository preventivi | importi, accettazione, conferimento | si | data path tenant | sessione | si | si quando collegato |
| Procure/privacy | template studio/documentale | procura, privacy cliente, firme | si | documentale tenant | sessione | si | si quando indicizzato |
| Portali importati | PST/PAT/PTT/PDP import autorizzati | uffici, RG, ricevute, deposito | si | data path tenant | sessione/autorizzazione | si | si quando presente |

I dati riservati non vengono inviati su web. La ricerca web riguarda solo norme e documentazione pubblica.
