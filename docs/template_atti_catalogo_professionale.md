# Catalogo template atti - Suite professionale

La pagina `/template-atti/catalogo` integra la Suite professionale completa del compilatore atti nella stessa superficie del catalogo esistente. Non esiste una pagina o un tab separato `Master professionale`: il catalogo master v1.1.0 e' usato come sorgente dati unica per filtri, card e controlli.

## Dati governati

- Versione suite: `v1.1.0`
- Template master: `420`
- Moduli professionali: `22`
- Canali telematici governati: `7`
- Sorgente master: `pct/template_atti_catalogo_data/catalogo_master.json`
- Split catalogo: `core.json`, `advanced.json`, `specialist.json`, `studio_interno.json`

## Superficie utente

La pagina mostra un riepilogo professionale, gruppi suite, ricerca libera, chip rapidi e filtri combinabili per materia, area, macro-area, sottobranca, procedimento, rito, fase, tipologia atto, categoria suite, canale, portale, stato, firma digitale, PDF/A, DatiAtto.xml, allegati, contributo, marca e controlli completi.

Ogni card template espone codice, titolo, categoria suite, materia, procedimento, rito, fase, canale/portale deposito, stato, controlli deposito disponibili, allegati obbligatori, dati obbligatori e azioni `Compila`, `Anteprima`, `Verifica deposito`, `Dettagli normativa`, `Duplica`.

## Controlli deposito

Le regole vivono in `pct/template_deposit_rules.py` e sono versionate con:

- fonte normativa o fonte configurabile;
- versione regola;
- data ultimo aggiornamento;
- severita;
- blocco deposito;
- messaggio utente;
- suggerimento correzione.

I canali gestiti sono PST/PCT Civile, SIGP/Giudice di Pace, PAT/SIGA, PTT/SIGIT, PDP Penale, PEC/Stragiudiziale e Atti interni studio.

## Endpoint

- `GET /template-atti/catalogo/data`
- `GET /template-atti/catalogo/filters`
- `GET /template-atti/<codice>/compliance`
- `POST /template-atti/<codice>/verifica-deposito`

Gli endpoint rispettano l'autenticazione esistente e non modificano i template master.
