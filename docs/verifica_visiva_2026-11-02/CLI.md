# Mappa area CLI — Clienti e comunicazioni (verifica visiva 02/11/2026, produzione 2.476.0)

Formati: PC 1440x900 e telefono 390x844. Sola lettura (scritture bloccate), CSS Bootstrap servito da copia locale
(il proxy di prova blocca cdn.jsdelivr.net: le prime schermate senza Bootstrap sono in `app/audit/CLI/bs/`).
Script: `app/cli_giro.js`, `cli_vista.js`, `cli_schede.js`, `cli_email.js`, `cli_catalogo.js`, `cli_tempo.js`, `cli_dom.js`.
Tempi al primo contenuto: /clienti 6,9 s, /email 6,3 s, /soggetti 6,4 s. Nessun errore JS, nessuna API 4xx/5xx.

| Pagina | Schede / sezioni | Pulsanti, filtri, finestre provati | Esito |
|---|---|---|---|
| /clienti | 9 indicatori (Totali, Attivi, Potenziali, Archiviati, Con procedimenti, Da completare, Senza recapiti, Privacy, Documenti scaduti), barra filtri (ricerca, Tipo, Stato, Filtri, Aggiorna), tabella 268 clienti, schermo intero, pannello laterale | Esporta, Archivio clienti, Nuovo cliente, azioni riga (scheda, modifica, cartella, elimina: non eseguito) | CLI-01, CLI-02 |
| /clienti/nuovo | Indicatori, schede Nuovo cliente / Nuovo soggetto, Tipo cliente PF/PG, dati, completezza campi | Solo modulo (nessun salvataggio) | OK (CLI-09 per la variante soggetto) |
| /clienti/{id} (= /cartella) | Avvisi anagrafici, 5 indicatori-catalogo (Fascicoli, Scadenze, Documenti, Comunicazioni, Parcelle: finestre con ricerca, filtro, selezione, Visualizza), Documenti d'identità, Antiriciclaggio, Dati cliente, Azioni rapide, Fascicoli, Scadenze, Preventivi, Comunicazioni, Agenda, Economia, Timeline | Modifica anagrafica, Nuovo fascicolo, Faldone cliente, Avvia adeguata verifica (non eseguito), cataloghi aperti tutti | CLI-03, CLI-04, CLI-05, CLI-06, CLI-07 |
| /clienti/{id}/faldone | Rende la stessa cartella React | Faldone PDF raggiungibile solo da /faldone/pdf | CLI-05 |
| /clienti/{id}/modifica | Modulo cliente in modifica | — | OK |
| /soggetti | 4 indicatori, ricerca, Tipo, Ruolo, ordinamento, Solo da completare, tabella 53 soggetti, schede telefono | dettaglio, modifica, elimina (non eseguito) | CLI-08, CLI-10 |
| /soggetti/{id}, /soggetti/{id}/modifica | Scheda soggetto selezionato (Modifica dati, Scrivi comunicazione, Nuovo fascicolo), modulo | — | CLI-08 |
| /soggetti/nuovo | Registri pubblici ReGIndE / PP.AA. / INI-PEC, tipo soggetto, completezza | Cerca (GET) | CLI-09, CLI-14 |
| /crm | 3 contatori, Registra contatto, 6 colonne del flusso (layout a due righe voluto) | Registra contatto (solo apertura) | OK |
| /cartelle-condivise | 6 indicatori, ricerca, Azzera filtri, avviso privacy, Cartelle gestite | Aggiorna, Clienti, Registro attività, Registro GDPR, Pulisci scaduti (non eseguito) | OK |
| /portale-cliente | Accesso cliente richiesto | Torna al sito | OK |
| /app/portale-clienti | 4 indicatori, Nuovo invito (cerca, cliente, fascicoli, validità, messaggio), Pratiche cliente | Crea invito (non eseguito), Link cliente, Avvia chat | OK |
| /messaggi | 4 indicatori, ricerca, canale, stato, Filtra, storico, canali disponibili, Lex | Apri, Elimina (non eseguito), Email studio, Nuovo messaggio | CLI-11, CLI-14 |
| /messaggi/{id} (3 email di maggio) | Messaggio selezionato: canale, destinatario, stato, creato | Rispondi, Chiedi a Lex | CLI-11 |
| /messaggi/nuovo | Canale (Email/SMS/WhatsApp), Destinatario, Testo, Anteprima, Checklist, Canali | Invia/Annulla (non inviato) | CLI-12, CLI-13, CLI-14 |
| /email (PEC) | 8 indicatori cliccati (Totali, In arrivo, Non lette, Inviate, Cestino, PST/PCT, Allegati, Collegate), schede Tutte/In arrivo/Inviati/Cestino, Filtri (stato lettura, esito PCT, ordinamento, 4 caselle), paginazione, dettaglio messaggio (Apri MIME, Esegui controllo, Salva nel fascicolo, Scadenza automatica), controllo automatico, profilo processuale, allegati (Visualizza → visore postacert.eml, Scarica), Cabina PEC, Controlli automatici, Esiti da presidiare, PST in attesa, Azioni rapide | solo visualizzazione | CLI-15, CLI-16, CLI-17, CLI-18 |
| /email-ordinaria | 6 indicatori, schede, Filtri, dettaglio (Apri, Rispondi, Cestino, Letta), Cabina email, Email da leggere, Allegati recenti, Azioni rapide | solo visualizzazione | CLI-16, CLI-17 |
| /notifiche | Impostazioni › Notifiche: 4 contatori, Notifiche su questo dispositivo, Avvisi operativi (30), presidio configurazione | Attiva/Disattiva/Invia test (non eseguiti) | CLI-19, CLI-20, CLI-21 |
| /notifiche-whatsapp | Impostazioni › WhatsApp: Twilio SID, chiavi, numero, CallMeBot, Verifiche operative | Invia test WhatsApp, Salva sezione (non eseguiti) | CLI-20 |

