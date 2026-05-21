# Test Legal Documents

Il test mirato principale è:

```bash
python -m pytest tests/test_legal_document_ingestion.py -q --tb=short
```

Copre:

- PEC con ZIP;
- ZIP con PDF, immagini, XML, cartelle e ZIP annidati;
- path traversal;
- zip bomb simulato;
- ZIP corrotto;
- duplicati;
- file senza estensione riconosciuto da magic bytes;
- file non ammesso;
- classificazione civile, penale, amministrativa, tributaria, Giudice di Pace, stragiudiziale, PEC e deposito;
- estrazione CF, PIVA, PEC, NRG, date, importi, parti, ufficio, udienze e termini;
- validazione negativa su CF/PEC/data futura/documento non leggibile;
- eventi agenda/scadenze/deposito/PEC;
- fascicolo matching sicuro, ambiguo e assente;
- Lex solo su validati;
- tenant isolation e proof bundle.

Il report metriche si esegue con:

```bash
python -m pct.cli legal-document-understanding-report --json
```

Il report non dichiara raggiunto il target 80% senza dati reali sufficienti.
