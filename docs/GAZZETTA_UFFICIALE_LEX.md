# Connettore Gazzetta Ufficiale per Lex AI

Il connettore Gazzetta Ufficiale alimenta il Centro Fonti Ufficiali Lex con le novita' normative recenti della Serie Generale.

## Endpoint pubblici usati

Elenco ultimi 30 giorni:

```text
https://www.gazzettaufficiale.it/30giorni/serie_generale
```

PDF paginato rilevato nella pagina:

```text
/do/gazzetta/serie_generale/0/pdfPaginato
```

Download PDF completo:

```text
/do/gazzetta/downloadPdf
```

Il connettore legge la pagina degli ultimi 30 giorni, ricava data pubblicazione, numero, serie e supplemento, poi genera l'URL `downloadPdf` senza conservare sessioni private.

## Esecuzione

```powershell
pip install -r requirements-lex-sources.txt
python tools\gazzetta_ufficiale_sync.py --init-db --max-issues 5 --export-jsonl
```

Esecuzione tramite registry:

```powershell
python tools\lex_sources_sync.py --run gazzetta_ufficiale --export-jsonl
```

Output:

```text
data\fonti_ufficiali\lex_sources.sqlite
data\fonti_ufficiali\raw\gazzetta_ufficiale\*.pdf
data\fonti_ufficiali\text\*.txt
data\fonti_ufficiali\index\lex_sources_chunks.jsonl
```

## Uso in Lex AI

- Gazzetta Ufficiale: novita' normative giornaliere.
- Normattiva: testi normativi consolidati, originali o vigenti.
- Lex AI: ricerca, confronto e risposta con fonte, data acquisizione e livello di affidabilita'.

## Regole operative

- Non aggirare login, CAPTCHA o protezioni.
- Usare frequenza ragionevole, ad esempio una volta al giorno.
- Salvare URL, data, hash documento e fonte.
- Non scaricare storico massivo se non necessario.
