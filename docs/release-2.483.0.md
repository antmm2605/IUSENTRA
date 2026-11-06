# Release 2.483.0 — altri casi di notifica dovuta, notifiche a cura dell'ufficio, portale clienti senza codice nei link

Richieste dell'avvocato del 06/11/2026: completare i casi di notifica che nascono dalle comunicazioni ricevute, in tutte
le materie; correggere il codice del cliente nei link del portale.

## Notifiche dovute riconosciute nei provvedimenti

Il termine è quello che il giudice scrive nel provvedimento; la regola di legge dà codice, atti, destinatari e norme.
Se la data non è leggibile, il software chiede all'avvocato di indicarla: nessuna data indovinata.

1. **Integrazione del contraddittorio**: art. 102 c.p.c., art. 49 c.p.a., art. 58 D.Lgs. 175/2024.
2. **Rinnovazione della notificazione**: art. 291 c.p.c., art. 44 c.p.a. **Rinnovazione della citazione nulla**: art. 164 c.p.c.
3. **Chiamata in causa del terzo**: art. 269 c.p.c. Nella scheda: almeno 120 giorni liberi prima dell'udienza differita
   (art. 163-bis); deposito della citazione notificata entro il termine dell'art. 165. La «dichiarazione di terzo» del
   pignoramento presso terzi (art. 547 c.p.c.) non è una chiamata in causa.
4. **Decreto cautelare inaudita altera parte**: art. 669-sexies c.p.c.; termine non superiore a otto giorni, triplicato
   se la notifica va eseguita all'estero.
5. **Opposizioni nell'esecuzione**: artt. 615, 617, 618 e 619 c.p.c.; i creditori di regola presso il difensore del
   processo esecutivo.
6. **Penale, atti dello studio**: costituzione di parte civile fuori udienza (artt. 78 e 79 c.p.p.) e richiesta di
   incidente probatorio (artt. 395 e 396 c.p.p.). Sono riconosciute dalla ricevuta di deposito. Le date sono prudenziali
   perché la legge non fissa giorni; la notifica si fa a cura del difensore (art. 152 c.p.p.).

## Notifiche a cura dell'ufficio

Per questi casi nessun termine a carico dello studio: c'è un avviso di attesa da verificare.

1. **Ordinanza che dispone l'incidente probatorio**: l'avviso lo fa notificare il giudice almeno due giorni prima
   (art. 398 c.p.p.).
2. **Ricorso per la liquidazione giudiziale**: ricorso e decreto di convocazione li notifica l'ufficio all'indirizzo PEC
   del debitore. Se la notifica non riesce, la esegue il ricorrente (art. 40 D.Lgs. 14/2019).

## Lettura del dispositivo

Nel capo «FISSA l'udienza del … e il termine perentorio fino al … per la notificazione» (formula degli artt. 618 e 619
c.p.c.) si legge la data del termine. Prima si leggeva solo quella dell'udienza (`pct/provvedimenti/ancore.py`).

## Portale clienti

Il link per scaricare un documento non contiene più il codice di accesso del cliente. Il codice finiva nei registri del
server, nella cronologia del browser e nell'intestazione Referer. Il cliente è riconosciuto dalla sessione del portale,
che si rinnova a ogni apertura (`web/services/react_client_portal_bridge.py`, `frontend/src/clientPortalData.ts`).

## Casella PEC in sola lettura

Il controllo delle PEC di cancelleria apriva la casella in scrittura: scaricando i messaggi li segnava come letti sul
server PEC dello studio. Ora la apre in sola lettura, come la sincronizzazione delle caselle (`pct/polling_depositi.py`).

Norme nuove nel registro, testo vigente letto dall'archivio Normattiva del software il 06/11/2026: artt. 79, 396 e 398
c.p.p. (`pct/procedura_fasi/fonti_notifiche.py`).

Test: `tests/test_email_client.py` (casella in sola lettura), `tests/test_notifiche_obblighi.py` (casi nuovi, falsi positivi dalle PEC reali, notifiche a cura dell'ufficio),
`tests/test_client_portal_api.py` (scarico con la sessione, negato senza).
