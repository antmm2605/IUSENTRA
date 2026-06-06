# PEC Control Tower e Lex AI

Data di registrazione: 6 giugno 2026.

## Regola madre

Ogni PEC acquisita deve diventare un evento giuridico tracciato. Ogni evento
giuridico può generare, quando serve, scadenza in bozza, evento agenda, task,
bozza notifica o riscontro e prova. Nessuna scadenza viene trattata come termine
legale definitivo finché non risulta confermata dall'avvocato con regola e audit.

## Perimetro attivo

- Repository: `pct.pec_control_tower.PecControlTowerRepository`.
- Database tenant-aware: `pec_control_tower.sqlite` nella cartella email del tenant, con schema PostgreSQL paritario in `pct/sql/20260606_pec_control_tower_postgres.sql`.
- API: `/api/pec/ingest`, `/api/pec/backfill-locali`, `/api/communications`, `/api/deadlines`, `/api/agenda`, `/api/notifications/*`, `/api/audit/<matter_id>`, `/api/calendar/export.ics`.
- Lex: sorgente `pec_control_tower`, strumenti `answer_pec_control_question` e `list_pec_control_events`.
- Test reale generativo: `python scripts/test_pec_control_tower.py --runtime-root <cartella>`.
- Audit sorgenti tenant: `python scripts/audit_lex_tenant_sources.py --data-root data`.

## Cosa viene letto

Il parser legge MIME RFC 822, intestazioni PEC, `daticert.xml`, allegati ZIP e
messaggi `.eml` annidati. Estrae mittente, destinatari, Message-ID, riferimento
al messaggio notificato, ricevuta di accettazione, ricevuta di consegna, mancata
consegna, hash SHA-256, allegati e testo di ricerca.

Per le comunicazioni di cancelleria su udienze non in presenza il presidio legge
anche PDF diretti e PDF compressi in ZIP. Quando `Comunicazione.xml`, corpo PEC
o oggetto indicano udienza da remoto, audiovisiva, videoconferenza, stanza
virtuale, collegamento o strumenti audiovisivi, l'audit deve cercare in allegati
e OCR: link di accesso, piattaforma, ID riunione, codice di accesso, data e ora.
Il link può essere dichiarato utilizzabile solo se il valore estratto coincide
esattamente con la fonte letta; in caso contrario l'interfaccia deve chiedere
verifica sul PDF originale. Se il link non è ancora leggibile ma esiste un
PDF/ZIP collegato, il report deve aprire un warning operativo: il PDF va letto o
acquisito con OCR prima di chiudere il presidio.

Il matcher fascicolo usa dati reali del tenant quando disponibili: numero R.G.,
anno, titolo, oggetto, cliente, controparte, tribunale e riferimenti testuali.
Se la confidenza non basta, crea task di associazione invece di scegliere in modo
silenzioso.

La Control Tower non legge solo il pannello `Scadenze dai PDF`: quel pannello è
un importatore mirato dai documenti del fascicolo. Per Lex le sorgenti operative
restano distinte e tenant-aware: PEC, fascicoli, documenti fascicolo,
scadenziario, agenda, notifiche, prove e Control Tower. Se una risposta PEC
risulterebbe vuota, Lex tenta un backfill idempotente dalla casella PEC reale del
tenant corrente, ordinando dalle PEC più recenti e rispettando un budget di tempo
per non bloccare la chat. Il backfill completo resta disponibile come endpoint
operativo esplicito.

Lo stesso principio vale per il fascicolo attivo: il widget Lex deve pubblicare
`caseId`, `clientId` e percorso pagina, e il backend deve normalizzare anche i
campi JavaScript (`pagePath`, `caseId`). Una sintesi sul fascicolo aperto deve
usare fascicolo, parti, documenti indicizzati, scadenze, agenda, PEC/prove e
moduli economici disponibili nel tenant; se i documenti risultano pronti per
Lex, gli estratti leggibili devono entrare nella risposta quando l'avvocato
chiede documenti chiave, rischi, cosa manca o prossimi passi.

## Avviso automatico PEC

Il valore "comunicazioni richiedono presidio" deve rappresentare solo PEC ancora
da lavorare, non l'intero storico della casella. Il ciclo
`/api/pec/email/acquisisci-locali` procede a blocchi e, per ogni messaggio della
casella PEC che ha identificativo, esito PCT/WARN o segnali PEC, registra una
riga terminale in `pec_local_acquire_items` anche quando:

- il MIME originale non è più disponibile localmente;
- la PEC è già presente nell'audit;
- la scadenza operativa è già presente;
- il termine letto è già scaduto e quindi non deve essere riportato in agenda o
  scadenziario.

Questi stati chiudono il presidio dell'avviso, perché l'avvocato deve vedere
arretrato reale e non PEC storiche già esaminate. Dopo il completamento del
ciclo massivo l'avviso deve scendere a `0 comunicazioni richiedono presidio` e
le esecuzioni successive devono lavorare solo le nuove PEC arrivate dopo
l'ultimo presidio.

Il presidio deve salvare nel database tenant-aware tutto ciò che serve a non
rileggere la stessa PEC dalla casella: MIME originale, hash, allegati,
classificazione, OCR/testo PDF o ZIP, firme, report di validazione, profilo
processuale, eventuale udienza audiovisiva/remota, azioni consigliate, scadenza
o agenda e riga `pec_local_acquire_items`. Se la PEC viene eliminata dalla
casella dopo l'acquisizione, la prova e il ragionamento operativo restano nel DB
audit e nelle sorgenti Lex/RAG del tenant.

## Classi operative

- `CANCELLERIA_PCT`
- `PROVVEDIMENTO_GIUDIZIARIO`
- `NOTIFICA_CONTROPARTE`
- `ATTO_AMMINISTRATIVO_PA`
- `ENTE_RICHIESTA_RISCONTRO`
- `ATTO_TRIBUTARIO_RISCOSSIONE`
- `DIFFIDA_MESSA_IN_MORA`
- `CONTRATTO_DISDETTA_RECESSO`
- `CLIENTE_DOCUMENTI`
- `PEC_OUTBOUND_PROOF`
- `UNKNOWN_LEGAL_RISK`

Le fonti normative mostrate sono cornici operative da verificare sul caso
concreto: L. 53/1994, DPR 68/2005, CAD art. 48, regole tecniche PCT e norme
specifiche dell'atto quando emergono dal contenuto.

## Domande Lex coperte

Lo script di generazione verifica che Lex risponda correttamente a:

- Quali PEC ricevute oggi generano scadenze?
- Quali notifiche verso enti o controparti devo fare?
- Quali PEC inviate non hanno ancora ricevuta di consegna?
- Quali termini sono stati calcolati ma non confermati?
- Quali atti sono arrivati da cancelleria?
- Quali comunicazioni PA richiedono risposta?
- Quali notifiche sono fallite?
- Qual è la prova completa di questa notifica?
- Chi ha confermato la scadenza e con quale regola?
- Quale fascicolo rischia una decadenza?

## Garanzie

- Audit append-only con catena HMAC.
- Scadenze sempre `draft_pending_confirmation` finché non confermate.
- Nessun invio PEC automatico dagli endpoint.
- Prova notifica ricostruita per Message-ID con accettazione e consegna.
- Orari visibili convertiti in `Europe/Rome` nelle risposte Lex.
- Output script forzato UTF-8 su Windows.
- Isolamento tenant verificabile: ogni repository filtra per `tenant_id` e
  l'audit read-only segnala eventuali righe Control Tower appartenenti ad altro
  studio.
