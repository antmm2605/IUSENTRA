# Fase 14, verifica interattiva del presidio fascicolo

## Obiettivo del gate finale

Questo gate conclude la sequenza di miglioramenti del fascicolo con una prova
materiale dei controlli che devono guidare l'avvocato. Non considera una card
un risultato: ogni esito deve portare al dato verificabile e modificabile nel
contesto del fascicolo.

## Prova reale eseguita

Sulla copia locale `http://127.0.0.1:8080` è stato verificato il fascicolo
`474DC848` nel presidio:

- le sette righe **Conformità e qualità** sono link accessibili, con etichetta
  esplicita e destinazione coerente: dati principali, cliente, soggetti,
  documenti, udienze/scadenze, controllo di conformità e sincronizzazione
  portale;
- i badge **OK** e **Verifica** sono leggibili per intero, senza testo
  sovrapposto o troncato;
- il click materiale su **Dati principali** ha aperto il pannello **Profilo
  fascicolo**, aggiornato l'URL a `#profilo` e mostrato il comando **Modifica
  dati fascicolo**;
- la stessa mappa è protetta dal test React già presente: i link richiamano
  `openQualityDestination`, aprono il pannello, lo rendono visibile e
  trasferiscono il focus alla relativa intestazione.

La prova complementare sul fascicolo `DC5BF1DB` ha confermato il passaggio
onesto dell'audit da **Da caricare** a **Audit 62** dopo il click sulla
sezione, senza presentare uno zero provvisorio come dato reale.

## Guardrail e limiti espliciti

- Il gate è di interazione e qualità visiva: non modifica dati, permessi,
  classificazioni, scadenze o documenti.
- L'apertura iniziale mostra lo stato di caricamento finché la richiesta reale
  del fascicolo non è terminata; le azioni non vengono esposte come disponibili
  prima che i dati siano presenti.
- Restano validi i gate di dominio già eseguiti nelle fasi precedenti; questo
  documento non sostituisce prove operative di deposito, firma o notifica.

## Rilascio

Il rilascio di questo gate viene registrato con commit, sincronizzazione dei
branch gemelli, deploy Hetzner, container applicativo unico e readiness
pubblica. Nessuna voce è considerata chiusa senza tali riscontri.
