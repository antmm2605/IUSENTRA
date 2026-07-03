# PolisWeb: controllo fonti, Studio Telematico e IUSENTRA

Generato: 03/07/2026 (Europe/Rome).

Questo file è il controllo di triangolazione da rileggere insieme a `polisweb-studio-telematico-end-to-end.md` quando si lavora su ricerca fascicoli, import da PST/PolisWeb, download documenti, notifiche di cancelleria, presidio PEC, agenda o scadenziario. Non è un promemoria di chat: è il contratto operativo che lega fonte ministeriale, comportamento osservato in Studio Telematico e implementazione IUSENTRA.

## Fonti controllate

- Fonte ufficiale PST più aggiornata reperita al 03/07/2026: `https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4571`, `Documentazione servizi web esposti (versione 1.69)`, ultimo aggiornamento `12/02/2026`.
- PDF ufficiale PST: `https://pst.giustizia.it/PST/resources/cms/documents/Documentazione_servizi_web_v1.69.pdf`.
- WSDL ufficiale collegato: `A1_WSDL_CATALOG_v1.52`, pubblicato nella stessa pagina PST.
- Sorgenti locali Studio Telematico decompilati:
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\WizardImportaPraticheDaPolisWeb.cs`
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\PCT.cs`
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\Common.cs`
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\FormMain.cs`
  - `C:\Users\antmm\AppData\Local\Temp\quickorganizer_decompiled_full\QuickOrganizer\BrowserForm.cs`
- Cataloghi locali Studio Telematico:
  - `C:\QuickOrganizer\ListaUfficiGiudiziari.xml`, modificato il `17/03/2026 14:05:05`.
  - `C:\QuickOrganizer\QC_Uffici.xml`, modificato il `17/03/2026 14:05:05`.
- Implementazione IUSENTRA controllata:
  - `pct/polisWeb.py`
  - `tools/local_signer.py`
  - `web/services/telematico_runtime.py`
  - `web/blueprints/api_v1_react.py`
  - `frontend/src/components/TelematicoSurfacePage.tsx`
  - `tests/test_polisweb.py`
  - `tests/test_local_signer.py`
  - `tests/test_portali_telematici_matrix.py`
  - `tests/test_react_shell.py`

## Esito sintetico

Il flusso reale da usare in IUSENTRA resta quello autenticato PST/JPW, non le consultazioni anonimizzate. La v1.69 aggiunge namespace per consultazioni anonime Minorenni e Giudice di Pace; queste informazioni vanno conservate come copertura futura/catalogo, ma non devono sostituire ricerca, profilo, storico, master/detail e download del fascicolo reale autenticato.

La catena primaria è corretta se conserva questi passaggi:

1. scelta registro professionale in UI;
2. conversione in registro ministeriale reale;
3. scelta endpoint/servizio PST;
4. sessione certificato web riusata;
5. ricerca con metodo specifico del registro;
6. profilo fascicolo;
7. storico/eventi;
8. master/detail da `idDocumento`;
9. download da `idCat` in batch;
10. persistenza tenant-aware in fascicolo, documenti, agenda, scadenziario e presidio PEC.

## Matrice controllo registro per registro

| Area utente | Codice IUSENTRA | Fonte PST v1.69 | Studio Telematico | Stato IUSENTRA |
| --- | --- | --- | --- | --- |
| Civile ordinario | `CC` / `JPW_SICID` | QBuilder SICID, `RicercaInformazioniFascicoloPerTipo`; documenti SICID via `idDoc`/`idCat`. | Wizard usa `RicercaInformazioniFascicoloPerTipo`, poi `ProfiloFascicolo`, `StoricoFascicolo`, `EstraiMasterDetailAtto`. | Allineato in `pct/polisWeb.py` e `tools/local_signer.py`; test su metodo, namespace, documenti e profilo. |
| Lavoro | `LAV` / `JPW_SIL_DISTR` | Famiglia SICID/Lavoro; registro `LAV`. | Wizard usa lo stesso metodo per tipo con registro lavoro. | Allineato; UI invia macroarea lavoro senza esporre codici tecnici. |
| Volontaria giurisdizione | `VG` / `JPW_SIVG` | Famiglia SICID/VG; registro `VG`. | Wizard usa `RicercaInformazioniFascicoloPerTipo`. | Allineato; registro distinto da civile ordinario. |
| Minorenni | `MIN` / `JPW_MIN` o `JPW_SIMIN` | v1.69 conferma anche consultazioni anonime Minorenni; import reale resta su sessione autenticata. | Wizard tratta `MIN` come registro specifico con metodo per tipo. | Allineato per import reale; anonimo catalogato come non sostitutivo del flusso fascicolo. |
| Esecuzioni mobiliari | `ESM` / `JPW_SIECIC` | QBuilder SIECIC; `RicercaInformazioniFascicoloPerNumero`, documenti SIECIC con namespace dedicato. | Wizard usa `RicercaInformazioniFascicoloPerNumero`, conserva `registro=ESM` e passa `idDfa` su dettaglio/documenti. | Allineato nel percorso esplicito; il fallback generico SIECIC resta solo per compatibilità già testata. |
| Esecuzioni immobiliari | `ESIM` / `JPW_SIECIC` | Come SIECIC, ma registro `ESIM`. | Wizard non accorpa con `ESM`: cambia `registro` e conserva `idDfa`. | Allineato; test `ESIM` verifica metodo numero, registro e `idDfa`. |
| Procedure concorsuali | `FALL` / `JPW_SIECIC` | Come SIECIC, con parti/pendenze concorsuali. | Wizard usa `RicercaInformazioniFascicoloPerNumero` e poi parti concorsuali (`ElencoPartiPC`). | Allineato per ricerca/profilo/documenti; parti PC da mantenere nel parser di dettaglio. |
| Giudice di Pace | `GP`/`GDP` / `JPW_SIGP` | v1.69 conferma SIGP e namespace/documenti SIGP; ricerca per RMO è nel catalogo. | Wizard usa metodo per tipo se c'è numero; usa `RicercaInformazioniFascicoloPerRMO` se si cerca per anno/archivio senza numero. | Allineato; test dedicato su `RicercaInformazioniFascicoloPerRMO`. |
| Cassazione civile | `CASSCI` / `JPW_CASSCI` | QBuilder Cassazione civile: `QC_Ricorsi`, `QC_FascicoloInformatico`, notifiche da ritirare e documenti dedicati. | Accesso PolisWeb usa URL dedicato `registroRicerca=CASSCI`; wizard civile usa `QC_Ricorsi`. | Allineato; `InvocationDomain` senza `group`, metodo `QC_Ricorsi`. |
| Cassazione penale | `CASSPE` / `JPW_CASSPE` | QBuilder Cassazione penale: `QP_Ricorsi`; ricevute PEC Cassazione civile/penale hanno servizio dedicato. | Accesso PolisWeb ha URL dedicato `registroRicerca=CASSPE`; il wizard import letto è più ricco sul civile. | Allineato da fonte ministeriale e Accesso PolisWeb; metodo `QP_Ricorsi` testato. |
| UNEP | Registri UNEP | Servizi distinti, non fascicolo civile ordinario. | Voci e cataloghi separati. | Tenere fuori dall'import fascicolo PST fino a canale dedicato notifiche/UNEP. |

