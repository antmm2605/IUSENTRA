# Fase 13, audit veritiero nel presidio del fascicolo

## Perimetro di questo incremento

Questo incremento corregge una rappresentazione fuorviante del registro audit
nel fascicolo React. Non dichiara esauriti gli altri obiettivi della Fase 13
del programma: conserva il perimetro residuo per gli incrementi successivi.

## Problema osservato sulla copia reale

Nel fascicolo `DC5BF1DB`, il presidio era aperto prima del caricamento lazy
dell'audit e mostrava `0` oppure **Nessuna evidenza**. Aprendo la sezione
**Audit** nella stessa copia locale, il registro operativo restituiva invece
62 eventi, tra cui consultazioni e download di documenti. Lo zero non era un
esito del registro, ma il valore di un payload non ancora richiesto.

## Regola introdotta

Il presidio ora distingue esplicitamente gli stati del caricamento:

1. prima della lettura: **Da caricare**, con il comando che spiega che il
   conteggio deriva dal registro operativo e probatorio;
2. durante la lettura: **Caricamento…**;
3. in caso di errore: **Da riprovare**, senza dichiarare assenza di prove;
4. soltanto a caricamento concluso: conteggio reale oppure **Nessuna
   evidenza** se il registro ha effettivamente zero eventi.

La navigazione del fascicolo segue la stessa regola: mostra `—`, `…` o `!`
finché il conteggio non è disponibile, quindi il numero reale. La sezione
Audit rende esplicito l'errore e invita al nuovo caricamento; non usa più uno
stato vuoto come esito implicito.

## Dati, sicurezza e audit

- Nessuna tabella, migrazione, repository o endpoint è stato modificato.
- Il registro SQL tenant-aware resta l'unica fonte del conteggio; non viene
  introdotto alcun fallback JSON.
- RBAC, permessi e tracciamento degli eventi restano invariati.
- La correzione non scrive dati nel fascicolo: la verifica ha solo letto la
  sezione Audit già disponibile all'utente autorizzato.

## Verifiche eseguite

- Test React mirato: il presidio non può dichiarare assenza di evidenze prima
  dello stato `loaded`; navigazione e sezione Audit condividono lo stato lazy.
- Typecheck TypeScript e build Vite completati.
- Prova reale visibile su `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`:
  prima dell'apertura la card mostrava **Da caricare** e la navigazione `—`;
  dopo il click materiale su **Audit**, la UI ha visualizzato il registro
  operativo con 62 eventi e la navigazione è diventata **Audit 62**.

## Rilascio

Il commit, il push dei branch gemelli e il deploy Hetzner seguono i gate
mirati e la prova locale. Il rilascio sarà registrato soltanto dopo la
verifica del commit remoto, del container applicativo unico e della readiness
pubblica.
