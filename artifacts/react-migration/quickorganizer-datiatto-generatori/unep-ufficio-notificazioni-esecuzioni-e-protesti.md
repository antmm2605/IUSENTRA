# Generatori DatiAtto - UNEP - Ufficio Notificazioni, Esecuzioni e Protesti

Generato: 30/06/2026 21:39 (Europe/Rome).

Tipi deposito nel settore: 18.

Ogni riga riporta il metodo esatto chiamato da Studio Telematico, la root XML salvata, i dati richiesti dal metodo e i campi/codici che il menu abilita.

## Pagamenti

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Atti_UNEP::PagamentoRichiestaNotifica | Pagamento della richiesta di notifica | Create_DatiAtto_UNEP_PagamentoRichiesta | PagamentoRichiesta | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, Ufficio giudiziario, AnagraficaProcedimento, ContributoUnificato (+1) |  |  |
| Atti_UNEP::PagamentoRichiestaPignoramento | Pagamento della richiesta di pignoramento | Create_DatiAtto_UNEP_PagamentoRichiesta | PagamentoRichiesta | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, Ufficio giudiziario, AnagraficaProcedimento, ContributoUnificato (+1) |  |  |

## Richieste di Notifica

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Atti_UNEP::AttoCivileAPagamento | Richiesta di notifica di atto Civile a pagamento | Create_DatiAtto_UNEP_RichiestaNotifica | RichiestaParte | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+6) |  | VisualizzaAnagraficaProcedimento, needContributoUnificato |
| Atti_UNEP::AttoCivileDebito | Richiesta di notifica di atto Civile (a debito) | Create_DatiAtto_UNEP_RichiestaNotificaDebito | RichiestaParteDebito | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+6) |  | VisualizzaAnagraficaProcedimento, needContributoUnificato |
| Atti_UNEP::AttoEsenteLavoro | Richiesta di notifica di atto Lavoro (esente) | Create_DatiAtto_UNEP_RichiestaNotifica | RichiestaParte | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+6) |  | VisualizzaAnagraficaProcedimento, needContributoUnificato |
| Atti_UNEP::AttoPenaleAPagamento | Richiesta di notifica di atto Penale (a pagamento) | Create_DatiAtto_UNEP_RichiestaNotifica | RichiestaParte | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+6) |  | VisualizzaAnagraficaProcedimento, needContributoUnificato |
| Atti_UNEP::AttoPenaleDebito | Richiesta di notifica di atto Penale (a debito) | Create_DatiAtto_UNEP_RichiestaNotificaDebito | RichiestaParteDebito | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+6) |  | VisualizzaAnagraficaProcedimento, needContributoUnificato |

## Richieste di pignoramento

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Atti_UNEP::RichiestaPignoramentoImmobiliare | Richiesta di pignoramento immobiliare | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoImmobiliareADebito | Richiesta di pignoramento immobiliare (a debito) | Create_DatiAtto_UNEP_RichiestaPignoramentoADebito | RichiestaPignoramentoDebito | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoImmobiliareMateriaLavoro | Richiesta di pignoramento immobiliare (in materia di lavoro) | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoMobiliare | Richiesta di pignoramento mobiliare | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoMobiliareADebito | Richiesta di pignoramento mobiliare (a debito) | Create_DatiAtto_UNEP_RichiestaPignoramentoADebito | RichiestaPignoramentoDebito | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoMobiliareMateriaLavoro | Richiesta di pignoramento mobiliare (in materia di lavoro) | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoPressoTerzi | Richiesta di pignoramento presso terzi | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoPressoTerziADebito | Richiesta di pignoramento presso terzi (a debito) | Create_DatiAtto_UNEP_RichiestaPignoramentoADebito | RichiestaPignoramentoDebito | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |
| Atti_UNEP::RichiestaPignoramentoPressoTerziMateriaLavoro | Richiesta di pignoramento presso terzi (in materia di lavoro) | Create_DatiAtto_UNEP_RichiestaPignoramento | RichiestaPignoramento | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Urgenza (+5) | 610012 610012 - Espropriazione Immobiliare (CARTABIA), 510002 510002 - Espropriazione mobiliare presso terzi (+1) | VisualizzaAnagraficaProcedimento, needContributoUnificato, VisualizzaGrigliaTerzi |

## Richieste di restituzione

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Atti_UNEP::RichiestaRestituzioneSomme | Richiesta di restituzione somme in eccesso | Create_DatiAtto_UNEP_RichiestaRestituzioneSomme | RichiestaRestituzioneSomme | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, ValoreCausa (+3) |  | VisualizzaAnagraficaProcedimento |

## Richieste di ricerca beni da pignorare

| Chiave | Tipo deposito | Metodo | Root XML | Dati richiesti | Codici oggetto fissi | Flag attivi |
| --- | --- | --- | --- | --- | --- | --- |
| Atti_UNEP::RichiestaRicercaBeni | Richiesta di ricerca beni da pignorare ex art. 492-bis c.p.c. | Create_DatiAtto_UNEP_RichiestaRicercaBeni | RichiestaRicercaBeni | IndiceBusta, AttoPrincipale.id, Allegati in IndiceBusta, RefId deposito multiplo, Deposito multiplo, ContributoUnificato, CodiceOggetto, Ufficio giudiziario (+3) | 401003 401003 - Ricerca con modalità telematiche dei beni da pignorare (art. 492 bis. c.p.c.) | VisualizzaAnagraficaProcedimento, needContributoUnificato |
