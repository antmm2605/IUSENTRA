# Audit specialistico delle famiglie documentali del fascicolo

- Data: 24/08/2026, fuso `Europe/Rome`.
- Stato: audit delle fonti e della tassonomia in corso; nessuna modifica
  applicativa è inclusa in questo dossier.
- Oggetto: verifica della copertura effettiva del vocabolario di 708 modelli
  che IUSENTRA deve trasformare in un catalogo documentale governato.

## Criterio di chiusura

Una riga è coperta soltanto se ha almeno tre fonti ufficiali, indipendenti e
pertinenti al suo procedimento: norma vigente, canale/procedura o autorità
competente, e fonte di controllo o interpretazione istituzionale. Per le
attività esclusivamente interne allo studio, la seconda e la terza fonte sono
professionali, deontologiche e privacy; non viene attribuito un rito giudiziario
inesistente.

L'associazione è semantica: `area`, `branca`, `sottobranca`, rito e canale.
Un prefisso storico del codice modello non è una prova di materia. In
particolare, una corrispondenza testuale di `TMP-TRIB` a una fonte civile non è
valida e non contribuisce al presente audit.

Le fonti con identificativo semplice sono registrate in
`pct/template_atti_legal_sources.py`; le identificazioni `snapshot:` fanno
riferimento al manifest con URL e SHA-256 in
`docs/specs/ministero/fonti_ufficiali/2026-08-24/README.md`; le fonti che il
fornitore rende leggibili solo con browser reale hanno identificativo `browser:`
e prova separata in
`docs/specs/ministero/fonti_ufficiali/2026-08-24/fonti_browser_verificate/`.

La fonte transitoria `normattiva_legge_fallimentare_267_1942_transitoria` è
esclusa dalle triadi: non è idonea a soddisfare il requisito di vigenza.

## Verifica attuale delle fonti esistenti

Il 24/08/2026 la verifica è stata svolta in due passaggi: risposta tecnica e
contenuto effettivo. Un `200` non è considerato valido se l'URL finale è una
barriera, una pagina generica o un documento diverso. Il controllo ha escluso
gli endpoint PTT che restituiscono `500`, le voci EUR-Lex che reindirizzano alla
Gazzetta del giorno e le voci ACF che non possono essere interrogate da un job
automatico senza barriera Radware. PTT è sostituito da Gazzetta Ufficiale e
circolari MEF; la giurisprudenza UE da CURIA; GDPR da Garante Privacy. Il
portale normativo ACF è stato invece controllato materialmente nel browser
integrato: ha mostrato normativa UE, nazionale e Consob, inclusi delibera
22721/2023 e testo consolidato del regolamento; la prova è nel registro
`browser:acf-normativa-2026`.

Le fonti deprecate non sono selezionabili dal resolver. Una verifica periodica
che non riesca a confermare una fonte attiva deve mettere in revisione la
regola, mai promuovere o conservare una classificazione certa.

### Riconvalida della campagna

La riconvalida locale del 24/08/2026 ha dato esito positivo su tutti i controlli
che possono attestare la ricerca: 55 acquisizioni principali e 57 copie di
triade hanno impronta SHA-256 corrispondente e nessun contenuto di errore,
barriera Radware o reindirizzamento improprio; le 57 copie contengono almeno
un termine semantico dichiarato dalla rispettiva fonte; i 25 profili risolvono
solo fonti attive, snapshot improntati o la prova browser esplicita ACF e ne
hanno almeno tre. La matrice di 47 sottofamiglie coincide inoltre, per chiave
`area`/`branca`/`sottobranca` e quantità, con tutti i 708 modelli effettivi del
catalogo.

Questo attesta il 100% della copertura di ricerca e di mappatura del corpus
versionato, non l'operatività dell'applicazione: l'audit funzionale resta
aperto fino al completamento e alla prova reale delle fasi applicative.

## Profili di fonte approvati

