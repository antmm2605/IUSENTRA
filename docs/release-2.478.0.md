# IUSENTRA 2.478.0 — correzioni della riverifica a vista e del collaudo dei motori (03/11/2026)

Dopo il deploy della 2.477.0 ogni difetto registrato è stato ricontrollato a vista su PC e telefono in produzione
(registri aggiornati in `docs/verifica_visiva_2026-11-02/`), la catena delle notifiche legali è stata verificata e il
collaudo dei motori ha fotografato sul server letti, da leggere ed errori di ogni lettore.

## Sentenze dalle PEC di cancelleria
- Le comunicazioni di cancelleria con allegati (IndiceBusta.xml + Comunicazione.xml) non sono più scartate come
  ricevute di deposito: la sentenza contenuta nello .zip e l'.eml della comunicazione entrano nel fascicolo; le PEC già
  scartate rientrano una volta in coda (regole versione 2), senza doppioni.
- Numero di ruolo letto anche nelle formule per esteso («Numero di Ruolo generale», «R.G.L.», «n. … R.G.»); riconvalida
  dello storico con la regola versione 3 (tre controlli invariati).

## Sentenza automatica (decisione dell'avvocato del 03/11/2026)
- Il lettore delle proposte esamina anche gli allegati delle PEC collegate.
- Definizione del fascicolo automatica quando la sentenza decide la causa e il procedimento coincide (artt. 132 e 92
  c.p.c.), con «Annulla»; credito delle spese automatico solo se certo (artt. 91 e 93 c.p.c.), altrimenti da confermare.
- «Visualizza sentenza» apre il documento sul passo del dispositivo evidenziato; citazioni su parole intere.
- Dopo la sentenza: fase «decisa», prossima udienza solo futura, niente «discussione» con trattazione scritta (art.
  127-ter c.p.c.).

## Motori e letture (collaudo)
- Eventi di fascicoli non più esistenti chiusi invece di ritentati senza fine; prenotazioni prorogate nei giri lunghi.
- Una lettura in coda conserva il suo posto; ogni notte si rimettono in coda i fascicoli mai verificati o fermi da oltre
  24 ore; un giro interrotto non blocca più.
- OCR anche per i documenti arrivati da portale e PEC senza testo, una sola volta; censimento dei lettori senza
  doppioni e lettori su richiesta non contati come «da leggere».
- Presidio PEC: posta nuova riconosciuta dal catalogo SQL della casella (caselle mai esaminate).
- Strumento di collaudo `deploy/hetzner/collaudo_motori.py` e workflow di profilazione di ricerca e notifiche.

## Notifiche legali
- «Da notificare» con relata depositata diventa «Da verificare»; prove di una diffida non chiudono più l'obbligo del
  ricorso; sentenza notificata «Da verificare» (decorrenza del termine breve, artt. 285, 325 e 326 c.p.c.).
- Nomi italiani dei pubblici elenchi; filtro «Non PEC» unico.

## Velocità
- Ricerca legale: il PDF ufficiale si cerca solo tra le fonti (mai tra i documenti degli studi), vettore della domanda
  calcolato una volta, riepiloghi riusati per 2 minuti, tetto di 6 s ai contesti ufficiali.
- Export «CSV economico» dal riepilogo consolidato; cabina telematica con cache stabile; 502 alla prima apertura del
  fascicolo: keepalive di Caddy sotto quello di Gunicorn.
- Conteggi delle scadenze aperti uguali in Panoramica, Statistiche, Calendari e Scadenziario.

## Interfaccia e testi
Correzioni grafiche e di testo in tutte le aree (tabelle, etichette tagliate, chiavi tecniche, accenti, uffici
giudiziari proponibili nei modelli, controlli notturni delle fonti pianificati alle 06:05).
