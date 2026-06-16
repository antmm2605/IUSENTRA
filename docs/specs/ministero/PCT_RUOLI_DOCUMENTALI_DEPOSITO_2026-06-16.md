# Ruoli documentali PCT per la UI di deposito

Data controllo: 16 giugno 2026.

## Fonti controllate

- Portale dei Servizi Telematici, pagina ufficiale `Specifiche Tecniche ex art. 34 DM 44/2011 - Provvedimento 7 agosto 2024`: alla data del controllo risultano il provvedimento 7 agosto 2024, l'avviso di rettifica del 16 settembre 2024 e l'avviso di rettifica del 30 ottobre 2024.
- Specifiche tecniche DGSIA ex art. 34 D.M. 44/2011, documento locale `docs/specs/ministero/Specifiche_Tecniche_DGSIA_DM44_2011_2024_08_07.pdf`.
- DTD locale busta `docs/specs/ministero/DTD_20180328/IndiceBusta.dtd`: la busta distingue `Atto` e `Allegato`; l'attributo tecnico `Tipo` degli allegati prevede, tra gli altri, allegato semplice, procura alle liti, dati atto, ricevuta telematica, messaggio PEC di notifica e ricevuta di avvenuta consegna.
- Direttive notifiche legali salvate in `docs/specs/ministero/notifiche_legali_directives.md` e matrice probatoria `docs/specs/ministero/NOTIFICHE_PEC_MATRICE_PROBATORIA_2026-06-02.md`.

## Regola applicativa

La UI del deposito non deve esporre ruoli ambigui come `Allegato / prova`.

I ruoli visibili all'avvocato sono:

- `Atto principale`;
- `Procura alle liti`;
- `Allegato`;
- `Prova notifica`;
- `Fuori busta`.

`Prova notifica` va usato solo quando il documento appartiene al fascicolo probatorio della notifica, ad esempio atto notificato, relata, PEC inviata, ricevuta di accettazione, ricevuta di avvenuta consegna, RAC/RdAC o evidenze equivalenti richieste dal deposito prova.

I documenti probatori ordinari del fascicolo, come contratti, buste paga, quietanze, documenti retributivi o documenti prodotti a sostegno della domanda, sono `Allegato` nella UI. La natura probatoria resta nel titolo, nei tag, nello slot documentale o nel tipo tecnico del pacchetto, ma non deve comparire come ruolo ibrido del menu.

## Compatibilità tecnica

Il valore storico interno `allegato_prova` può essere ancora accettato in ingresso per non rompere classificazioni già salvate o chiamate vecchie, ma deve essere normalizzato e mostrato come `Allegato`.

La normalizzazione deve valere sia nella UI React sia nell'endpoint di salvataggio della classificazione documenti.

## Guardrail

- Il menu React `DEPOSIT_DOCUMENT_ROLE_OPTIONS` non deve contenere `Allegato / prova` né il valore `allegato_prova`.
- L'endpoint `/api/v1/ui/fascicoli/<id>/deposito/classifica-documenti` deve convertire alias vecchi come `prova`, `documento_prova` e `allegato_prova` in `allegato`, salvo `prova_notifica` che resta ruolo separato.
- Gli slot documentali generici possono continuare a essere soddisfatti da un documento con ruolo `Allegato`.
- Gli slot di notifica, ricevute o RAC/RdAC devono richiedere `Prova notifica`.
