# Generatori DatiAtto - Procedimenti concorsuali

Generato: 30/06/2026 21:39 (Europe/Rome).

Tipi deposito nel settore: 18.

Ogni riga riporta il metodo esatto chiamato da Studio Telematico, la root XML salvata, i dati richiesti dal metodo e i campi/codici che il menu abilita.

## Atti del Consulente

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Professionista_CONCORSUALI_SIECIC::AttoNonCodificato | Atto non codificato CTU (in materia concorsuale) | Create_DatiAtto_ProfSiecicConcorsuali_DepositoSemplice | ProfSiecicConcorsuali.DepositoSemplice | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, Rito |  |  |
| Professionista_CONCORSUALI_SIECIC::DepositoIntegrazioneCTU | Deposito integrazione CTU (in materia concorsuale) | Create_DatiAtto_ProfSiecicConcorsuali_DepositoSemplice | ProfSiecicConcorsuali.DepositoSemplice | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, Rito |  |  |
| Professionista_CONCORSUALI_SIECIC::DepositoRelazioneCTU | Deposito relazione CTU (in materia concorsuale) | Create_DatiAtto_ProfSiecicConcorsuali_DepositoSemplice | ProfSiecicConcorsuali.DepositoSemplice | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, Rito |  |  |
| Professionista_CONCORSUALI_SIECIC::DepositoRelazioneNotarile | Deposito Relazione Notarile (in materia concorsuale) | Create_DatiAtto_ProfSiecicConcorsuali_DepositoRelazioneNotarile | ProfSiecicConcorsuali.DepositoRelazioneNotarile | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, Rito |  |  |
| Professionista_CONCORSUALI_SIECIC::NotaDeposito | Nota di deposito del CTU (in materia concorsuale) | Create_DatiAtto_ProfSiecicConcorsuali_DepositoSemplice | ProfSiecicConcorsuali.DepositoSemplice | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, Rito |  |  |

## Atti del Curatore

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
|  | Atti del Curatore |  |  |  |  |  |

## Atti endo-processuali

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Parte_CONCORSUALI_SIECIC::AttoCostituzioneAvvocato | Atto Costituzione Avvocato (in materia concorsuale) | Create_DatiAtto_ParteSiecicConcorsuali_AttoCostituzioneAvvocato | ParteSiecicConcorsuali.AttoCostituzioneAvvocato | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, RiferimentoProcedimento, ModificheAnagrafica (+2) |  | VisualizzaAnagraficaProcedimento, needProcura |
| Parte_CONCORSUALI_SIECIC::AttoGenerico | Atto Generico (in materia concorsuale) | Create_DatiAtto_Parte_CONCORSUALI_SIECIC_AttoGenerico | ParteSiecicConcorsuali.AttoGenerico | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, RiferimentoProcedimento, Urgenza (+1) |  |  |
| Parte_CONCORSUALI_SIECIC::AttoGenericoCCIPU | Atto Generico (codice crisi impresa CCIPU) | Create_DatiAtto_Parte_CONCORSUALI_SIECIC_AttoGenericoCCIPU | AttoGenericoCCIPU | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, AnagraficaProcedimento (+2) |  |  |
| Parte_CONCORSUALI_SIECIC::AttoRichiestaVisibilità | Richiesta di visibilita' fascicolo (concorsuali) |  |  | AnagraficaProcedimento, ContributoUnificato, Rito |  | VisualizzaAnagraficaProcedimento, needProcura |
| Parte_CONCORSUALI_SIECIC::DepositoMemorie | Deposito Memorie (in materia concorsuale) | Create_DatiAtto_Parte_CONCORSUALI_SIECIC_AttoGenerico | ParteSiecicConcorsuali.AttoGenerico | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, RiferimentoProcedimento, Urgenza (+1) |  | VisualizzaAnagraficaProcedimento |
| Parte_CONCORSUALI_SIECIC::NotaDepositoCCI | Nota di deposito CCI (codice crisi impresa) | Create_DatiAtto_Parte_CONCORSUALI_SIECIC_NotaDepositoCCI | ParteSiecicConcorsuali.NotaDepositoCCI | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, RiferimentoProcedimento, Urgenza, AnagraficaProcedimento (+2) |  |  |
| Parte_CONCORSUALI_SIECIC::NoteTrattazione | Note di trattazione scritta (in materia concorsuale) | Create_DatiAtto_Parte_CONCORSUALI_SIECIC_AttoGenerico | ParteSiecicConcorsuali.AttoGenerico | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, RiferimentoProcedimento, Urgenza (+1) |  |  |

## Atti introduttivi

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Introduttivi_CONCORSUALI_SIECIC::RicorsoAmmissConcordatoPreventivoCCIPUIstanzaDebitore | Ricorso per ammissione concordato preventivo CCIPU, ad istanza del debitore | Create_DatiAtto_Introduttivi_SIECIC_Cartabia_RicorsoAmmissConcordatoPreventivoCCIPU | RicorsoAmmissConcordatoPreventivoCCIPU, ParteSiecicConcorsuali.AttoRichiestaVisibilita, ParteSiecicConcorsuali.AttoRichiestaVisibilita (+2) | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, RiferimentoProcedimento, ContributoUnificato (+7) |  | VisualizzaAnagraficaProcedimento, needProcura, needContributoUnificato |
| Introduttivi_CONCORSUALI_SIECIC::RicorsoDichiarazioneInsolvenzaCCIPUIstanzaCreditore | Ricorso per la dichiarazione dello stato d'insolvenza CCIPU, ad istanza del creditore | Create_DatiAtto_Introduttivi_SIECIC_Cartabia_RicorsoDichiarazioneInsolvenzaCCIPU | RicorsoDichiarazioneInsolvenzaCCIPU | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, ContributoUnificato, CodiceOggetto (+5) |  | VisualizzaAnagraficaProcedimento, needProcura, needContributoUnificato |
| Introduttivi_CONCORSUALI_SIECIC::RicorsoLiquidazioneControllataCCIPUIstanzaCreditore | Ricorso per liquidazione controllata CCIPU, ad istanza del creditore | Create_DatiAtto_Introduttivi_SIECIC_Cartabia_RicorsoLiquidazioneControllataCCIPU | RicorsoLiquidazioneControllataCCIPU | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, ContributoUnificato, CodiceOggetto (+5) |  | VisualizzaAnagraficaProcedimento, needProcura, needContributoUnificato |
| Introduttivi_CONCORSUALI_SIECIC::RicorsoLiquidazioneGiudizialeCCIPUIstanzaCreditore | Ricorso per liquidazione giudiziale CCIPU, ad istanza del creditore | Create_DatiAtto_Introduttivi_SIECIC_Cartabia_RicorsoLiquidazioneGiudizialeCCIPU | RicorsoLiquidazioneGiudizialeCCIPU | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, ContributoUnificato, CodiceOggetto (+5) |  | VisualizzaAnagraficaProcedimento, needProcura, needContributoUnificato |
| Introduttivi_CONCORSUALI_SIECIC::RicorsoOmologaAccordiRistrutturazioneCCIPUOrdinarioIstanzaDebitore | Ricorso per omologa accordi di ristrutturazione CCIPU, ad istanza del debitore | Create_DatiAtto_Introduttivi_SIECIC_Cartabia_RicorsoOmologaAccordiRistrutturazioneCCIPU | RicorsoOmologaAccordiRistrutturazCCIPU | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, AnagraficaProcedimento, ContributoUnificato, CodiceOggetto (+5) |  | VisualizzaAnagraficaProcedimento, needProcura, needContributoUnificato |
