# Fase 11 — Presidio economico unico del fascicolo

## Obiettivo

Rendere **Presidio economico** l'unico punto operativo nel fascicolo per
incarico, valore, contributo unificato, ricevuta di pagamento, spese,
liquidazioni, parcelle, incassi e letture economiche dei provvedimenti. Il
Quadro fascicolo resta una sintesi navigabile: non deve duplicare moduli o
regole.

## Analisi prima della modifica

- Il riepilogo `paymentSummary` è già la fonte SQL tenant-aware per le voci
  economiche; l'editor React salva tramite l'API esistente e mantiene la
  parità SQLite/PostgreSQL. Non va sostituito né ricostruito da JSON.
- Il contributo unificato è usato anche dal deposito e dalle relative
  validazioni. Rimane quindi una riga autonoma del medesimo presidio e non
  può essere rimosso come presunto doppione.
- Il controllo sentenze/provvedimenti legge i relativi audit ed eventi
  economici già prodotti dal runtime. I suoi importi e avvisi devono essere
  mostrati nello stesso presidio, non in un pannello concorrente.
- La precedente sezione React dedicata alle sentenze non era più montata;
  lasciare codice morto e una seconda etichetta alimentava l'impressione di
  due controlli diversi sullo stesso dato.

## Implementazione eseguita

1. Il Presidio del fascicolo contiene ora la card **Presidio economico** con
   due comandi reali: apertura/modifica del controllo e calcolo del contributo
   unificato.
2. Le card Contributo e Provvedimenti economici aprono lo stesso controllo,
   senza perdere stati, ricevute o fonti già collegate.
3. La modale unica include le evidenze da provvedimenti e l'azione per
   aprire i documenti sorgente nel lettore interno.
4. È stato eliminato soltanto il componente dedicato non montato; runtime,
   repository, API, controlli deposito e dati di pagamento esistenti.

## Verifiche eseguite prima del rilascio

- Test statico React: una sola superficie operativa, entrambe le card
  instradano al presidio, contributo e fonti documentali restano disponibili.
- Test runtime sentenze e test del bridge per importi, avvisi, fonti leggibili
  e parità dati: `15 passed`.
- Test mirati del presidio, audit documento e lettore: `3 passed`.
- Typecheck TypeScript e build Vite completati senza errori.
- Prova reale su `127.0.0.1:8080`, fascicolo `DC5BF1DB`: il comando **Apri
  presidio economico** ha mostrato contributo, ricevuta, spese, liquidazione,
  parcella e le evidenze dai provvedimenti; **Apri documenti sorgente** ha
  chiuso la modale e portato alla sezione documenti; **Calcola contributo
  unificato** ha aperto il calcolo interno. Layout desktop, hover e focus da
  tastiera sono risultati leggibili; console senza errori.

## Rilascio

Il commit, il push dei due branch gemelli e il deploy Hetzner seguono questa
verifica locale. Il rilascio è registrato come concluso solo dopo il controllo
del container applicativo unico e della readiness pubblica.
