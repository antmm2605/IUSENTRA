# Registri consultazione fascicoli QuickOrganizer

Generato: 30/06/2026 21:39 (Europe/Rome).

Questo file risponde al perimetro richiesto: civile ordinario SICID/RGN, lavoro SIL/LAV, volontaria giurisdizione SIVG/VG, minorenni MIN/SIMIN, esecuzioni e concorsuali SIECIC, Giudice di Pace SIGP/GDP, Cassazione civile CASSCI, Cassazione penale CASSPE e registri ulteriori trovati.

## Sintesi

- QuickOrganizer legge i registri disponibili da `C:/QuickOrganizer/ListaUfficiGiudiziari.xml` e li incrocia con logica runtime in `Common.cs` e `WizardImportaPraticheDaPolisWeb.cs`.
- Per il civile ordinario QuickOrganizer usa registro `CC`; `RGN/RNG` sono alias/tipo numero ruolo da normalizzare in IUSENTRA.
- Per Giudice di Pace il XML espone `GDP`, mentre alcune parti del codice storico usano `GP`: IUSENTRA deve accettare entrambi.
- Per lavoro, volontaria giurisdizione e minorenni QuickOrganizer passa spesso dal target `JPW_SICID`, ma con URN dedicati `CONS-SIL-BE`, `CONS-SIVG-BE`, `CONS-MIN-BE`.
- `Agrarie` e `Speciali` risultano tipi/filtro locali QuickOrganizer: non ho trovato una combinazione JPW autonoma nel catalogo XML.

## Conteggio servizi nel catalogo uffici

| Servizio | Righe ufficio |
| --- | --- |
| PAGAM_TEL | 1036 |
| DEPOT | 659 |
| JPW_SIGP | 562 |
| JPW_SICID | 450 |
| SICID | 429 |
| SIECIC | 386 |
| JPW_SIECIC | 338 |
| COM_TEL_VAL_LEG | 196 |
| COM_TEL_136 | 158 |
| COMTEL | 50 |
| JPW_UNEP | 3 |
| COM_TEL_SPER | 1 |
| JPW_CASS | 1 |

## Registri e mapping operativo

| Servizio XML | Applicazione | Registro XML | Descrizione | Uffici | Target Quick | Servizio IUSENTRA | URN | Ruoli | Note |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| JPW_CASS | sic | CASSCI | Cassazione Civile | 1 | JPW_CASS | JPW_CASSCI | CONS-CASSCI | AVV, DEL, CTU, AUS, AVV@AVV | QuickOrganizer usa anche URL browser PST con ufficio 80417740588, registroRicerca=CASSCI e ruoloRicerca=AVV@AVV. |
| JPW_CASS | sic | CASSPE | Cassazione Penale | 1 | JPW_CASS | JPW_CASSPE | CONS-CASSPE | AVV@AVV | Il XML QuickOrganizer espone CASSPE e il menu apre il PST penale; IUSENTRA ha già prove live su JPW_CASSPE/QP_Ricorsi. |
| JPW_SICID | sicid | CC | Contenzioso Civile | 421 | JPW_SICID | JPW_SICID | CONS-SICC-BE | AVV, DEL, CTU, NOT, TUT, AUS | Civile ordinario: in QuickOrganizer il registro è CC; IUSENTRA può mantenere alias RGN/RNG ma deve inviare il registro reale CC quando interroga il servizio. |
| JPW_SICID | sicid | LAV | Lavoro | 421 | JPW_SICID | JPW_SIL / JPW_SIL_DISTR | CONS-SIL-BE | AVV, DEL, CTU, NOT, TUT, AUS | QuickOrganizer usa gateway JPW_SICID, ma namespace lavoro CONS-SIL-BE. IUSENTRA ha già fallback logico JPW_SIL_DISTR/JPW_SIL. |
| JPW_SICID | sicid | MIN | Minorenni | 29 | JPW_SICID | JPW_MIN / JPW_SIMIN | CONS-MIN-BE | AVV, DEL, CTU, NOT, TUT, AUS | Il XML ministeriale QuickOrganizer espone MIN per i tribunali per i minorenni; IUSENTRA distingue MIN e SIMIN come servizi logici già provati. |
| JPW_SICID | sicid | VG | Volontaria Giurisdizione | 421 | JPW_SICID | JPW_SIVG | CONS-SIVG-BE | AVV, CTU, AUS | Volontaria giurisdizione: servizio logico SIVG, gateway QuickOrganizer JPW_SICID. |
| JPW_SIECIC | siecic | ESIM | Esecuzioni Immobiliari | 338 | JPW_SIECIC | JPW_SIECIC | CONS-SIECIC-BE | AVV, DEL, CTU, CUS, AUS | Esecuzioni immobiliari SIECIC; richiede gestione ruolo/dfa reale. |
| JPW_SIECIC | siecic | ESM | Esecuzioni Mobiliari | 338 | JPW_SIECIC | JPW_SIECIC | CONS-SIECIC-BE | AVV, DEL, CTU, CUS, AUS | Esecuzioni mobiliari SIECIC; stesso gateway delle concorsuali ma registro diverso. |
| JPW_SIECIC | siecic | FALL | Procedure Concorsuali | 338 | JPW_SIECIC | JPW_SIECIC | CONS-SIECIC-BE | AVV, DEL, CTU, CUR, CUS, AUS | Procedure concorsuali SIECIC; per dettaglio può servire idRuoloJPW/idDfa reale, non inventabile. |
| JPW_SIGP | sigp | GDP | Giudice di Pace | 562 | JPW_SIGP | JPW_SIGP | CONS-SIGP-BE | AVV, DEL, CTU, AUS | Nel XML il registro è GDP; nel codice QuickOrganizer il filtro storico usa GP. IUSENTRA deve accettare entrambi come alias. |
| JPW_UNEP | unep | A | Atti a Richiesta di Parte a Pagamento | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
| JPW_UNEP | unep | A/GP | Giudice di pace esente | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
| JPW_UNEP | unep | A/TER/P | Atto materia lavoro esente | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
| JPW_UNEP | unep | B/P | Atto Penale a Pagamento | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
| JPW_UNEP | unep | C | Esecuzione | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
| JPW_UNEP | unep | C/TER | Esecuzione Lavoro | 3 | JPW_UNEP | JPW_UNEP |  |  | Registro UNEP esposto dal catalogo uffici; non è scarico fascicolo civile ordinario. |
|  |  | Agrarie | Controversie Agrarie | 0 |  | da verificare |  |  | QuickOrganizer lo conserva come tipo registro locale/filtro, ma non ho trovato una combinazione JPW autonoma nel XML ministeriale. |
|  |  | Speciali | Procedimenti Speciali o Sommari | 0 |  | da verificare |  |  | QuickOrganizer lo conserva come tipo registro locale/filtro, ma non ho trovato una combinazione JPW autonoma nel XML ministeriale. |