| Profilo | Fonti indipendenti minime | Campo di applicazione |
| --- | --- | --- |
| `CIV-PCT` | `normattiva_codice_civile`; `normattiva_cpc`; `pst_specifiche_tecniche_pct`; `corte_cassazione_sentenzeweb` | Cognizione civile e documenti PCT. |
| `CIV-MON-CAU` | `normattiva_cpc`; `cpc_procedimento_monitorio`; `cpc_procedimenti_cautelari_uniformi`; `pst_specifiche_tecniche_pct` | Monitorio, cautelare, urgenza, possessorio e sfratto. |
| `CIV-ESE` | `normattiva_cpc`; `pst_specifiche_tecniche_pct`; `pst_portale_vendite_pubbliche_specifiche_concorsuali`; `corte_cassazione_sentenzeweb` | Esecuzioni, pignoramenti, opposizioni e vendite. |
| `CIV-IMP` | `normattiva_cpc`; `pst_specifiche_tecniche_pct`; `corte_cassazione_sentenzeweb` | Appello, reclamo, cassazione e rimedi civili. |
| `CIV-NOT` | `normattiva_legge_53_1994_notifiche`; `normattiva_dpr_68_2005_pec`; `pst_dgsia_2024_art_27_attestazione_conformita`; `normattiva_cad_art_48` | Notifica, PEC, attestazione, UNEP e ricevute. |
| `CIV-PROC` | `normattiva_cpc`; `normattiva_l_247_2012_ordinamento_forense`; `cnf_codice_deontologico_forense`; `pst_specifiche_tecniche_pct` | Procure, deleghe, mandato e domiciliazione. |
| `CIV-GDP` | `normattiva_cpc`; `normattiva_d_lgs_150_2011_riti`; `pst_specifiche_tecniche_pct`; `corte_cassazione_sentenzeweb` | Giudice di pace. |
| `LOC` | `normattiva_legge_392_1978_locazioni`; `normattiva_legge_431_1998_locazioni_abitative`; `agenzia_entrate_rli_locazioni` | Locazioni, immobili e condominio. |
| `RCD` | `normattiva_codice_civile`; `normattiva_codice_strada_285_1992`; `normattiva_codice_assicurazioni_209_2005`; `ivass_arbitro_assicurativo` | Responsabilità civile, sinistri e danni. |
| `ADR` | `normattiva_d_lgs_28_2010_mediazione`; `normattiva_dm_150_2023_mediazione`; `giustizia_registro_mediazione_dm_150_2023`; `normattiva_dl_132_2014_negoziazione` | Mediazione, negoziazione, arbitrato e relativi verbali/accordi. |
| `PAT` | `normattiva_cpa`; `giustizia_amministrativa_pat`; `giustizia_amministrativa_dpcs_2025_pat`; `giustizia_amministrativa_ricerche_decisioni` | Processo amministrativo e Formweb. |
| `CONC` | `normattiva_codice_crisi_14_2019`; `normattiva_d_lgs_136_2024_correttivo_crisi`; `pst_portale_vendite_pubbliche_specifiche_concorsuali`; `snapshot:pvp-specifiche-2024-v1.2` | Crisi, procedure concorsuali, PVP e BDAG. |
| `BAN` | `normattiva_tub_385_1993`; `abf_normativa`; `bancaditalia_abf_disposizioni_2025`; `browser:acf-normativa-2026` | Bancario, finanziario, ABF e ACF. |
| `SOC` | `normattiva_codice_civile`; `normattiva_tuf_58_1998`; `snapshot:registro-imprese-bilanci-2026`; `snapshot:registro-imprese-specifiche-2026` | Società, contratti, bilanci e depositi Registro Imprese. |
| `LAV` | `normattiva_l_300_1970_statuto_lavoratori`; `normattiva_l_604_1966_licenziamenti`; `inl_contestazione_licenziamento_gmo`; `snapshot:inps-ricorso-previdenziale-2026` | Lavoro, previdenza, INPS, INAIL e impugnazioni. |
| `VGS` | `normattiva_codice_civile`; `normattiva_cpc`; `snapshot:vg-dm-2024`; `snapshot:vg-specifiche-2023`; `snapshot:successione-certificato-giustizia-2026` | Volontaria giurisdizione, protezione e successioni. |
| `FAM` | `normattiva_codice_civile`; `normattiva_cpc`; `normattiva_d_lgs_149_2022_cartabia_civile`; `corte_cassazione_sentenzeweb` | Famiglia, minori, separazione, divorzio e tutele. |
| `PEN` | `normattiva_cpp`; `normattiva_d_lgs_150_2022_cartabia_penale`; `pst_pdp_penale`; `pst_specifiche_penale_2024`; `corte_cassazione_sentenzeweb` | Difesa penale, persona offesa, PDP e PPT. |
| `TRIB` | `normattiva_d_lgs_546_1992_tributario`; `normattiva_dm_163_2013_ptt`; `snapshot:ptt-specifiche-2015-gu`; `snapshot:ptt-modifica-2017-gu`; `snapshot:ptt-modifica-2023-gu`; `snapshot:ptt-circolare-2019`; `giustizia_tributaria_def_giurisprudenza` | Processo tributario telematico, SIGIT e contenzioso. |
| `STD` | `normattiva_l_247_2012_ordinamento_forense`; `cnf_codice_deontologico_forense`; `normattiva_dm_55_2014_parametri_forensi`; `snapshot:agid-gestione-documentale-2026` | Atti di studio, incarico, compensi, fascicolo interno e conservazione. |
| `IPD` | `normattiva_cpi_30_2005`; `uibm_deposito_telematico_proprieta_industriale`; `normattiva_diritto_autore_633_1941`; `snapshot:uibm-marchi-disegni-2026` | Proprietà industriale, diritto d'autore, media e web. |
| `IMM` | `normattiva_tu_immigrazione_286_1998`; `normattiva_d_lgs_25_2008_protezione_internazionale`; `interno_protezione_internazionale_commissioni`; `snapshot:protezione-internazionale-guida-2024` | Permessi, cittadinanza e protezione internazionale. |
| `PRI` | `normattiva_privacy_196_2003`; `garante_gdpr`; `snapshot:garante-privacy-regolamento-reclami-2019` | Privacy, GDPR, reclami e compliance. |
| `STR` | `normattiva_codice_civile`; `normattiva_d_lgs_28_2010_mediazione`; `normattiva_dm_150_2023_mediazione`; `cnf_codice_deontologico_forense` | Diffide, accordi, pareri e recupero stragiudiziale. |
| `CON` | `normattiva_codice_consumo_206_2005`; `agcom_conciliaweb`; `agcom_delibera_203_18_conciliaweb`; `snapshot:arera-tico-209-2016` | Consumatori, utenze e conciliazione regolatoria. |

