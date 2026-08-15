# Notiziario nella Panoramica

## Stato dell'intervento

Data del collaudo: 15 agosto 2026.

Il Notiziario è stato integrato nella Panoramica React come superficie operativa reale. Non usa dati dimostrativi e non contiene riferimenti visibili a prodotti esterni.

## Dati e proprietà tenant

- Le notizie pubblicate provengono dal repository strutturato `legal_updates` già usato dalla pipeline di aggiornamento legale.
- Fonte, categoria e ufficialità sono lette tramite le relazioni SQL `news`, `source_documents_normalized`, `source_documents_raw` e `sources`.
- Stato di lettura, preferito e collegamento al fascicolo sono salvati per utente nella tabella tenant `settings_config`.
- SQLite locale e PostgreSQL di produzione usano lo stesso schema `settings_config`; il JSON non è fonte operativa.
- Le fonti rapide sono una lista chiusa di siti istituzionali. Il lettore rifiuta URL non riconosciuti e limita dimensione, durata e redirect del recupero.

## API e interfaccia

- `GET /api/v1/ui/notiziario`: elenco delle sole notizie pubblicate, filtri, fascicoli disponibili e stato utente.
- `PATCH /api/v1/ui/notiziario/<id>/interazione`: lettura, preferito e collegamento al fascicolo con controllo tenant.
- `GET /api/v1/ui/notiziario/fonti/<fonte>`: lettura testuale governata della fonte istituzionale selezionata.
- Il componente React consente ricerca, filtri per fonte e stato, tutto schermo, lettura, preferiti, collegamento a fascicolo e apertura della nuova scadenza precompilata.
- Il lettore delle fonti non usa riquadri esterni vuoti: quando il sito non offre testo leggibile mostra una spiegazione e conserva il collegamento al sito ufficiale.

## Prova reale locale

Collaudo eseguito nella sessione autenticata reale su `http://127.0.0.1:8080` dopo ricostruzione del container `iusentra-app`, risultato healthy.

Sono stati osservati materialmente:

- caricamento di 8 aggiornamenti reali dalla Gazzetta Ufficiale;
- passaggio del contatore da 8 a 7 dopo la lettura e persistenza dopo ricaricamento;
- aggiunta e rimozione del preferito con filtro dedicato;
- collegamento al fascicolo `RG 1025/2026` e successiva rimozione del dato di prova;
- apertura di `Nuova scadenza` con titolo, descrizione, fonte e note precompilati, senza salvataggio di una scadenza di prova;
- lettura interna riuscita per Gazzetta Ufficiale e Consiglio Nazionale Forense;
- messaggio esplicito, senza area vuota, per una fonte non leggibile nel pannello;
- ricerca testuale, stato hover, focus visibile, tutto schermo e scroll completo;
- resa desktop, tablet `900 × 900` e mobile `390 × 844`, poi ripristino della dimensione normale.

Gli stati di lettura e preferito usati nel collaudo sono stati ripristinati; nessuna scadenza o collegamento di prova è rimasto salvato.

## Guardrail automatici

- `python -m pytest tests/test_notiziario_react.py -q`
- compilazione Python dei moduli modificati;
- typecheck TypeScript;
- build Vite nella ricostruzione Docker reale;
- controllo di URL istituzionali, estrazione testuale, API elenco/interazioni/fonti e persistenza SQL tenant.

## Limite governato

Alcuni siti istituzionali possono non esporre testo leggibile senza autenticazione o possono rifiutare il recupero automatico. In quel caso il pannello non simula contenuti: dichiara l'indisponibilità e offre il collegamento ufficiale. Il Notiziario e tutte le altre azioni restano operativi.
