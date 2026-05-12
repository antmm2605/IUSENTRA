# Matrice campo -> fonte Template Atti

Aggiornato: 2026-05-12.

| Campo | Significato | Fonte primaria | Fonti secondarie | Fallback ammesso | Confidence |
|---|---|---|---|---|---|
| `client_or_sender` / `cliente` | Cliente, assistito, mittente | parti fascicolo ruolo assistito | cliente collegato, preventivo/conferimento | manuale dopo ricerca interna | alta |
| `counterparty_or_recipient` / `controparte` | Controparte/destinatario | parti fascicolo ruolo controparte | soggetti/fascicolo/import portale | manuale dopo ricerca interna | alta |
| `lawyer` / `difensore` / `author_user_id` / `autore` | Avvocato/autore atto | Dati Studio: Avvocato titolare | utente corrente o professionista assegnato, timbro/configurazione studio | manuale dopo ricerca interna | alta |
| `recipient_or_court` / `ufficio_giudiziario` | Ufficio giudiziario/destinatario | fascicolo.tribunale/ufficio | import telematici, Practice Engine | manuale dopo ricerca interna | alta |
| `case_id` / `case_reference_display` | Pratica collegata/RG | fascicolo id/RG | import portale, ricevute | manuale dopo ricerca interna | alta |
| `subject` / `oggetto` | Oggetto atto | fascicolo oggetto/titolo | preventivo, conferimento, classificazione | manuale dopo ricerca interna | alta |
| `attachments_list` | Allegati | documenti fascicolo classificati | slot documentali/upload/import | manuale dopo ricerca interna | media |
| `case_value` / `dispute_value` | Valore causa/lite | fascicolo valore | preventivo/parcella/fattura | manuale dopo ricerca interna | media |
| `_lawyer_pec` / `pec_studio` | PEC studio | timbro studio | configurazione studio | manuale dopo ricerca interna | alta |
| `studio_timbro` | Intestazione studio | timbro studio | configurazione studio | blocco se richiesto e assente | alta |

Ogni campo mancante produce `missing_reason`. Ogni conflitto tra fonti affidabili produce warning e alternative.
