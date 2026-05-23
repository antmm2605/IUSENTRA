# Guida Pratica - Knowledge Base completa

La Guida Pratica vive fuori dal codice applicativo:

- `pct/data/legal_knowledge_base.full.json`;
- `pct/data/legal_knowledge_base.json`;
- `pct/data/legal_knowledge_base_modules/*.json`;
- `pct/data/legal_knowledge_base_index.json`.

Il merge dei moduli produce un knowledge base unico, ma il catalogo ufficiale PST/XSD resta separato in `pct/data/cataloghi/codici_oggetto_pst.json`.

## Risultato operativo 2.248.19

- Codici nel catalogo guida: 1.080.
- Codici ufficiali PST/XSD: 1.018.
- Codici ufficiali con guida curata: 1.018.
- Codici ufficiali senza guida curata: 0.
- Schede interne o alias non depositabili: 62.

Le schede interne sono mantenute per continuità dei fascicoli, ricerca e guida operativa facoltativa, ma non vengono considerate codici di deposito.

## Uso nel fascicolo

Nel dettaglio fascicolo React, `GuidaPraticaSidebar` legge il codice oggetto quando presente e chiama:

```text
GET /api/v1/ui/fascicoli/<id_fasc>/guida-pratica
```

Il backend risolve il codice, legge il knowledge base, applica eventuale ereditarietà e restituisce:

- checklist;
- normativa;
- atto principale;
- campi obbligatori;
- allegati;
- adempimenti;
- stato operativo della guida.

Se il fascicolo non ha un codice oggetto valorizzato, il backend può proporre una scheda pratica dall'oggetto o dal titolo. La proposta è sempre facoltativa e non blocca il lavoro: per un deposito telematico resta necessario scegliere nella scheda fascicolo un codice PST/XSD ufficiale.

## Validazione

```bash
python scripts\merge_legal_kb_modules.py
python scripts\validate_guida_pratica.py --require-official-curated --fail-on-generated
python -m pytest tests\test_guida_pratica_service.py tests\test_guida_pratica_api.py -q --tb=short
```

La copertura ufficiale deve rimanere al 100%. Se un codice ufficiale entra nel catalogo senza guida curata, il validatore deve fallire e il modulo guida va completato prima del rilascio.

## Aggiornamento TOP9 set5

Il set ricevuto il 23 maggio 2026 è integrato nei moduli:

- `pct/data/legal_knowledge_base_modules/kb_98_top9_set5_parte1.json`;
- `pct/data/legal_knowledge_base_modules/kb_98_top9_set5_parte2.json`.

Le schede coerenti con codice ufficiale restano depositabili (`411601`, `102002`, `151110`, `220020`). Le schede con codice assente o diverso dal contenuto ministeriale sono guide interne facoltative: `GUIDA_REGOLAMENTO_CONFINI_130032`, `GUIDA_IMPUGNAZIONE_TESTAMENTO_120020`, `GUIDA_RESPONSABILITA_NOTAIO_COMMERCIALISTA_143003`, `GUIDA_CONSUMATORE_CLAUSOLE_VESSATORIE_180001`, `GUIDA_AZIONE_NEGATORIA_SERVITU_POSSESSORIA_130031`.

## Aggiornamento TOP9 set6

Il set ricevuto il 23 maggio 2026 è integrato nei moduli:

- `pct/data/legal_knowledge_base_modules/kb_98_top9_set6_parte1.json`;
- `pct/data/legal_knowledge_base_modules/kb_98_top9_set6_parte2.json`.

Il codice `111003` resta agganciato al catalogo ufficiale. Le altre otto schede restano guide interne facoltative perché il codice ricevuto è assente o descrive nel catalogo locale una materia diversa: `GUIDA_PRELIMINARE_COMPRAVENDITA_2932_140002`, `GUIDA_IMPUGNAZIONE_DELIBERE_ASSEMBLEARI_155001`, `GUIDA_LICENZIAMENTO_DISCIPLINARE_220003`, `GUIDA_OPPOSIZIONE_CARTELLA_ESATTORIALE_191001`, `GUIDA_IMMISSIONI_INTOLLERABILI_130012`, `GUIDA_EREDITA_GIACENTE_413021`, `GUIDA_OPPOSIZIONE_SANZIONE_AMMINISTRATIVA_240001`, `GUIDA_DEMANSIONAMENTO_DEQUALIFICAZIONE_220030`.

L'audit voce per voce controlla ora 11 moduli utente e 54 schede iper-dettagliate: nessun campo ricevuto è perso tra KB full, servizio/API, UI React e Lex, e nessuna denominazione/competenza/rito viene sostituita da profili automatici.
