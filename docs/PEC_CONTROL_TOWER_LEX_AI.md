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
- API: `/api/pec/ingest`, `/api/communications`, `/api/deadlines`, `/api/agenda`, `/api/notifications/*`, `/api/audit/<matter_id>`, `/api/calendar/export.ics`.
- Lex: sorgente `pec_control_tower`, strumenti `answer_pec_control_question` e `list_pec_control_events`.
- Test reale generativo: `python scripts/test_pec_control_tower.py --runtime-root <cartella>`.

## Cosa viene letto

Il parser legge MIME RFC 822, intestazioni PEC, `daticert.xml`, allegati ZIP e
messaggi `.eml` annidati. Estrae mittente, destinatari, Message-ID, riferimento
al messaggio notificato, ricevuta di accettazione, ricevuta di consegna, mancata
consegna, hash SHA-256, allegati e testo di ricerca.

Il matcher fascicolo usa dati reali del tenant quando disponibili: numero R.G.,
anno, titolo, oggetto, cliente, controparte, tribunale e riferimenti testuali.
Se la confidenza non basta, crea task di associazione invece di scegliere in modo
silenzioso.

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
