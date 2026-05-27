# Traccia PST reale - Palmi SICID 274/2026 - Local Signer 1.6.59

Data: 27 maggio 2026.

Ambiente: macchina locale Windows con Local Signer `1.6.59`, token CNS inserito,
curl disponibile e registro uffici locale attivo.

Perimetro verificato:

- ufficio selezionato lato IUSENTRA: Tribunale di Palmi `0910011`;
- codice ministeriale risolto dal Local Signer: `0800570094`;
- fascicolo: R.G. `274/2026`;
- selezione certificato: `GET /ping?auto=1&prefer_cf=...` ha restituito
  `auto_selezionato=true`, codice fiscale coerente e thumbprint disponibile;
- ricerca reale inviata senza `cert_thumbprint` manuale nel payload: il Local
  Signer ha riusato il certificato auto-selezionato;
- esito ricerca: `ok=true`, 1 fascicolo, 6 documenti, sessione PST attiva;
- scarico documenti: `/pst/download-documenti-batch` sullo stesso flusso,
  sempre senza `cert_thumbprint` manuale nel payload;
- esito download: 6 documenti richiesti, 6 documenti scaricati, 0 fallimenti.

Documenti ricevuti nel batch reale:

- `Decreto_35052610.pdf`
- `AttoNonCodificato_34341272.pdf`
- `Decreto_34319834.pdf`
- `Decreto_34319834.pdf`
- `Decreto_34319834.pdf`
- `Citazione_34316125.pdf`

Regressioni presidiate:

- la UI non deve aprire il selettore certificato quando il Local Signer espone
  già un certificato PST compatibile con il codice fiscale richiesto;
- il Local Signer deve ricordare il certificato auto-selezionato e usarlo nelle
  chiamate PST successive se il client non passa un thumbprint;
- il download resta in lotto unico e non torna al download singolo ripetuto;
- eventuali errori di singoli documenti devono restare failure per documento,
  senza azzerare i file realmente consegnati dal PST.
