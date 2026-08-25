# Fase 9 — Audit di implementazione DMS, 25/08/2026

- Stato: fase aperta fino ai gate finali di test, commit e distribuzione.
- Ambito: fascicolo `DC5BF1DB`, copia locale reale `http://127.0.0.1:8080`.
- Fonte di verità: SQLite tenant-aware; schema PostgreSQL aggiornato in parità.

## Correzione applicata

Il resolver `2026.08.25.catalogo-fascicolo.v14` determina anzitutto
l'identità del documento da formule forti del contenuto indicizzato. I
richiami a CTU, contributo, termini, rito o provvedimenti restano segnali
procedurali distinti: non possono più sostituire tipo, sezione o ruolo del
documento.

Le nuove evidenze SQL sono `document_identity` e `procedural_signal`. Il
payload React le presenta separatamente nel disclosure **Prova e fonti**,
insieme alle fonti normative in denominazione leggibile. L'estratto viene
minimizzato alla sola formula identificativa: non duplica nell'interfaccia
codici fiscali, PEC, nominativi o testo integrale. Il pulsante **Apri la prova
nel lettore** conserva il documento originale nel lettore interno autorizzato.

Una lettura ordinaria del catalogo (`process=false`) non crea più job in coda:
soltanto il comando esplicito di aggiornamento avvia una nuova elaborazione.

## Riscontro sul dato controllato

Nel fascicolo controllato il documento nominato `Note conclusive Alessi
Robertino.pdf.p7m` è stato ricalcolato come **Note conclusionali**; la prova
mostra la formula minimizzata letta dal contenuto, non dal nome file. I
richiami a CTU e gli altri presìdi restano visibili sotto **Segnalazioni
procedurali** e non alterano l'identità.

Il comando reale **Aggiorna catalogazione** è stato cliccato nella pagina
locale e ha restituito il messaggio visibile *Catalogazione aggiornata: 20
documenti elaborati.*. Il server ha registrato il `POST`
`/api/v1/ui/fascicoli/DC5BF1DB/catalogazione-documentale/aggiorna` con esito
HTTP 200. Il catalogo risultante usa la versione resolver v14 per tutti i 20
documenti e non lascia in revisione un documento a causa del solo presidio.

Il catalogo ha mostrato identità contenuto-prima per due **Istanze di
trattazione scritta**, una **Nota di deposito**, un **Decreto di fissazione
udienza** e una voce **Istanze e conclusioni**. Per il decreto, **Prova e
fonti** ha mostrato la formula `Decreto di fissazione udienza`, i segnali
procedurali separati e cinque fonti ufficiali; il relativo pulsante ha aperto
una sola preview interna e la chiusura ha rimosso correttamente lettore e
iframe dalla pagina.

Sono stati inoltre verificati con click reale:

1. apertura di **Prova e fonti**;
2. separazione visibile fra identità, segnali e fonti;
3. apertura del documento nel lettore interno IUSENTRA;
4. apertura di **Correggi catalogo**, con i valori correnti modificabili;
5. salvataggio di una correzione nel fascicolo di prova `2DE106E6`, audit e
   persistenza `manual_override` dopo il refresh del resolver;
6. scroll completo desktop, tablet e mobile, compresi hover e focus da
   tastiera del controllo di correzione.

Non sono stati modificati file originali, firme, depositi, notifiche o
conferme manuali dell'avvocato.

## Guardrail eseguiti

- test mirati del catalogo, pipeline, schema/API e interfaccia React,
  inclusi il guardrail contro la sostituzione dell'identità con il presidio;
- controllo sintattico Python del pipeline e resolver: superato;
- controllo TypeScript senza emissione: superato;
- migrazione SQLite verificata con le nuove evidenze;
- parità PostgreSQL verificata in contenitore isolato PostgreSQL 16 e rimosso
  al termine;
- controllo `git diff --check`: superato;
- rebuild della copia Docker locale, applicazione `2.278.77` healthy su
  `http://127.0.0.1:8080/api/pronto`.

## Gate residui

- verifica prestazionale finale sul build corrente;
- commit, push dei due branch gemelli, deploy Hetzner, controllo del singolo
  contenitore `iusentra-app`, health pubblico e igiene della cache Docker;
