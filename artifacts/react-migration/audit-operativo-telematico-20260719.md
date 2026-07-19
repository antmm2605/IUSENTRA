# Audit operativo deposito, notifiche e PST

Aggiornato il 19/07/2026.

Questo file è la memoria operativa del lavoro su deposito telematico, notifiche ex L. 53/1994, consultazione PST/PolisWeb, documenti del fascicolo d'ufficio e Local Signer. Deve essere aggiornato a ogni revisione significativa prima del report finale.

## Fonti e materiali

- Fonti ministeriali locali versionate:
  - `data/uffici/uffici_giudiziari.json`
  - `pct/data/uffici_pst_pubblici.json`
  - `pct/data/uffici_ministero.json`
  - `pct/data/uffici_ministero_extra.json`
  - XSD e mapping usati da `pct/deposito_telematico_catalogo.py`, `pct/busta.py`, `pct/datiatto_xsd.py`.
- Fonti ufficiali verificate via web il 19/07/2026:
  - Portale Servizi Telematici, sezione servizi: https://pst.giustizia.it/PST/it/services.page
  - Specifiche tecniche ex art. 34 D.M. 44/2011, provvedimento DGSIA 7 agosto 2024: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC3429
  - Scheda ReGIndE del PST: https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC405
  - Consultazione ReGIndE e servizio web per Punto di Accesso: https://pst.giustizia.it/PST/it/dettaglio_schede_tematiche.page?contentId=ACC427&modelId=12
