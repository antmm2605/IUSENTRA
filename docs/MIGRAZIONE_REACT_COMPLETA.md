# Migrazione completa a React e rimozione delle route Flask storiche

Obiettivo: tutte le pagine dello studio girano nella shell React; le route Flask
che rendono template Jinja si eliminano solo quando la pagina React ha le stesse
funzioni, verificate con test. Restano sul server, per natura, le risposte che
non sono pagine: API JSON, download, documenti da stampare (copertine), PDF,
azioni POST dei moduli esistenti e ingressi tecnici.

Aggiornato: 27/09/2026 (2.418.0).

## Regola

1. Una pagina si dichiara migrata quando la shell React la serve all'indirizzo
   storico e copre le azioni della vista Jinja (test in `tests/test_migrazione_react_*.py`).
2. Finché il template storico esiste resta raggiungibile con `?_legacy=1`, solo
   come ripiego; i collegamenti dell'applicazione non lo usano.
3. La route storica e il suo template si eliminano nella release di pulizia,
   dopo la verifica nel browser sulla macchina dello studio.

## Migrate

| Versione | Pagina | Dove in React |
|---|---|---|
| 2.412.0 | `/lex-operativo` | `LexOperativoPage` (API `/api/lex-operativo`) |
| 2.412.0 | `/preventivi/p/<id>` | `PreventiviPage`: scheda con prossimo passo del workflow, PDF, parcella, conferimenti, eliminazione |
| 2.412.0 | `/backup/<id>/ripristina` | Impostazioni › Backup: ripristino in una cartella dedicata (`ripristini/<nome>`) |
| 2.412.0 | `/utenti/<id>/modifica`, `/utenti/<id>/permessi` | `UtentiPage`: profilo, ruolo, stato, credenziale, permessi personalizzati |
| 2.412.0 | `/giurisprudenza/<id>`, `/giurisprudenza/<id>/modifica` | `GiurisprudenzaPage`: scheda dall'indirizzo, modifica con gli stessi campi dell'inserimento |
| 2.412.0 | `/template-atti/nuovo`, `/template-atti/scheda/<id>`, `/template-atti/<id>/modifica`, `/template-atti/<id>/usa` | `TemplateStudioPage` (API `/api/v1/ui/template-atti/studio`) |
| 2.412.0 | `/pagamenti/impostazioni/pagamenti` | Reindirizza a Impostazioni › Pagamenti (stessi campi) |
| 2.413.0 | `/fatturazione/nuova/<cliente>`, `/preventivi/nuovo/<cliente>`, `/preventivi/conferimento/nuovo/<cliente>` | Modulo React con il cliente già scelto (`?id_cliente=`) |
| 2.413.0 | `/fatturazione/<id>` | `FatturazionePage`: scheda aperta dall'indirizzo, link di pagamento (crea, rinnova, copia, email, WhatsApp), eliminazione della sola bozza |
| 2.413.0 | `/ricerca-legale/news/<slug>`, `/ricerca-legale/fonte/<id>`, `/ricerca-legale/daily/update/<id>/diff` | `RicercaLegaleSchedaPage` (API `/api/v1/ui/ricerca-legale`): news, fonte con storico e variazioni, differenze con approvazione |
| 2.413.0 | Controllo giornaliero delle fonti (pagina storica `/ricerca-legale`) | `ControlloGiornalieroPanel` in Ricerca legale: fonti, variazioni, approvazione, avvio in sfondo |
| 2.413.0 | `/checklist`, `/checklist/<id>` | `ChecklistAttiPage`: catalogo per aree con filtri, scheda dell'atto (documenti, controlli bloccanti, canale, cartella) |
| 2.413.0 | `/fascicoli/<id>/wizard/<modello>`, `/step/<n>`, `/completa` | `ChecklistAttiPage`: raccolta guidata con la via comune di caricamento dei documenti, passi facoltativi, indice, passaggio al deposito React |
| 2.413.0 | `/polisWeb/documenti`, `/pdp/documenti`, `/polisWeb/fascicolo-wizard` | Acquisizione guidata React del portale (`/portali/<portale>/acquisizione`) con ufficio, numero e anno del ruolo |
| 2.413.0 | `/sito-studio/servizi`, `/professionisti`, `/sedi`, `/regole-agenda` (elenco, nuovo, modifica) | `SitoStudioContenutiPage` (API `/api/v1/ui/sito-studio/contenuti`) |
| 2.413.0 | `/sito-studio/impostazioni`, `/sito-studio/articoli/nuovo` | `SitoStudioContenutiPage`: impostazioni complete del sito; bozza dell'articolo e apertura dell'editor React |
| 2.413.0 | `/sito-studio/pagine/nuova`, `/sito-studio/pagine/<id>/modifica`, `/sito-studio/preview`, `/sito-studio/prenotazioni` | Builder React (`?page_id=`, anteprima per dispositivo) e contatti React (prenotazioni) |
| 2.414.0 | `/admin/`, `/admin/governance`, `/admin/stato-installazione`, `/admin/salute-sistema`, `/admin/siti-studio/`, `/admin/lex-scorecard`, `/admin/osservabilita` | `PiattaformaApp`: applicazione React del superamministratore montata in `#piattaforma-react-root` (template `piattaforma_shell.html`), dati da `/api/v1/ui/piattaforma/<pagina>` con le sezioni di `web/services/react_piattaforma_bridge.py` |
| 2.415.0 | `/admin/pianificazioni`, `/admin/crash-test-operativo`, `/admin/installazione-pack/`, `/admin/assistente-migrazione` | `PiattaformaApp` con azioni (`/api/v1/ui/piattaforma/<pagina>/azioni/<azione>`): moduli in `web/services/react_piattaforma_pagina_*.py` |
| 2.416.0 | `/admin/studi`, `/admin/studi/nuovo`, `/admin/studi/<slug>`, `/admin/studi/<slug>/utenti`, `/admin/studi/<slug>/database`, `/admin/utenti-piattaforma`, `/admin/server-manutenzione` | `PiattaformaApp` con parametri dell'indirizzo e navigazione dopo le azioni |
| 2.417.0 | `/admin/aggiornamenti-legali/*` (cruscotto, fonti, acquisizione e scheda, catalogazione, archivio, revisioni), `/admin/copertura-ai/`, `/admin/copertura-ai/review`, `/admin/supporto-remoto` | `PiattaformaApp`: il pannello di piattaforma è interamente React; le console storiche restano con `?_legacy=1` (e per gli amministratori non superamministratori di aggiornamenti legali e copertura AI) |
| 2.418.0 | `/applicazioni`, `/applicazioni/<id>` | `ApplicazionePage` (API `/api/v1/ui/applicazioni`): utilità e verifiche in pagina, strumenti con valori predefiniti e dati della pratica |
| 2.418.0 | Azioni della pagina storica `/ricerca-legale` (monitoraggio, tabelle normative, registro della mediazione) | `ControlloGiornalieroPanel` |
| 2.418.0 | `/fascicoli/<id>/penale/pdp` | Sezione `#penale-pdp` del fascicolo React (`PenalePdpSezione`) |

