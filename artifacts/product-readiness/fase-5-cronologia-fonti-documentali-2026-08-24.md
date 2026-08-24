# Fase 5 — Cronologia della pratica e fonti documentali

Data: 24/08/2026
Perimetro: cronologia delle attività processuali del fascicolo React.

## Obiettivo operativo

Separare con chiarezza le attività create e gestibili dallo studio dalle
rilevazioni derivate dal contenuto di un documento indicizzato. Un passaggio
letto da un atto non è una bozza dell'avvocato e non deve poter essere posto
in attesa, salvato, eliminato o trasformato silenziosamente in un esito.

## Implementazione

- Le righe con `sourceIsDerived` o `readOnly` mostrano un titolo professionale
  del tipo `Udienza rilevata dal documento`, il badge `Rilevazione` e una
  microcopy esplicita: la fonte va consultata prima di agire.
- La descrizione tecnica duplicata dell'estrazione non viene più ripetuta nel
  corpo della cronologia. La riga espone invece una sintesi leggibile e la
  scheda `Fonte dell'informazione`, con documento originale, passaggio letto e
  comando `Apri fonte` nel lettore interno IUSENTRA.
- Per tali righe non vengono renderizzati selettore di esito, `Salva` o
  `Elimina`. Il backend già impedisce le mutazioni sulle attività derivate;
  l'interfaccia ora rende visibile e coerente lo stesso vincolo.
- Il modulo `Aggiungi attività` mantiene i normali stati per un'attività
  manuale: non è stato eliminato né reinterpretato come evento documentale.
- Non sono stati modificati deposito telematico, firma, busta, notifica, SQL,
  API, classificazione documentale o connettori PST/PolisWeb.

## Verifiche tecniche

- Test React mirato sulla fonte documentale nella cronologia: superato.
- TypeScript senza errori: superato.
- Suite frontend di contratti, presidi, design system, App V2 e copertura UI:
  superata.
- Build Vite di produzione: superata.
- `git diff --check` sul contenuto predisposto per il commit: superato.

## Prova reale locale

Nella copia Docker reale `http://127.0.0.1:8080`, fascicolo `DC5BF1DB`, è
stata aperta materialmente la sezione `Attività processuali`. Le rilevazioni
di udienza mostrano titolo, badge, fonte e passaggio letto senza comandi di
modifica. La scheda della fonte conserva il comando `Apri fonte` verso il
lettore interno. Il modulo manuale rimane disponibile separatamente in alto.

Non sono stati creati, salvati, cancellati o modificati eventi; non sono stati
avviati firma, deposito, notifica o invio PEC. La prova è limitata alla
presentazione e all'integrità delle azioni della cronologia; deploy e verifica
post-deploy restano da eseguire prima della chiusura della fase.
