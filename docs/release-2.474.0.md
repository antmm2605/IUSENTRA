# 2.474.0 — Provvedimenti del giudice in tutte le materie, decreti 127-ter senza data, passaggi visibili e regole dello studio

- **Provvedimenti del giudice** (`pct/provvedimenti/`): decreti, ordinanze, verbali e sentenze ricevuti per PEC o letti
  nel fascicolo si trasformano in proposte da confermare: udienze e modalità (presenza, remoto, cartolare, camera di
  consiglio), termini scritti dal giudice o di legge (tabella versionata `pct/data/provvedimenti_regole_v2026_11.json`
  con norme e fonti Normattiva consultate il 02/11/2026), adempimenti, attese. Date relative calcolate con il motore dei
  termini esistente (sospensione feriale, festivi, a ritroso). Le ambiguità diventano domande all'avvocato; nessun
  doppione. Coperti: fissazione e rinvio, 127-ter e 127-bis, art. 415 c.p.c., ammissione testi e CTU, 171-ter, art.
  189, decreto ingiuntivo, sentenze, riserva, 473-bis, trattazione tributaria e amministrativa, citazione penale.
- **Decreti 127-ter senza data** («sino alla data della predetta udienza», caso reale di cinque decreti del
  02/11/2026): termine perentorio per le note alla data dell'udienza già fissata, alle 09:30 se il giudice lo chiede;
  udienza cartolare alla conferma; elenco delle note (cinque indicazioni, sole istanze e conclusioni, prova della
  notifica se il cliente è ricorrente e la resistente non è costituita, decisione entro 30 giorni).
- **Passaggi visibili e regole dello studio** (`pct/passaggi/`, API `/api/v1/ui/fascicoli/<id>/passaggi`,
  `/api/v1/ui/regole-studio`): nella Lettura del fascicolo «Come ha lavorato il software» mostra ogni passaggio con
  regola, norma, prova e dati; «Correggi la regola» registra una regola dello studio (fascicolo, giudice, ufficio o
  tutti i casi) applicata ai casi successivi; Impostazioni › Regole dello studio. Vincoli di legge invalicabili: termini
  perentori (art. 153 c.p.c.) e deposito non autonomo (art. 196-quater disp. att. c.p.c.).
