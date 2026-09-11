# Conformità agli schemi PST — verifica dell'11/09/2026

Fonte consultata: PST, pagina **Download > File Ufficiali del Processo Civile Telematico**
(`https://pst.giustizia.it/PST/it/download.page`) e schede collegate, lette l'11/09/2026.
Metodo: ogni pacchetto è stato scaricato dal PST e confrontato file per file (SHA-256 a parità di
fine riga, perché il repository normalizza gli XSD in LF) con le copie in `docs/specs/ministero/`.

## Pacchetti ufficiali e copie nel repository

| Canale | Pacchetto PST | SHA-256 zip | Stato PST | Copia nel repository |
|---|---|---|---|---|
| SICI | `XSD_SICI_20260508.zip` (12/05/2026) | `C59C825E…30CC0B` | in esercizio dal 14/05/2026 (NWS4877) | `xsd/2026-05-12-sici/` identica |
| SICI | `XSD_POL27A_11_06_2026.zip` (11/06/2026) | — | anticipazione (NWS4931) | `xsd/2026-06-11-sici-preview/` |
| SICI | `XSD_SICI_20260720.zip` (22/07/2026) | `83E5CA05…11A264` | anticipazione, test su Model Office (NWS5070) | non salvata |
| SIGP | `XSD_SIGP_20241128.zip` | — | in esercizio | `schema/` identica |
| UNEP | `XSD_PLO118_FASE2_per_SW_House_20241106.zip` | — | in esercizio | `XSD PLO118 FASE2 per SW House/` identica |
| ReGIndE | `XSD_REGINDE_20251010.zip` | — | in esercizio | `XSD_REGINDE_20251010/` identica |
| DTD | `DTD_20180328.zip` | — | in esercizio | `DTD_20180328/` identica |
| Cassazione | `XSD_Cassazione_20260227.zip` (v.21) | `8CCF63A9…D507EA` | in esercizio dal 04/03/2026 (NWS4683) | `parte/` identica (v3–v21) |
| Cassazione | `XSD_Cassazione_20260611.zip` | `B5E3758F…A7352D` | anticipazione (NWS4954) | `xsd/2026-06-15-cassazione-preview/` identica |
| Cassazione | `XSD_Cassazione_20260907.zip` (v.22) | `46313B36…549300` | anticipazione, esercizio da comunicare (NWS5108 del 09/09/2026) | non salvata |
| Certificati proxy PdA/PST | `20260325_Proxy_PDA_EXT.zip` | — | in produzione | `certificato autenticazione proxy/` identici |

Differenze verificate tra pacchetti:

- SICI 26/01/2026 → 12/05/2026: cambia solo `Atti/sici/tipi-base.xsd` (tipo `CodiceOggetto`). La
  Nota modifiche XSD (versione 1 dell'11/05/2026) corregge la descrizione dell'oggetto **171404**
  ("Reclamo avverso il rigetto della dichiarazione dello stato di insolvenza (Marzano)", la precedente
  "induceva gli utenti all'errore") e aggiunge gli oggetti CCI **471404, 471405, 471412–471419**.
- SICI 12/05/2026 → 22/07/2026: cambiano `tipi-base.xsd` ed `eventi.xsd`; 13 nuovi codici TSAP
  (118012–118018, 118021–118024, 418098, 418100). Il pacchetto non contiene le novità dell'11/06/2026.
- Cassazione 27/02/2026 → 11/06/2026: schemi degli atti identici, cambia solo PagamentiTelematiciGiustizia (6.2.0).
- Cassazione v21 → v22: tipo ricorso `Ricorso_art_14_1_TU_IMM`, atti `MemoriaDifensivaTUImmigrazione`
  e `MemoriaIllustrativaTUImmigrazione`.

## Non conformità trovate e correzioni (2.286.0)

1. **Catalogo codici oggetto SICID fermo al 26/01/2026.** Allineato al pacchetto in esercizio con
   `scripts/allinea_codici_oggetto_sici.py` (regola in `pct/guida_pratica/sici_catalog_alignment.py`):
   descrizione 171404 corretta, codici CCI depositabili sul SICID, grafia ministeriale di 473455–473457,
   provenienza e fonti aggiornate in catalogo tecnico, catalogo UI e schede Guida Pratica. Test di
   regressione: `tests/test_codici_oggetto_sici_xsd_esercizio.py`.
2. **DatiAtto Cassazione generato con i namespace v13** mentre è in esercizio la v21. La versione attiva è
   ora dichiarata una sola volta (`PST_CASSAZIONE_XSD_ACTIVE_VERSION`) e generatore, anagrafica,
   validatore e campi leggono le enumerazioni degli XSD in esercizio (`pct/cassazione_xsd_tables.py`):
   - tipo ricorso: tolto `RicorsoPerRevocazione` (eliminato dalla v16, la revocazione ha atti dedicati);
   - ruoli del fascicolo impugnato: aggiunti CassazioneCivile, AltreProcedureConcorsuali,
     ProcedimentoUnitario, GiustiziaTributaria; rito selezionabile dai 44 valori ministeriali; supporto
     `SubSocio` e `NumeroCCI`;
   - `SegnalazioneErroreMateriale`: numero e anno di raccolta generale del provvedimento, obbligatori dalla v21;
   - `Memoria380bis`: non più radice degli atti di parte dalla v16. Il catalogo la mostra come atto eliminato
     dal Ministero, non inviabile, con il motivo visibile all'avvocato.
   Test di regressione: `tests/test_cassazione_datiatto_schemi_esercizio.py` (32 atti validi sugli XSD v21).
3. **Monitor normativo PST**: le formule usate dal PST nel 2026 ("saranno in esercizio a seguito…",
   "sarà dato successivo avviso…", "verrà resa nota con una successiva comunicazione") non venivano
   riconosciute; aggiunte con test.

## Punti ancora aperti

- **Beni mobili pignorati**: `tipologia` è testo libero (predefinito `MOBILI`), mentre la
  `Codifiche_Beni_Mobili.pdf` del PST prevede codici numerici. Da implementare con la tabella ufficiale salvata qui.
- **Codifica errori controlli 1.0**: `legal_deposit/errors/rejection_analyzer.py` non mappa i messaggi
  FATAL/ERROR/WARN ministeriali.
- **Atti Cassazione v21 non ancora nel catalogo**: IstanzaSospensioneExL197_2022, ProduzionePagamentoExL197_2022,
  IstanzaAnticipazioneUdienza, IstanzaTrattazionePubblicaUdienza, RevocazioneExArt391ter,
  RevocazioneExArt391quater, RicorsoErroreMateriale, IstanzaOscuramento.
- **Anticipazioni non salvate**: `XSD_SICI_20260720.zip` e `XSD_Cassazione_20260907.zip` vanno salvati in
  `xsd/` (hash sopra) prima di usarli nel codice; alla messa in esercizio aggiornare catalogo e versione attiva.
- Schede Guida Pratica dei codici CCI 4714xx: normativa generica ereditata dal modello (c.c. 404 ss.), da curare.
- Il registro `CASSAZIONE` del catalogo codici oggetto deriva da `CodiceOggetto` di base_v3–v7; dagli schemi
  successivi la Cassazione usa `MaterieRicorso`.