## Già React (verificato 27/09/2026)

`/portali/<portale>/acquisizione` (acquisizione guidata), `/fascicoli/<id>/deposito/prepara`
(preparazione del deposito), `/clienti/<id>/faldone`, `/clienti/<id>/portale`,
`/fascicoli/<id>/collaboratori`: il gate li serve già con la shell React.

## Documenti, non pagine

- `/fascicoli/<id>/copertina` e `/clienti/<id>/faldone/copertina`: fogli da
  stampare. Dalla 2.412.0 il gate React non li intercetta più (la copertina del
  faldone finiva nella Panoramica React).

## Ancora da migrare

| Area | Pagine | Nota |
|---|---|---|
| Studio | `/fascicoli/<id>/documenti/<doc>/editor` | Già React (`DocumentEditorPage`): resta da togliere il ramo `?_legacy=1` e il template storico |
| Supporto | `/support/join/<token>` | Stanza del cliente (JavaScript storico); la stanza dell'operatore è React e dalla 2.414.0 si avvia davvero (prima il modulo senza parametro di versione non partiva e la stanza restava vuota) |
| Pubbliche | `/login`, `/login/2fa`, profilo con password obbligatoria, `/portale/<token>/*`, `/pagamenti/paga/<token>`, `/support/join/<token>`, `/accesso/<token>` | Serve un ingresso React pubblico (come `/portale-cliente`) |
| Pubbliche | sito dello studio `/web/<slug>/*` | Pagine pubbliche indicizzate dai motori di ricerca: restano rese dal server finché non c'è un rendering React lato server |
| Tecniche | `/offline`, pagine di errore | Restano statiche: servono quando l'applicazione non risponde |
