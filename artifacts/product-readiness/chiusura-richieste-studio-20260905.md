# Chiusura delle richieste dello studio — 05/09/2026

## Stato effettivo

Il lavoro complessivo è aperto. Il registro mediazione verificato non equivale
alla consegna della mediazione nel fascicolo né al completamento del programma
originale in 14 fasi. Questo registro raccoglie anche le richieste precedenti
che non vanno perse concentrandosi sull'ultima segnalazione.

| Perimetro richiesto | Evidenza disponibile | Passaggio necessario ancora aperto |
| --- | --- | --- |
| Registro mediazione, sedi, filtri territoriali, scheda inline, siti cliccabili, velocità | Inventario SQL di 491 organismi attivi e 6.673 sedi; prova reale locale su 55 organismi; riscontro positivo dell'utente | Ultima riconciliazione documentazione e verifiche del deploy |
| Portali e modulistica degli organismi | Censimento pubblico avviato; 422 verifiche sito registrate su 491 organismi attivi | Terminare acquisizione, distinguere risorse pubblicate da canali verificati, collegare risorse e moduli alla UI |
| Procedimento di mediazione nel fascicolo | Registro organismi e calcolatore esistenti; nessun flusso completo individuato nel componente Fascicoli | Fonti ufficiali aggiornate, modello e repository tenant SQL, API, procedimento React, prove e audit; portale e preparazione PEC senza invio automatico |
| Documenti completi PST nel wizard e nel fascicolo | Ripristino e confronti precedenti con baseline Local Signer 1.6.116 documentati | Riconciliare catalogo e allegati sul caso reale fino al conteggio finale; preservare accesso rapido e indicatori di attesa |
| Attività processuali e acquisizioni tecniche | Caso reale 0D4A4802 sul server: 37 attività e falsa scadenza identità; precedenti fix locali non tutti commitati | Correggere provenienza/stati, falsi termini e tracciamento tecnico senza cancellare attività manuali o prove |
| Condivisioni clienti e altre correzioni UI precedenti | Modifiche locali e cinque sorgenti server ancora fuori commit | Revisione puntuale, prova reale, integrazione nei commit senza sovrascriverle |
| Programma originario fasi 4–14 | Programma del 23/08/2026 e report successivi con perimetri diversi | Matrice capacità/evidenze coerente con il programma originale; i soli report UI non attestano SSO, DLP, HA o tutte le altre capacità |
| Backup, commit, branch gemelli, deploy, qualità e performance | 7f3030162 sui branch gemelli; gate richiesti superati; backup preventivo verificato; unico iusentra-app healthy in produzione | Integrare il codice precedente ancora non commitato e mantenere allineamento durante la consegna restante |

## Vincoli operativi

- Non modificare per rifiniture la logica funzionante di wizard, deposito,
  notifiche, firma singola e multipla. Le sole correzioni richieste sul recupero
  documenti devono preservare i contratti della versione verificata.
- Non eseguire PEC, depositi o firme reali per un collaudo senza un'operazione
  concretamente richiesta e verificata. Nessun PIN o credenziale nei report.
- Nessun reset del repository server che perda i sorgenti precedenti.
- Ogni cambiamento percepibile richiede prova reale locale sulla porta 8080,
  oltre alla verifica sul caso di produzione quando coinvolto.
- Nessun dato ministeriale assente viene inventato; una risorsa individuata
  sul web non è automaticamente un canale di deposito confermato.
- Lo spegnimento del PC non fa parte della richiesta corrente.

## Rilascio registro già eseguito

- Versione 2.278.86; commit 7f3030162712d9fd7d2e74a4d860f0d666f712f9.
- Backup preventivo con retention di una copia verificato prima del deploy:
  due database, source_of_truth=sqlite, circa 11,7 GB.
- Importato in produzione esclusivamente il registro ministeriale aggiornato
  e il repository pubblico sedi; nessuna altra tabella normativa cambiata.
- Deploy con profilo deploy/hetzner: unico container applicativo iusentra-app,
  healthy; /api/pronto risponde con versione 2.278.86.
- Diff dei cinque sorgenti server precedenti identico prima/dopo il deploy;
  questa conservazione non equivale ancora alla loro integrazione in Git.
- Rimossi circa 7 GB di cache di compilazione Docker rigenerabile; nessun
  volume applicativo cancellato. Nessuno snapshot temporaneo residuo rilevato.

Questo registro va aggiornato con prove concrete, non con percentuali stimate.
