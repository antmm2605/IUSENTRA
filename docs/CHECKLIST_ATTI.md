# Checklist Atti

## Obiettivo

La superficie `/checklist` e' il catalogo operativo degli atti con:

- aree professionali
- branche
- sottobranche
- canale di deposito o invio
- documenti obbligatori e opzionali
- controlli critici prima del deposito

## Superfici

- `/checklist`
- `/checklist/<id_template>`

## Regole di prodotto

- La data nelle cartelle usa sempre il formato italiano filesystem-safe `gg-mm-aaaa`.
- Il catalogo distingue i canali:
  - `PCT_TELEMATICO`
  - `PDP_PENALE`
  - `PAT_AMMINISTRATIVO`
  - `PTT_TRIBUTARIO`
  - `MISTO`
  - `PEC`
  - `CARTACEO`
- Il naming cartella e' generato dal dominio e non dal template HTML.
- Il catalogo checklist deriva anche dal catalogo built-in del workspace `Template Atti`, cosi' aree, branche e sottobranche non divergono piu' tra le due superfici.

## Aree operative coperte

- Civile
- Lavoro e Previdenza
- Famiglia e Persone
- Penale
- Amministrativo
- Tributario
- Societario
- Immigrazione
- Stragiudiziale

## Template inclusi

La release `2.176.0` porta il catalogo a `318` checklist operative:

- `30` checklist curate ad alta densita' operativa
- `288` checklist derivate dal catalogo built-in di `Template Atti`
- copertura completa `288/288` del catalogo professionale
- copertura completa `25/25` di aree, branche e sottobranche presenti nel catalogo template

Le checklist ora coprono anche i rami che mancavano in modo evidente rispetto a `/template-atti`, per esempio:

- procure e deleghe
- UNEP e notificazioni
- contenzioso tributario
- societario
- immigrazione e cittadinanza
- workflow misti di studio, pareri e atti esterni
- tutte le varianti built-in del workspace atti professionale

## Verifiche minime

- test dominio checklist: `python -m pytest -q tests/test_checklist_atti.py`
- build CSS via Docker release locale
- smoke route autenticata sul catalogo checklist
