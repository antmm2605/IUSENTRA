# Release 2.481.0 — agenda come scrivania dell'avvocato e lettura delle PEC collaudata sui provvedimenti reali

Richieste dell'avvocato del 05/11/2026: ogni PEC lavorata come da una segreteria, con tutto preparato e confermato solo
dall'avvocato; l'agenda come unico punto di lavoro; collaudo della lettura delle PEC sulle comunicazioni reali.

## Lettura delle PEC e dei provvedimenti

Collaudo su 1.784 testi reali dello studio (226 provvedimenti): i capi con un termine non letti passano da 14 a 5
(nessuno a carico dello studio), le proposte da 460 a 632.

1. **Allegati firmati** — i provvedimenti `.p7m` (anche `.p7m.p7m`, in base64 e dentro lo zip) si leggono dal
   documento firmato; gli zip annidati fino a due livelli; immagini `.jfif` e `.webp` all'OCR (`pct/pec_pipeline.py`,
   `pct/ocr.py`).
2. **Rito del provvedimento** — «oltre spese generali, IVA e CPA» (Cassa forense) non è più letto come «c.p.a.»:
   111 provvedimenti del giudice ordinario erano trattati come amministrativi, con i termini del c.p.a. invece degli
   artt. 325, 327 e 434 c.p.c. Decide l'intestazione (chi emette il provvedimento); «R.G. lav.», «controversie di
   lavoro», «/LAV» indicano il rito del lavoro (`pct/provvedimenti/materia.py`).
3. **Formule dei tribunali** — primo capo subito dopo il «P.Q.M.»; «termine di ulteriori/altri N giorni»; «nel
   termine perentorio del giorno dell'udienza fissata»; «prima della predetta data / della nuova udienza / del termine»;
   «dall'odierna pronuncia»; «giorni 10, decorrente dalla comunicazione»; anno con apostrofo («26.11.'26»); date
   incollate dall'OCR (`pct/provvedimenti/ancore.py`, `dispositivo.py`, `testo.py`).
4. **Termine senza decorrenza** — bozza alla data più anticipata tra pronuncia e comunicazione, con la decorrenza da
   confermare (art. 176, co. 2, c.p.c.) (`pct/provvedimenti/statuizioni.py`).
5. **Sentenza con motivazione riservata** (art. 429 c.p.c.) — attesa della motivazione e termine lungo dichiarato
   provvisorio (`pct/provvedimenti/motivazione_riservata.py`).
6. **Ordinanze che assegnano un termine** (anche dei TAR) e **rigetto dell'istanza di trattazione scritta**, con data,
   ora e collegamento dell'udienza da remoto (`pct/provvedimenti/tipi.py`, `rigetto_trattazione.py`).
7. **Note scritte ex art. 127-ter** — il presidio automatico della PEC non blocca più la bozza del termine legale
   (perentorio, con l'ora del decreto); confermato il termine, il presidio della stessa PEC si chiude con il motivo
   (`pct/note_127_ter/proposta.py`, `pct/scadenziario.py`).
8. **Udienza da remoto** — il codice di accesso non è più «FiscaleDestinatario» di `Comunicazione.xml`; l'ID riunione
   non include la parola seguente; la fissazione dell'udienza non è più titolata «Rinvio udienza».
9. **Testo incollato dall'OCR** — avviso «leggere l'originale» quando mancano gli spazi.

## Agenda: ruolo dello studio e scheda di lavorazione

1. **Viste** Giorno, Settimana, Mese ed Elenco; ogni impegno con banda del tipo, titolo in linguaggio legale e riga
   «Cliente · Fascicolo · RG · Ufficio»; filtri «Da lavorare», Udienze, Termini, Notifiche, Comunicazioni
   (`frontend/src/features/agenda/ruolo/`).
2. **Scheda di lavorazione** (`GET /api/v1/ui/agenda/lavorazione`): cosa è arrivato con le prove della PEC, termini
   proposti da confermare o scartare (route esistenti dello scadenziario, con i loro permessi), collegamento
   dell'udienza da remoto, notifica, prossimo passo (`pct/agenda_lavorazione.py`,
   `web/services/react_agenda_lavorazione_bridge.py`).
3. **Collegamento della PEC al fascicolo** dalla scheda: dal profilo processuale (RG, anno e ufficio; oppure cliente
   presso lo stesso ufficio); mai indovinato a pari merito; per le cause nuove «Apri il fascicolo della nuova causa»
   con titolo, RG, anno, ufficio e giudice precompilati.
4. **Linguaggio legale** dei titoli scritti dalla pipeline e, in sola lettura, di quelli già salvati
   (`pct/agenda_linguaggio.py`); date sempre in formato italiano e ora di Roma.

## PEC di cancelleria leggibile per l'avvocato

1. **Finestra della PEC** — dati della comunicazione dal profilo processuale (ufficio e sezione, RG, giudice, parti,
   evento, descrizione, udienza), provvedimento in evidenza con «Leggi», prove di consegna e file tecnici raggruppati
   (ricevuta e firma del gestore, indice della busta, Comunicazione.xml), testo del messaggio diviso in consegna, campi
   della comunicazione (una volta sola, senza la copia in inglese del gestore) e testo integrale
   (`frontend/src/features/comunicazioni/`).
2. **Mittente** — «Per conto di: …» mostra l'indirizzo dell'ufficio, non quello del gestore.
3. **Dettaglio leggero della PEC** (`/api/pec/messages/<id>/source`) con il solo profilo processuale del rapporto.
4. **Scheda dell'impegno** — «Leggi il provvedimento», «Apri la PEC», «Scarica l'originale»; «Altre azioni» al posto del
   vecchio pannello di dettaglio.

Test: `tests/js/pec_cancelleria_testo.test.mjs`, `tests/test_pec_allegati_firmati.py`, `tests/test_provvedimenti_formule_tribunali.py`,
`tests/test_agenda_lavorazione.py`, `tests/test_agenda_linguaggio.py`, aggiornati `tests/test_pec_change_receipt.py`,
`tests/test_pec_audit_pipeline.py`, `tests/test_react_shell.py`.
