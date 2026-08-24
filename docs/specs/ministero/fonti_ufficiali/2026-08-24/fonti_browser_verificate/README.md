# Fonti ufficiali verificate con browser reale

Questa cartella non sostituisce le copie scaricate con SHA-256 del manifest
principale. Registra fonti ufficiali che il fornitore rende disponibili
correttamente al browser reale ma blocca ai downloader automatici. Un job non
può quindi interrogarle né assumerne la disponibilità: deve richiedere la
revisione della regola.

| ID | Fonte e URL | Verifica materiale del 24/08/2026 | Regola di utilizzo |
| --- | --- | --- | --- |
| `browser:acf-normativa-2026` | Consob/ACF, [Normativa ACF](https://www.acf.consob.it/normativa/normativa-acf/-/asset_publisher/3ZtmdCgqd1re/content/aggiornamento-area-riservata?inheritRedirect=false) | Nel browser integrato è stata visualizzata la sezione «Normativa ACF», con normativa europea, nazionale primaria e regolamenti/disposizioni Consob; sono presenti la delibera Consob n. 22721 del 1° giugno 2023 e il collegamento al testo integrato del regolamento. Il collegamento ufficiale di download esposto dalla pagina è `/documents/20184/0/Regolamento+ACF+-integrato+con+delibera+22721/8a8168e2-c220-4d71-9d8e-e338ef6fbab2`. | Fonte procedurale per il profilo `BAN`. Non viene usata dai job HTTP. Un controllo periodico deve richiedere un browser reale; se la pagina non espone più i contenuti dichiarati, tutte le regole ACF dipendenti passano a revisione umana. |

La pagina vecchia «quando e come fare ricorso» e i suoi download sono
esplicitamente esclusi: l'acquisizione automatica ha prodotto un avviso di
manutenzione/barriera, non il contenuto procedurale. Questa distinzione evita
che il catalogatore attribuisca certezza a una fonte soltanto apparente.
