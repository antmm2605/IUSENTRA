# Atti Cassazione v21 predisposti e non attivi

Stato: **predisposti, non attivi** (decisione dello studio dell'11/09/2026). Interruttore:
`pct/cassazione_atti_v21.py` → `CASSAZIONE_ATTI_V21_ATTIVI = False`.

Con l'interruttore spento gli atti non compaiono nel catalogo depositi, non sono selezionabili e il
generatore DatiAtto rifiuta la preparazione con un messaggio per l'avvocato. Con l'interruttore acceso
entrano nel catalogo Corte di Cassazione (33 → 41 voci, 270 → 278 tipi) e sono inviabili.

Nota sulle fonti: le otto radici appartengono agli schemi **v21 già in esercizio** (XSD_Cassazione_20260227,
applicati dal 04/03/2026). Dal lato ministeriale non serve attendere un'ulteriore messa in esercizio:
l'attivazione dipende dalla prova sulla macchina reale e dal deploy di IUSENTRA.

## Atti

| Radice XSD | Dal | Voce catalogo | Dati generati oltre a procedimento/IndiceBusta | Base |
|---|---|---|---|---|
| `IstanzaSospensioneExL197_2022` | v14 | Istanza di sospensione per definizione agevolata | — | L. 197/2022, art. 1, comma 197 |
| `ProduzionePagamentoExL197_2022` | v14 | Definizione agevolata: produzione del pagamento | — | L. 197/2022, art. 1, commi 186-203 |
| `IstanzaAnticipazioneUdienza` | v16 | Istanza di anticipazione dell'udienza | — | XSD v21 |
| `IstanzaTrattazionePubblicaUdienza` | v16 | Istanza di trattazione in pubblica udienza | — | XSD v21 ("da protocollo di intesa") |
| `IstanzaOscuramento` | v17 | Istanza di oscuramento dei dati identificativi | `Parte` (CF/P.IVA), `Privacy` (A_RICHIESTA_DI_PARTE, EX_LEGE) | D.Lgs. 196/2003, art. 52 |
| `RicorsoErroreMateriale` | v16 | Ricorso per correzione di errore materiale | destinazione, date notifica, Provvedimento, Materia, speseGiustizia, AnagraficaProcedimento, DocumentiECLI | c.p.c., art. 391-bis |
| `RevocazioneExArt391ter` | v16 | Ricorso per revocazione ex art. 391-ter | come sopra + `MotiviRevocazione391Ter` (art. 395 nn. 1, 2, 3, 6) | c.p.c., artt. 391-ter e 395 |
| `RevocazioneExArt391quater` | v16 | Ricorso per revocazione ex art. 391-quater | come sopra + `MotiviRevocazione391Quater` (lett. a, b) | c.p.c., art. 391-quater (D.Lgs. 149/2022) |

Riferimenti consultati l'11/09/2026: testo degli artt. 391-ter e 391-quater c.p.c. (Brocardi);
Ministero della Giustizia, pagina sul contributo unificato per la definizione agevolata "art. 1, commi 186-203,
L. n. 197/2022"; art. 1, comma 197, L. 197/2022 (sospensione su richiesta del contribuente). Per
`IstanzaAnticipazioneUdienza` e `IstanzaTrattazionePubblicaUdienza` la fonte è lo schema ministeriale: non è
stata individuata una norma specifica da citare.

## Codice

- `pct/cassazione_atti_v21.py`: interruttore, radici, voci del catalogo con base normativa.
- `pct/cassazione_atti_v21_datiatto.py`: generazione DatiAtto (mixin di `BustaTelematica`).
- `pct/cassazione_xsd_tables.py`: namespace e tabelle degli XSD Cassazione in esercizio.
- `pct/deposito_datiatto_fields.py`: campi del deposito (motivi di revocazione, oscuramento, dati del ricorso).
- `frontend/src/components/FascicoloDepositoPage.tsx`: campo `motivi-revocazione-cassazione`.
- `scripts/audit_deposito_catalogo_end_to_end.py`: riconosce la fonte XSD delle voci e i campi XML attesi.
- Test: `tests/test_cassazione_atti_v21_predisposti.py` (interruttore spento e acceso); le attese di
  `tests/test_deposito_telematico_catalogo.py` si adeguano da sole allo stato dell'interruttore.

Prova eseguita l'11/09/2026 con interruttore acceso nel sandbox: 8/8 DatiAtto validi su `parte_v21`; audit del
catalogo con 40 atti Cassazione verificati e nessun errore sulle voci Cassazione (gli altri errori dell'audit
dipendono dall'ambiente: certificati PST e sorgenti Studio Telematico non raggiungibili).

## Checklist di attivazione

1. Portare `CASSAZIONE_ATTI_V21_ATTIVI` a `True` in un commit dedicato con bump di versione.
2. Rieseguire sulla macchina reale `tests/test_cassazione_atti_v21_predisposti.py` e
   `tests/test_deposito_telematico_catalogo.py` (audit completo, attese 278 tipi).
3. Ricompilare il bundle React e provare sulla UI reale: selezione di ciascun atto, campi richiesti, motivi di
   revocazione, oscuramento, simulazione di deposito fino alla richiesta PIN senza invio reale.
4. Verificare la presenza dei relativi modelli in Redazione Atti, se lo studio li vuole disponibili.
5. Aggiornare `PST_XSD_CONFORMITA_2026-09-11.md` e il CHANGELOG, poi commit, push dei branch gemelli e deploy.
