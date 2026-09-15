# Archivio letture e presìdi: lavoro da completare e verificare

Aggiornato: 15/09/2026.

## Regola di sicurezza dati

La sincronizzazione locale/produzione riguarda solo codice, commit, versione e
container. Non si copiano dati di produzione sulla macchina locale: niente
database, documenti fascicolo, allegati PEC, volumi, dump o backup.

## Obiettivo

La catena deve funzionare così:

1. il motore documenti legge i documenti del fascicolo solo quando sono nuovi o
   cambiati;
2. il motore PEC legge PEC e allegati solo quando sono nuovi o cambiati;
3. entrambi scrivono nell'archivio `letture_fatti`;
4. l'archivio fonde i fatti equivalenti, così PEC e documento che riportano la
   stessa informazione diventano un solo fatto canonico con più fonti;
5. i presìdi ricevono o consultano solo l'archivio, senza rileggere file o PEC;
6. i presìdi che scrivono nel proprio registro confermano la consegna in
   `letture_consegne`, così il fatto non viene riproposto e non nascono doppioni;
7. a fascicolo invariato il ciclo resta `fermo` e non apre file.

## Presìdi da coprire

- Agenda: scrive udienze lette e conferma la consegna.
- Scadenziario: scrive termini e costituzioni e conferma la consegna.
- Calendario: consulta agenda/scadenziario alimentati dall'archivio.
- Presidio del fascicolo: consulta date, ruoli, prove di notifica ed eventi.
- Catalogo documentale fascicolo: consulta segnali documentali dall'archivio.
- Lettura fascicolo: consulta l'archivio per sintesi e cronologia.
- Presidio economico: consulta importi letti.
- Contesto economico: consulta importi ed eventi economici per regia e Lex.
- Fatture/proforme: consulta importi letti per proposte economiche.
- Presidio notifiche: consulta prove di notifica riconosciute nel contenuto.
- Dati del fascicolo: consulta i ruoli letti.
- Cronologia: consulta eventi letti dalle PEC.

## Implementazione prevista

- Aggiungere una vista canonica dei fatti letti che fonda informazioni
  equivalenti, senza cancellare i fatti grezzi utili all'audit.
- Usare la vista canonica nelle consegne ai presìdi e nei riepiloghi
  dell'archivio.
- Censire tutti i presìdi dichiarando categorie, campi e modo operativo
  (`scrive` o `consulta`).
- Correggere l'audit della catena perché i presìdi consultivi non risultino
  falsamente "da consegnare".
- Aggiungere test anti-doppione e anti-rilettura.
- Eseguire verifica locale, commit/push sui due branch, deploy Hetzner e
  verifica produzione.

## Criteri di accettazione

- Due fonti diverse con stessa udienza/termine producono un solo fatto canonico.
- Agenda e scadenziario non duplicano mai righe già presenti o già consegnate.
- Un secondo giro su fascicolo invariato non allinea inventario e non legge file.
- Lo script `scripts/verifica_catena_letture.py` mostra presìdi consultivi come
  serviti dall'archivio e presìdi che scrivono con conteggi di consegna reali.
- Locale e produzione restano sullo stesso commit e sulla stessa versione.
