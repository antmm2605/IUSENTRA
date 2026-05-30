# PST / PolisWeb - test reale import fascicolo Palmi R.G. 1025/2024

Data prova: 30 maggio 2026.

Ambiente: IUSENTRA locale `http://127.0.0.1:8080`, Local Signer `1.6.67`, token CNS Bit4id, certificato Windows auto-selezionato `MNTRRT64L01L063H`.

## Percorso eseguito

1. Apertura wizard `Portali / PST / Acquisizione` con ufficio `Tribunale di Palmi`, codice ufficio UI `0910011`, R.G. `1025/2024`.
2. Ricerca PST reale dal browser: risultato `RG 1025/2024`, stato `PROCEDIMENTO DEFINITO`, parte `MONTAGNESE ELISABETTA`.
3. Anteprima completa fascicolo: `51` documenti, `36` righe cronologia complessiva, `3` parti, scadenziario da data ministeriale `12/12/2024`.
4. Step selezione: `51/51` documenti selezionati, pulsanti `Seleziona tutti`, `Nessuno`, `Scarica selezionati`, `Scarica tutti` presenti.
5. Download batch `Scarica tutti`: completato `51/51`, con `51` documenti PST scaricati e marcati `Scaricato`.
6. Analisi qualità: punteggio `100`, blocchi `0`, avvisi `0`, OK `4`.
7. Import finale: `Importazione completata`, pratica gestionale `2026/008`, fascicolo locale `487EE7F3`.

## Esito documentale

Report UI import:

- `Documenti reali`: `51`
- `Informazioni`: `0`
- `Solo catalogo`: `0`
- `Senza contenuto`: `0`
- `Scartati`: `0`

Verifica su disco:

- record documento nel fascicolo `487EE7F3`: `51`
- file fisici nella cartella `data/tenants/tenant-8bf98719c459/fascicoli/documenti/487EE7F3`: `51`
- collegamenti mancanti tra record e file fisico: `0`
- nomi duplicati reali preservati: `DatiAtto.xml.p7m` `4` volte, `IndiceDocumentiDepositati.PDF` `4` volte.

## Regola di non regressione

Il software non deve deduplicare i documenti PST usando solo il nome file. I duplicati di nome esposti dal portale in depositi diversi devono restare documenti distinti, usando identificativi ministeriali come `id_documento_portale`, `id_cat`, `id_deposito_pct`, `id_reperto`, `msg_id` e hash contenuto come chiave di controllo.

La cronologia mostrata all'utente deve conteggiare anche comunicazioni, istanze, udienze e righe di sezione, non solo l'array tecnico `eventi`, perché il portale espone il fascicolo su più schede logiche.