- Materiale decompilato di confronto:
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer`
  - Dossier collegato: `artifacts/react-migration/confronto-documenti-fascicolo-ufficio.md`
- Prove reali disponibili nel software:
  - depositi reali già completati e ricevute presenti nei fascicoli;
  - notifiche già eseguite nei fascicoli con documenti rinominati come originale notificato;
  - fascicoli scaricati da PST/PolisWeb e relativo storico documentale.

## Regole non negoziabili

- Il software deve risolvere ufficio, codice ministeriale, codice interno e PEC prima del deposito; l'avvocato non deve correggere dati che il catalogo ufficiale consente di completare.
- Un invio o una simulazione può essere bloccato solo da requisiti obbligatori reali: atto principale, ufficio/PEC/codice, dati XML richiesti dal tipo deposito, firme, busta/indice, prova PEC, ricevute dove necessarie.
- Le notifiche devono conservare il ciclo: selezione pratica e documenti, destinatari da elenco corretto, verifica pubblico elenco, relata e attestazione unica, firma digitale, prova senza invio, invio PEC dal PC locale, acquisizione ricevute, marcatura del documento notificato come originale notificato.
- La consultazione PST/PolisWeb deve seguire il percorso: pratica già nota, accesso al portale, sezione documenti, scelta dell'avvocato, download/acquisizione nel fascicolo senza duplicare documenti già presenti.
- Ogni documento o PEC letto deve avere chiave/hash di presidio; quello già letto non deve essere riletto, ma ogni nuovo documento o ZIP deve entrare nel controllo automatico.
- Ogni informazione automatica in agenda, scadenziario, notifiche, fascicolo e dashboard deve poter mostrare la fonte interna senza uscire dal software.

## Script e gate

- `scripts/audit_deposito_catalogo_end_to_end.py`
  - Deve fallire se un tipo deposito PCT non genera XML coerente.
  - Deve fallire se un ramo resta sospeso come generatore non completato.
  - Deve fallire se un ufficio PCT operativo non è nel catalogo IUSENTRA.
  - Deve fallire se PEC o codice ufficio mancano.
  - Deve fallire se il resolver React non completa PEC/codice da alias reali di pratica.
  - Ultimo esito: OK, 270 tipi deposito, 252 PCT, 18 UNEP, 593 uffici PCT operativi coperti, 0 errori resolver.
- `scripts/audit_legal_notification_coverage.py`
  - Deve presidiare modelli relata, attestazione, registri pubblici e indirizzi disponibili.
  - Da rilanciare prima della chiusura notifiche.
- Test mirati da eseguire a ogni modifica:
  - `python -m pytest -q tests/test_reginde.py`
  - `python scripts/audit_deposito_catalogo_end_to_end.py --output artifacts/react-migration/audit-deposito-catalogo-20260719.json`
  - test React interessati dal deposito/notifiche.
  - build frontend senza chunk sopra soglia governata.

## Fix del 19/07/2026

### Ufficio Reggio Calabria

Problema riprodotto:

- `TRIBUNALE DI REGGIO CALABRIA` si risolveva.
- `TRIBUNALE DI REGGIO DI CALABRIA` non si risolveva.

Causa:

- Il catalogo conteneva `Tribunale di Reggio Calabria`, codice interno `0910010`, codice ministeriale `0800630097`, PEC `tribunale.reggiocalabria@civile.ptel.giustiziacert.it`.
- Il resolver confrontava nomi quasi letterali e non normalizzava articoli/preposizioni ridondanti usati nelle pratiche reali.

Soluzione:

- Alias centrali in `pct/uffici_giudiziari.py` per nomi ufficio reali e descrizioni ministeriali.
- Priorità agli uffici operativi con PEC/codice rispetto a righe storiche `ex` o `non attivo`.
- Payload deposito React allineato al resolver centrale in `web/services/react_fascicoli_bridge.py`.
- Test di regressione in `tests/test_reginde.py`.
- Audit esteso per provare alias reali su tutti gli uffici PCT operativi.

Esito verificato:

- `TRIBUNALE DI REGGIO DI CALABRIA` risolve `0910010`, `0800630097`, `tribunale.reggiocalabria@civile.ptel.giustiziacert.it`.
- I 7 Giudici di Pace scoperti dall'audit vengono risolti sulla riga attiva con PEC.
- `scripts/audit_deposito_catalogo_end_to_end.py` passa con `react_resolver_errors: 0`.

## Checklist aperta prima della chiusura definitiva

- Verifica produzione pagina deposito `F7AA4E0C` dopo deploy: il box ufficio deve mostrare PEC e codice risolti.
- Verifica reale, senza invio PEC, della simulazione deposito con Local Signer raggiungibile dal browser.
- Verifica notifiche ex L. 53/1994 con chiavetta: PEC notificante, destinatario, data/ora verifica, relata, attestazione unica, firma relata e prova senza invio.
- Verifica che dopo notifica i documenti acquisiscano la marcatura `originale notificato` secondo le notifiche già presenti nei fascicoli.
- Verifica PST/PolisWeb: apertura portale, accesso, arrivo a InfoFascicolo, tab documenti, scelta documento, acquisizione nel fascicolo senza duplicati.
- Verifica agenda/scadenziario: fonte visualizzabile in finestra sopra pagina, link audiovisivo cliccabile, colori coerenti con legenda, completamento stato funzionante.
- Riallineamento locale, commit, push branch gemelli, deploy Hetzner, container unico `iusentra-app`, `/api/pronto`, igiene repo.

## Aggiornamento 19/07/2026 - pulsanti prova deposito

Log deposito controllato: in `artifacts/react-migration/procedura-deposito-telematico.md` è registrata la prova reale del 29/06/2026 su `795C50AC`, con `Prova senza invio reale` cliccabile, busta pronta, destinatario PEC, oggetto PEC, report di compatibilità e successivo invio reale partito dal PC locale dell'avvocato.

Correzione richiesta: `Prova senza invio reale` e `Simula invio PEC` non devono più spegnersi per gli stessi motivi dell'invio reale. Devono restare azionabili come prova diagnostica e riportare il requisito mancante senza spedire PEC. `Invia deposito reale` mantiene invece tutti i blocchi obbligatori fino a prova positiva, busta conforme e invio locale disponibile.

Verifica reale su produzione del 19/07/2026: pagina `F7AA4E0C/deposito/prepara` aperta su `https://app.iusentra.it`, pulsanti `Prova senza invio reale` e `Simula invio PEC` abilitati, click reale su `Simula invio PEC`, conferma senza invio esterno e messaggio puntuale `Atto principale non selezionato. Seleziona l'atto principale nello step documenti.`. Nessun invio PEC reale eseguito.
