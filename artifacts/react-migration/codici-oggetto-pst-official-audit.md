# Audit CodiceOggetto PST ufficiali - 2026-05-11

## Fonti ufficiali PST usate

- PST Download: `https://pst.giustizia.it/PST/it/download.page`
- XSD SICI, riferimento PST `ACC3277`, pacchetto `XSD_SICI_20260116.zip`, aggiornamento 26/01/2026, SHA-256 `9882A052EE7F4B16DDB89E533534435203F048CFB4C4D45C1E8EA1443AC1C4B0`.
- XSD SIGP / Giudici di pace, riferimento PST `ACC3199`, pacchetto `XSD_SIGP_20241128.zip`, aggiornamento 29/11/2024, SHA-256 `845C52B4335F46C1690A8E9359E6DD715F517B1E5A712E2E570878C07253A17F`.
- XSD UNEP, riferimento PST `ACC3136`, pacchetto `XSD_UNEP_20241106.zip`, aggiornamento 06/11/2024, SHA-256 `01922D7AD93B0C73FB6F0421CDCC034751F6BF942F298B8BCBA7100C9C1F2C1F`.
- XSD Corte Suprema di Cassazione, riferimento PST `ACC4671`, pacchetto `XSD_Cassazione_20260227.zip`, aggiornamento 27/02/2026, SHA-256 `8CCF63A9C16D87E65AFBF11D5913AF7C54E54F212F68225B3F44F96953D507EA`.

## Esito estrazione

- File XSD con `xs:simpleType name="CodiceOggetto"`: 9.
- Enumeration sorgente lette: 4.618.
- Codici unici ufficiali normalizzati: 1.018.
- Codici ufficiali per registro: SICID 812, SIGP 36, UNEP 965, Cassazione 554.
- Codici verificati espressamente: `014001` presente, `111604` presente.
- XSD beta esclusi: non usati per la whitelist di produzione.

## Confronto con `codici_oggetto_iusentra_catalogo.xlsx`

- Righe foglio `Catalogo`: 826.
- Righe marcate `codice_oggetto`: 724.
- Righe marcate `materia/gruppo`: 102.
- Codici del foglio trovati negli XSD ufficiali: 707.
- Codici del foglio non trovati negli XSD ufficiali attivi: 17.
- Codici ufficiali XSD non presenti come `codice_oggetto` nel foglio: 311.

## Decisione applicativa

- Validazione, pre-deposito e `DatiAtto.xml`: usano solo `pct/data/cataloghi/codici_oggetto_pst.json`.
- UI React: usa `pct/data/cataloghi/codici_oggetto_pst_ui.json`, compatto, con area e gruppo arricchiti dal foglio Excel solo per facilitare la ricerca.
- Il foglio Excel non viene usato come fonte di verita' depositabile: le righe `da verificare`, OCR o non presenti negli XSD non entrano nella whitelist.

## Verifica UI 2.215.6

- Docker locale ricostruito no-cache e `/api/pronto` confermato su versione `2.215.6`.
- Browser Chrome headless verificato su desktop 1366x900, tablet 820x1180 e mobile 390x844.
- Route verificate: `/fascicoli/nuovo`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`, `/preventivi/wizard`.
- Esiti ricerca: `014001` selezionabile, ricerca per materia `famiglia` con risultati, `111604` presente, `014700` escluso perche' non ufficiale negli XSD attivi.
- Layout: nessun overflow orizzontale e nessun errore console sulle superfici verificate.