## Matrice integrale: 47 sottofamiglie e 708 modelli

Ogni riga eredita soltanto il profilo indicato, non fonti generiche ottenute da
somiglianza del nome del file. Il totale dei modelli è 708.

| Area | Branca | Sottofamiglia | Modelli | Profilo | Esito della mappatura |
| --- | --- | --- | ---: | --- | --- |
| ADR | ADR, mediazione, negoziazione, arbitrato | Mediazione e arbitrato | 14 | `ADR` | Triade definita. |
| Amministrativo | Amministrativo | Ricorsi, memorie e cautelare | 6 | `PAT` | Triade definita. |
| Amministrativo | Giustizia amministrativa | Ricorsi e appelli | 3 | `PAT` | Triade definita. |
| Civile | Civile ordinario | Introduttivi e difensivi | 19 | `CIV-PCT` | Triade definita. |
| Civile | Civile ordinario | Introduttivi, difensivi e istanze | 34 | `CIV-PCT` | Triade definita. |
| Civile | Esecuzioni | Precetti, pignoramenti e opposizioni | 13 | `CIV-ESE` | Triade definita. |
| Civile | Esecuzioni civili | Espropriazione e opposizioni | 17 | `CIV-ESE` | Triade definita. |
| Civile | Impugnazioni | Appello, cassazione e rimedi | 13 | `CIV-IMP` | Triade definita. |
| Civile | Impugnazioni civili | Appelli, reclami e rimedi impugnatori | 12 | `CIV-IMP` | Triade definita. |
| Civile | Monitorio e cautelare | Ricorsi d'urgenza, monitori e sfratti | 13 | `CIV-MON-CAU` | Triade definita. |
| Civile | Monitorio, cautelare e possessorio | Ricorsi speciali | 12 | `CIV-MON-CAU` | Triade definita. |
| Civile | Notifiche e adempimenti | UNEP, notifica in proprio e allegati | 9 | `CIV-NOT` | Triade definita. |
| Civile | Procure e deleghe | Mandati e domiciliazioni | 11 | `CIV-PROC` | Triade definita. |
| Civile | UNEP e notificazioni | Notifiche, depositi e fascicolo telematico | 1 | `CIV-NOT` | Triade definita. |
| Crisi d'impresa e insolvenza | Procedure concorsuali e crisi | Concorsuale | 15 | `CONC` | Triade definita. |
| Diritto amministrativo | Amministrativo | PAT e contenzioso amministrativo | 18 | `PAT` | Triade definita. |
| Diritto bancario | Bancario e finanziario | Bancario e finanziario | 12 | `BAN` | Triade definita. |
| Diritto civile | Core civile | Contenzioso ordinario | 38 | `CIV-PCT` | Triade definita. |
| Diritto civile | Giudice di Pace | Giudice di Pace | 16 | `CIV-GDP` | Triade definita. |
| Diritto civile | Locazioni, condominio e immobili | Locazioni, condominio e immobili | 21 | `LOC` | Triade definita. |
| Diritto civile | Procedimento monitorio | Procedimento monitorio | 18 | `CIV-MON-CAU` | Triade definita. |
| Diritto civile | Recupero crediti e stragiudiziale | Recupero crediti e diffide | 20 | `STR` | Triade definita. |
| Diritto civile | Responsabilità civile e danni | Responsabilità civile | 15 | `RCD` | Triade definita. |
| Diritto commerciale | Commerciale e societario | Societario | 16 | `SOC` | Triade definita. |
| Diritto del lavoro | Lavoro e previdenza | Lavoro e previdenza | 20 | `LAV` | Triade definita. |
| Diritto delle persone e successioni | Volontaria giurisdizione e successioni | Volontaria giurisdizione | 19 | `VGS` | Triade definita. |
| Diritto di famiglia | Famiglia, minori e persone | Famiglia e minori | 25 | `FAM` | Triade definita. |
| Diritto penale | Penale | Difesa penale e persona offesa | 25 | `PEN` | Triade definita. |
| Diritto processuale civile | Cautelari e urgenza | Cautelari e urgenza | 17 | `CIV-MON-CAU` | Triade definita. |
| Diritto processuale civile | Esecuzioni | Esecuzioni | 33 | `CIV-ESE` | Triade definita. |
| Diritto tributario | Tributario | Contenzioso tributario | 20 | `TRIB` | Triade definita. |
| Famiglia e Persone | Famiglia e persone | Separazione, divorzio e volontaria giurisdizione | 10 | `FAM` | Triade definita. |
| Famiglia e Persone | Famiglia, persone e volontaria giurisdizione | Separazione, divorzio e tutele | 14 | `FAM` | Triade definita. |
| Gestione studio | Atti interni di studio | Operatività interna | 20 | `STD` | Triade definita. |
| IP, media e digitale | Proprietà intellettuale e digitale | Proprietà intellettuale e web | 15 | `IPD` | Triade definita. |
| Immigrazione | Immigrazione e cittadinanza | Ricorsi, permessi e protezione | 5 | `IMM` | Triade definita. |
| Lavoro e Previdenza | Lavoro e previdenza | Ricorsi e impugnazioni | 10 | `LAV` | Triade definita. |
| Lavoro e Previdenza | Lavoro e previdenza | Ricorsi, memorie e previdenza | 8 | `LAV` | Triade definita. |
| Penale | Difesa penale | Atti difensivi e richieste | 12 | `PEN` | Triade definita. |
| Penale | Penale | Difesa, istanze e impugnazioni | 22 | `PEN` | Triade definita. |
| Privacy e protezione dati | Privacy e compliance | GDPR e compliance | 11 | `PRI` | Triade definita. |
| Societario | Societario | Pareri, contratti e contenzioso | 7 | `SOC` | Triade definita. |
| Stragiudiziale | Diffide e atti stragiudiziali | Richieste, intimazioni e lettere | 8 | `STR` | Triade definita. |
| Stragiudiziale | Stragiudiziale | Comunicazioni, accordi e pareri | 21 | `STR` | Triade definita. |
| Tributario | Contenzioso tributario | Ricorso e difese | 3 | `TRIB` | Triade definita. |
| Tributario | Tributario | Ricorsi, controdeduzioni e appelli | 5 | `TRIB` | Triade definita. |
| Tutela del consumatore | Consumatori e utenze | Consumo e utenze | 12 | `CON` | Triade definita. |

## Vincoli per la fase applicativa successiva

1. Il codice mapperà ogni documento al profilo semantico della presente
   matrice prima di consultare le fonti; nessuna regola sarà autorizzata dal
   solo prefisso storico.
2. Ogni regola puntuale conserverà gli identificativi della sua triade, la
   versione, il checksum della copia e il motivo dell'applicazione.
3. Fonti non raggiungibili o sostituite produrranno revisione della regola,
   non classificazione silenziosa o certezza fittizia.
4. Una pagina che richieda browser reale non è interrogata da job automatici:
   il suo identificativo `browser:` impone la verifica materiale programmata e,
   in caso di esito negativo, la revisione umana della regola interessata.
5. Questa è copertura di ricerca e progettazione. Il 100% funzionale richiede
   ancora la persistenza SQL, il resolver dei profili, la pipeline, i test e la
   prova reale nella copia locale dell'utente; nessuno di tali punti è qui
   dichiarato completato.
