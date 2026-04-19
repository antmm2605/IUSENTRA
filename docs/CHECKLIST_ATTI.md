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
  - `PEC`
  - `CARTACEO`
- Il naming cartella e' generato dal dominio e non dal template HTML.

## Aree operative coperte

- Civile e commerciale
- Lavoro e previdenza
- Famiglia e persone
- Esecuzioni e cautelare
- Penale e indagini
- Amministrativo e appalti
- Tributario
- ADR e stragiudiziale

## Template inclusi

La release `2.175.0` porta il catalogo a `30` template strutturati, con copertura espansa su:

- rito lavoro
- licenziamenti
- separazione consensuale
- divorzio congiunto
- modifica condizioni familiari
- opposizioni esecutive
- motivi aggiunti TAR
- appello al Consiglio di Stato
- memoria ex art. 415-bis c.p.p.
- istanza di dissequestro
- negoziazione assistita
- diffida e messa in mora

## Verifiche minime

- test dominio checklist: `python -m pytest -q tests/test_checklist_atti.py`
- build CSS via Docker release locale
- smoke route autenticata sul catalogo checklist
