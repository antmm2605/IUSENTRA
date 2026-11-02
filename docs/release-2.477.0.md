# IUSENTRA 2.477.0 — correzioni della verifica visiva completa del 02/11/2026

Ogni pagina e funzione dell'applicazione è stata aperta e controllata a vista su PC e telefono, in sola lettura sulla
produzione 2.476.0 (mappa e registri in `docs/verifica_visiva_2026-11-02/`). Questa versione raccoglie tutte le
correzioni in un unico rilascio. Fuori perimetro: deposito telematico, notifiche legali, ricerca fascicoli.

## PEC collegate con certezza
- Il numero di ruolo si legge anche nelle forme ministeriali («COMUNICAZIONE 2539/2025/LAV», «RG: 2539 - 2025»,
  «procedimento n. …/…»): prima quasi tutte le PEC della cancelleria risultavano «ruolo assente».
- Il motivo del mancato collegamento dice quale controllo manca (cliente, ufficio o entrambi); la riconvalida dello
  storico riparte con la regola nuova (versione 2). Base: art. 16 D.L. 179/2012; D.M. 44/2011.

## Sentenza: processo automatico con fonte visibile
- Proposte uguali fuse; ogni proposta ha «Visualizza sentenza» con il passo del dispositivo da cui nasce.
- Nei casi certi la liquidazione delle spese e la definizione del fascicolo si registrano da sole (con «Annulla»);
  i casi incerti restano da confermare con il motivo. Lo storico si ricontrolla a lotti. Artt. 91, 92, 93, 132 c.p.c.

## Letture dei documenti
- «Lettura interrotta dopo 3 tentativi»: i riavvii non contano più come tentativi, la lettura procede a turni con
  progresso visibile, un documento guasto si chiude «non leggibile», le letture ferme ripartono da sole.
- Indice Lex: la busta cifrata Atto.enc non è più un errore ma «non applicabile» (buste cifrate per l'ufficio), anche
  negli esiti già registrati.
- Date dei pagamenti e riferimenti non processuali non diventano più udienze o termini; motivi di lettura leggibili.

## Fascicolo
- Profilo procedurale dedotto dai dati certi (sezione, ufficio, registro, atto introduttivo, codice oggetto PST) con
  la fonte visibile, «Cambia profilo» con alternative della stessa materia, riconvalida notturna alle 02:55.
- «Notifiche richieste»: una voce per atto, «Notificato» solo con le prove, mai «da notificare» dopo la sentenza.
- «Parti lette»: niente codice fiscale di persona fisica agli enti, il petitum non è una parte, varianti fuse.
- Rito del lavoro: appello art. 434 c.p.c., art. 417-bis corretto, fasi di udienza e decisione con fonti Normattiva.
- Copertina, viste elenco su telefono, menu e pannelli corretti; chiave della cache dell'elenco con l'archivio.

## Pagine dell'applicazione (tutte le aree)
- Studio: Panoramica, Oggi, Controllo studio, Agenda, Scadenziario, Timesheet, top bar e comandi su telefono.
- Clienti, soggetti, messaggi ed email: errori leggibili, schede su telefono, notifiche push.
- Economia: etichette delle fasi (anche mediazione), calcolo compensi, preventivi, prima nota, recupero crediti.
- Documenti, modelli, redazione, contratti (locazione commerciale L. 392/1978; foro artt. 21 e 447-bis c.p.c.) e sito.
- Ricerca e Lex: pagina «Completamento procedure» collegata, schede normative senza chiavi tecniche, avviso «fonti
  cambiate» non più a ogni ricerca, sigle uniformi in Codici e leggi, danno biologico «Artt. 138 e 139 cod. ass.»,
  registro delle violazioni art. 33 par. 5 GDPR, Regia agentica in italiano.
- Amministrazione: registro attività leggibile, «Automazioni» al posto di «Scheduler», etichette italiane.
- Grafica: pulsanti del design system, spaziature, nessun elemento fuori bordo su telefono.

## Restano da decidere con l'avvocato
Indicati nei registri dell'area con il motivo (valore indeterminabile in compensi, regime fiscale delle bozze,
fascicolo di collaudo in produzione, nome della pagina «Utility», e altri).