## Controllo PIN e sessione

Studio Telematico non salva il PIN come dato applicativo: carica il certificato web e riusa la sessione/oggetto certificato lungo ricerca, profilo, storico, master/detail e download. IUSENTRA deve mantenere la stessa logica:

- una sola autenticazione per visualizzare/leggere il fascicolo finché la sessione è valida;
- un solo lotto per scaricare più documenti;
- nessun download documento per documento se moltiplica la richiesta PIN;
- nessun salvataggio del PIN;
- separazione tra certificato web PST e firma digitale qualificata.

Presidio codice: `tools/local_signer.py` usa cache sessione PST, preparazione sessione autenticata e batch documenti; i test `test_local_signer.py` presidiano riuso sessione, batch e id documento/catalogo.

## Controllo documenti

La fonte PST e Studio Telematico distinguono gli identificativi:

- `idDocumento` / `idDoc`: atto o documento da passare a master/detail e profilo documento;
- `idCat`: file scaricabile;
- `original=true`: duplicato/originale firmato;
- `original=false`: copia informatica con gestione delle informazioni di firma secondo il tipo documento.

Regola IUSENTRA: master/detail deve partire da `idDocumento` quando c'è; `idCat` serve al download. Se arriva un catalogo incompleto o legacy, il batch deve recuperare il miglior identificativo disponibile senza spezzare il lotto.

## Controllo notifiche e PEC

La fonte PST espone `NotificheDaRitirare`, comunicazioni di cancelleria, download notifiche/comunicazioni e ricevute PEC Cassazione. Studio Telematico conserva questi flussi come consultazione/download collegati alla pratica. IUSENTRA deve usarli per presidio PEC, agenda, scadenziario e notifiche web push solo dopo persistenza reale e deduplica.

Regola invariata: l'invio PEC operativo per deposito/notifica non parte dal server; resta dal PC locale tramite Local Signer/servizio locale. Questo controllo non autorizza SMTP server-side per invii legali.

## Controllo UI

I nomi Studio Telematico, QuickOrganizer, `JPW_*`, namespace, WSDL, `idDfa`, `idCat` e metodi QBuilder sono dettagli tecnici ammessi in codice, test e artifact. Non devono comparire nella UI utente.

La UI deve parlare così:

- `Civile ordinario`
- `Lavoro e previdenza`
- `Volontaria giurisdizione`
- `Minorenni`
- `Esecuzioni mobiliari`
- `Esecuzioni immobiliari`
- `Procedure concorsuali`
- `Giudice di Pace`
- `Cassazione civile`
- `Cassazione penale`

Test collegato: `tests/test_react_shell.py::test_pst_acquisizione_badge_tabella_non_mostra_codici_tecnici`.

## Decisioni operative

1. La fonte ministeriale attiva da citare nei nuovi lavori PolisWeb è PST v1.69, non v1.67.
2. Le consultazioni anonime v1.69 vanno trattate come catalogo/futuro accesso anonimo, non come import fascicolo autenticato.
3. Il confronto Studio Telematico resta il riferimento comportamentale per sequenza operativa, campo per campo.
4. IUSENTRA deve continuare a migliorare i flussi già testati senza regressioni: SIECIC generico già collaudato resta compatibilità; `ESM`, `ESIM`, `FALL` espliciti seguono il percorso ministeriale Studio con registro e `idDfa`.
5. Ogni nuovo intervento su questi flussi deve aggiornare questo file o il documento end-to-end principale, rilanciare i test mirati e, se modifica la UI/flusso visibile, fare prova reale su `127.0.0.1:8080`.

## Stato verifica di questo controllo

- Controllo fonte ministeriale: eseguito su PST v1.69 al 03/07/2026.
- Controllo Studio Telematico: eseguito sui sorgenti decompilati e sui cataloghi XML locali indicati sopra.
- Controllo IUSENTRA: eseguito su codice e test esistenti; non sono stati cambiati i payload runtime in questo file.
- Prova live PST con certificato ministeriale: non eseguita in questo passaggio, perché il controllo è documentale/codice; le prove reali precedenti sulla pagina `127.0.0.1:8080/portali/pst/acquisizione` restano documentate nel file end-to-end principale.
