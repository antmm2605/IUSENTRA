# Audit fonti Cartabia e processo telematico

Ultimo aggiornamento: 2026-05-12

## Regole coperte da fonte ufficiale

- Civile ordinario, semplificato, esecuzioni, cautelari e monitori: `CARTABIA-CIVILE-DLGS-149-2022`, `PST-DEPOSITO-ATTI-GIUDIZIARI`, `PST-DOCUMENTAZIONE-TECNICA`.
- Famiglia, minori e persone: `CARTABIA-CIVILE-DLGS-149-2022`, `PRIVACY-GDPR-GARANTE`, `PST-DEPOSITO-ATTI-GIUDIZIARI`.
- ADR, mediazione e negoziazione: `CARTABIA-CIVILE-DLGS-149-2022`, `MEDIAZIONE-DLGS-28-2010`.
- Penale e PDP: `CARTABIA-PENALE-DLGS-150-2022`, `PDP-SPECIFICHE-TECNICHE-2023`.
- Tributario e PTT/SIGIT: `PTT-SPECIFICHE-TECNICHE-2021`.
- Amministrativo e PAT/SIGA: `PAT-REGOLE-TECNICHE-2021-2025`.
- Studio interno, privacy, mandato e revisione professionale: `PRIVACY-GDPR-GARANTE`, `CNF-DEONTOLOGIA-PROFESSIONALE`.

## Fonti ufficiali registrate

I record completi sono in `docs/legal_sources/cartabia_sources.jsonl`.

- Normattiva: D.Lgs. 149/2022, D.Lgs. 150/2022, D.Lgs. 28/2010.
- Ministero della Giustizia / PST / DGSIA: deposito atti giudiziari, documentazione tecnica, PDP.
- Giustizia Amministrativa: Processo Amministrativo Telematico.
- Giustizia Tributaria: Processo Tributario Telematico.
- Garante Privacy: GDPR.
- Gazzetta Ufficiale: Codice deontologico forense.

## Regole senza fonte

Nessuna regola nel ruleset `2026.05.12.1` viene marcata pronta senza `source_evidence_ids`.
Se una nuova area o sottoregola non trova fonte ufficiale, il codice imposta:

- `fonte_regole = "fonte ufficiale non documentata"`;
- `richiede_verifica_avvocato = true`;
- `stato_conformita = cartabia_review_required`;
- issue bloccante `fonte_normativa_mancante`.

Per i 1320 template canonici con fonte ufficiale e capability complete, `richiede_verifica_avvocato` resta `false`: il cliente o la pratica vengono richiesti solo durante la compilazione e non abbassano lo stato del modello.

## Fonti non trovate

- CNF: non e' stata usata una pagina CNF non autenticata come fonte primaria per il testo completo aggiornato; e' stata usata la pubblicazione in Gazzetta Ufficiale del Codice deontologico forense.
- PTT: se il portale istituzionale dovesse cambiare URL pubblico, i template tributari restano verificabili ma il record `PTT-SPECIFICHE-TECNICHE-2021` va aggiornato prima di promuovere nuove regole tecniche specifiche.

## Template bloccati per fonte mancante

Il blocco viene calcolato dal catalogo unificato. Alla data del report, ogni area standard ha almeno un evidence id ufficiale; eventuali template con `processo_area` non riconosciuta vengono degradati a revisione e compaiono nel report inventario.

## Privacy ricerca web

La ricerca web e' stata limitata a norme, portali istituzionali e documentazione pubblica. Non sono stati inviati dati cliente, fascicolo, soggetti, PEC personali, codici fiscali, contenuti atti o dati riservati dello studio.