---

# Registro difetti area CLI — Clienti e comunicazioni (02/11/2026, produzione 2.476.0)

Schermate in `scratchpad/app/audit/CLI/` (prefissi: `v_` viste, `s_` schede/cataloghi, `e_` posta, `m_` montaggi, `bs/` senza Bootstrap).
Nessun dato di cliente riportato: si usano id di pagina.

| Id | Pagina / funzione | Formato | Descrizione | Schermata | Gravità | Causa nel codice | Stato |
|---|---|---|---|---|---|---|---|
| CLI-01 | /clienti tabella e filtri | PC | Colonne compresse: C.F. su tre righe, badge «Qualità» troncati («Da comp», «Docume») sotto la colonna Azioni fissa, colonna Stato fuori vista; selettori Tipo e Stato troncati («Tutti i tipi (2(»). | v_pc_clienti_0.png | media | frontend/src/components/AnagraficaClientiPage.css:1 (selettori 180px), :7 e :25-69 (min-width 1240px, larghezze colonne) | corretto |
| CLI-02 | /clienti scheda cliente | tel | Il nome del cliente compare due volte nella stessa scheda (accanto alla casella e come titolo). | v_tel_clienti_1.png (bs/) | bassa | frontend/src/components/AnagraficaClientiPage.tsx:384 | corretto |
| CLI-03 | /clienti/{id} Documenti d'identità | PC/tel | Testo con genere fisso: «collegato ai fascicoli della cliente» anche per clienti uomini o società. | s_pc_clienti_FBA5C7FF_00.png | bassa | frontend/src/components/CartellaClientePage.tsx:243 | corretto |
| CLI-04 | /clienti/{id} indicatori, pannello e catalogo «Fascicoli attivi» | PC/tel | Sotto «Fascicoli attivi» compaiono fascicoli in stato «Definito»: il bridge (per scelta documentata) considera fuori gestione solo gli archiviati, ma l'etichetta dice «attivi». | m_pc_cli_det.png | media | CartellaClientePage.tsx:221,275; CartellaClienteCatalog.tsx:11 | corretto (etichetta «Fascicoli in gestione») |
| CLI-05 | /clienti/{id} «Faldone cliente» | PC/tel | Il collegamento porta a /clienti/{id}/faldone, che nella shell React rende la stessa cartella: il clic non produce nulla di nuovo; inoltre è un link senza stile accanto a due pulsanti. Il faldone reale è il PDF /faldone/pdf (verificato 200, %PDF). | s_pc_clienti_FBA5C7FF_00.png | media | web/services/react_clienti_bridge.py:591; CartellaClientePage.tsx:207 | corretto (Faldone PDF) |
| CLI-06 | /clienti/{id} Controlli anagrafici | PC/tel | Avviso doppio: «Anagrafica incompleta: almeno un recapito» e «Nessun recapito operativo registrato». | s_pc_clienti_FBA5C7FF_00.png | bassa | CartellaClientePage.tsx:183-186 | corretto |
| CLI-07 | /clienti/{id} Antiriciclaggio | PC/tel | La frase cita l'esclusione della difesa in giudizio come «art. 17 c. 7» D.Lgs. 231/2007; la stessa citazione è nella scheda di fonte del progetto (docs/specs/ministero/ANTIRICICLAGGIO_CNF_231_2007_2026-08-13.md), ma il comma va riscontrato sul testo vigente (Normattiva) prima di toccarla. | s_pc_clienti_FBA5C7FF_00.png | bassa | frontend/src/components/clienti/ClienteAntiriciclaggio.tsx:111; pct/antiriciclaggio.py:50 | aperto: verifica della fonte normativa, non si cambia una norma senza riscontro |
| CLI-08 | /soggetti tabella, scheda telefono e scheda soggetto | PC/tel | Ruolo mostrato come codice («ALTRO» maiuscolo) mentre il filtro dice «Altro»; su telefono «ALTRO - -» perché il bridge manda «-» come identificativo assente. | v_pc_soggetti_0.png, m_tel_soggetti.png | bassa | frontend/src/components/SoggettiPage.tsx:201,237 | corretto |
| CLI-09 | /soggetti/nuovo | PC/tel | Gli indicatori in testa sono quelli dei clienti (268 clienti, 250 PF…) anche nella creazione di un soggetto; «1 documenti scaduti» al plurale. | v_pc_soggetti_nuovo_0.png | media | frontend/src/components/NuovoClientePage.tsx:947, 2022 | corretto |
| CLI-10 | /soggetti dato «Agenzia delle Entrate-Riscossione» | PC/tel | Ente pubblico classificato «Persona fisica» con P.IVA: il dato falsa il conteggio «Persone fisiche». | v_pc_soggetti_0.png | bassa | dato in archivio, non codice | aperto: correzione del dato da parte dello studio |
| CLI-11 | /messaggi elenco e dettaglio (3 email di maggio in «Errore») | PC/tel | Lo stato «Errore» non dice mai il motivo; il bridge passa `error` ma la pagina non lo mostra e il valore salvato è un'eccezione Python grezza («('a float is required', <object…>)», «'NoneType' object has no attribute 'email'»). | pc/_messaggi_944C9CE3.txt | alta | web/services/react_messaggi_bridge.py:173; frontend/src/components/MessaggiPage.tsx (nessun uso di `error`) | corretto |
| CLI-12 | /messaggi/nuovo schede Canale | PC/tel | Badge di stato tagliati («omple», «ink We»): la regola dell'icona 40x40 colpisce anche il badge. | v_pc_messaggi_nuovo_0.png | media | frontend/src/components/MessaggiPage.css `.iu-msg-channel-card>span` | corretto |
| CLI-13 | /messaggi/nuovo barra Invia/Annulla | PC/tel | Barra fissa a 82px dal fondo anche su PC: copre il campo «Email destinatario»; su telefono è alta ~150px sopra la barra di navigazione. | v_pc_messaggi_nuovo_0.png, m_tel_messaggi_nuovo.png | media | MessaggiPage.css `.iu-msg-submitbar` e @media 620px | corretto |
| CLI-14 | Intestazioni di /messaggi, /messaggi/nuovo, /clienti/nuovo, /soggetti/nuovo | tel | Le azioni dell'intestazione restano in una colonna stretta a destra del titolo (testo su più righe, pulsante bianco schiacciato). | m_tel_vari.png, m_tel_soggetti.png | media | preset globale (IusentraPreset.tsx:134, display:flex riga !important); le regole mobili dei componenti usano grid e non hanno effetto | corretto (regole mobili nei CSS di pagina) |
| CLI-15 | /email elenco, dettaglio, Esiti da presidiare, filtro Esito PCT | PC/tel | Stati PCT mostrati come codici: «ACCETTATO_PEC», «CONSEGNATO», «Esito telematico rilevato: ACCETTATO_PEC», opzioni del filtro con il codice. | m_e1.png | media | EmailPecPage.tsx:1138,1279,1345; web/services/react_email_bridge.py:1538 | corretto |
| CLI-16 | /email, /email-ordinaria riga di stato | PC/tel | Se una richiesta non arriva al server compare il messaggio tecnico inglese «Failed to fetch». | m_e2.png | bassa | EmailPecPage.tsx (14 gestori `error instanceof Error ? error.message`) | corretto |
| CLI-17 | /email dettaglio, sopratitolo | PC | Cartella ripetuta: «INVIATI · INVIATI», «CESTINO · CESTINO». | m_e2.png | bassa | EmailPecPage.tsx:1258 | corretto |
| CLI-18 | /email elenco, avatar | PC/tel | Iniziali con virgolette quando il nome mittente è tra apici ('"C'). | pc/_email.ctrl.json | bassa | EmailPecPage.tsx:286 | corretto |
| CLI-19 | /notifiche Avvisi operativi (e campanella) | PC/tel | Avvisi di trattazione scritta (note in sostituzione dell'udienza, art. 127-ter c.p.c.) etichettati «Udienza audiovisiva da verificare»: la sola modalità «trattazione scritta»/«in presenza» basta a generare l'etichetta audiovisiva (art. 127-bis). | pc/_notifiche.txt | alta | web/services/topbar_operational.py:1256-1286 | corretto |
| CLI-20 | Banner Local Signer (tutte le pagine, visto su /notifiche-whatsapp) | PC | La posizione fissa dipende dalla classe Bootstrap `position-fixed` caricata da CDN esterno: se il CSS non arriva il banner finisce in fondo al documento, metà sotto la barra laterale. | bs/v_pc_notifiche_whatsapp_1.png | bassa | web/static/js/local-signer-monitor.js:164 | corretto |
| CLI-21 | /notifiche «Notifiche su questo dispositivo» | tel | Titolo e descrizione compressi in una colonna stretta dal badge di stato. | m_tel_notifiche.png | bassa | frontend/src/features/impostazioni/components/NotificationsSettingsPanel.css:40 e @media 900px | corretto |

Riepilogo: 21 difetti — alta 2, media 9, bassa 10. Corretti 19, aperti 2 (CLI-07 fonte normativa da riscontrare, CLI-10 dato).
