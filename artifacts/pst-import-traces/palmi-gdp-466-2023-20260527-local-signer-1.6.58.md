# Traccia prova PST/SIGP - Giudice di Pace di Palmi 466/2023

Data prova: 27 maggio 2026.

Ambito: prova reale autorizzata sul PC locale con certificato CNS/CIE presente
in Windows Certificate Store. Non sono stati salvati PIN, cookie, sessioni PST,
XML SOAP grezzi, contenuto PDF o thumbprint del certificato.

## Parametri

- Ufficio IUSENTRA: `0910401`.
- Codice PST ministeriale: `0800570152`.
- Servizio PST: `JPW_SIGP`.
- Registro: Giudice di Pace / SIGP.
- R.G.: `466/2023`.
- Local Signer: `1.6.58`.

## Esito ricerca

- Diagnosi Local Signer: OK, versione `1.6.58`.
- Ricerca snapshot: OK.
- Fascicoli trovati: 1.
- Documenti a catalogo: 34.
- Sessione PST locale presente: sì.

Primi documenti letti dal catalogo:

- `Atto_3080760.pdf` - `Decreto`.
- `Atto_3080731.pdf` - `Sentenza`.
- `Atto_3076763.pdf` - `Verbale`.
- `Atto_3073476.pdf` - `DepositoNoteConclusionali`.
- `Atto_3068389.pdf` - `DepositoNoteConclusionali`.

## Esito download

Con Local Signer `1.6.57` la ricerca e il catalogo erano riusciti, ma il
download SIGP andava in timeout. La verifica live ha mostrato che, per questo
servizio, il PST risponde a `estraiProfiloDocumento`, `estraiMasterDetailAtto`
e `calcolaHash`, e che il download riesce dopo `calcolaHash`.

Con Local Signer `1.6.58`:

- download batch singolo `Atto_3080760.pdf`: OK, 1 file, 0 fallimenti;
- lunghezza base64 del file singolo: `91664`;
- download batch multiplo `Atto_3080760.pdf` + `Atto_3080731.pdf`: OK, 2 file, 0 fallimenti;
- lunghezze base64 del lotto multiplo: `91664`, `262308`.

## Invarianti confermate

- La ricerca esatta numero/anno non aggiunge filtri di parte o CF.
- Il CF operativo deriva dal certificato selezionato sul PC.
- Il catalogo documenti resta nella stessa sessione della ricerca snapshot.
- Lo scarico del fascicolo resta batch e non torna al download singolo ripetuto.
- Per SIGP il lotto esegue `calcolaHash` prima del `downloadAtto` nello stesso
  processo `curl`.