## Campione uffici

| Registro | Codice ufficio | Ufficio | Tipo | PEC |
| --- | --- | --- | --- | --- |
| CASSCI | 80417740588 | Corte Suprema di Cassazione | CC | cassazione@ptel.giustiziacert.it |
| CASSPE | 80417740588 | Corte Suprema di Cassazione | CC | cassazione@ptel.giustiziacert.it |
| CC | 03200602501 | Commissariato agli usi civici per il FRIULI VENEZIA GIULIA | CV | usicivici.trieste@civile.ptel.giustiziacert.it |
| CC | 05809102502 | Commissariato agli usi civici per il LAZIO, la TOSCANA e l'UMBRIA | CV | usicivici.roma@civile.ptel.giustiziacert.it |
| LAV | 03200602501 | Commissariato agli usi civici per il FRIULI VENEZIA GIULIA | CV | usicivici.trieste@civile.ptel.giustiziacert.it |
| LAV | 05809102502 | Commissariato agli usi civici per il LAZIO, la TOSCANA e l'UMBRIA | CV | usicivici.roma@civile.ptel.giustiziacert.it |
| MIN | 0580910112 | Tribunale per i Minorenni - Roma | TM | tribmin.roma@civile.ptel.giustiziacert.it |
| MIN | 0900640115 | Tribunale per i Minorenni - Sassari | TM | tribmin.sassari@civile.ptel.giustiziacert.it |
| VG | 03200602501 | Commissariato agli usi civici per il FRIULI VENEZIA GIULIA | CV | usicivici.trieste@civile.ptel.giustiziacert.it |
| VG | 05809102502 | Commissariato agli usi civici per il LAZIO, la TOSCANA e l'UMBRIA | CV | usicivici.roma@civile.ptel.giustiziacert.it |
| ESIM | 987654321Z | Corte di Appello di Model Office | CA | mopectest02@civile.ptel.giustiziacert.it |
| ESIM | 0690050192 | Sezione Distaccata - Atessa | SD | tribunale.lanciano.atessa@civile.ptel.giustiziacert.it |
| ESM | 987654321Z | Corte di Appello di Model Office | CA | mopectest02@civile.ptel.giustiziacert.it |
| ESM | 0690050192 | Sezione Distaccata - Atessa | SD | tribunale.lanciano.atessa@civile.ptel.giustiziacert.it |
| FALL | 987654321Z | Corte di Appello di Model Office | CA | mopectest02@civile.ptel.giustiziacert.it |
| FALL | 0690050192 | Sezione Distaccata - Atessa | SD | tribunale.lanciano.atessa@civile.ptel.giustiziacert.it |
| GDP | 06300101547 | GIUDICE DI PACE - Acerra | GP | gdp.acerra@civile.ptel.giustiziacert.it |
| GDP | 06500601569 | GIUDICE DI PACE - Amalfi | GP | gdp.amalfi@civile.ptel.giustiziacert.it |
| A | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| A | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |
| A/GP | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| A/GP | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |
| A/TER/P | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| A/TER/P | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |
| B/P | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| B/P | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |
| C | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| C | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |
| C/TER | 1514600637 | UNEP - Corte d'Appello - Milano | UP | unep.ca.milano@civile.ptel.giustiziacert.it |
| C/TER | 01514902233 | UNEP - Tribunale Ordinario - Monza | UP | unep.tribunale.monza@civile.ptel.giustiziacert.it |

## Regole per IUSENTRA

- La ricerca fascicolo deve salvare sempre registro normalizzato, alias mostrato, servizio JPW, ufficio, ruolo e anno.
- La ricerca per anno non è un filtro testuale: deve diventare parametro governato del servizio o del portale, con `numero=0` quando previsto.
- Per SIECIC non inventare `idRuoloJPW` o `idDfa`: se mancano, bloccare solo quel dettaglio con motivo puntuale.
- Le aree Cassazione civile e penale vanno tenute separate: `CASSCI` e `CASSPE` hanno URL/servizi distinti.
