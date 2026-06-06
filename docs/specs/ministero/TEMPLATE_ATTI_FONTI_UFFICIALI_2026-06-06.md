# Fonti ufficiali Template Atti - verifica 6 giugno 2026

Questa nota versiona le fonti ufficiali usate dal registro
`pct/template_atti_legal_sources.py` per Template Atti, editor, Lex AI e RAG
Legal. Non contiene testo normativo copiato: conserva fonte, ambito, ruolo,
URL ufficiale, data di consultazione e limite operativo.

## Regola di copertura

- Una fonte `base_comune` non chiude la copertura del modello.
- Un modello è coperto solo se ha almeno una fonte professionale valida e
  almeno una fonte collegata tra `telematica`, `secondaria_collegata`,
  `deontologia`, `ordinamento_professionale` o `autorita`, non transitoria, con
  URL ufficiale e data di verifica aggiornata.
- Le fonti primarie principali non bastano da sole: dove esistono decreti
  attuativi, specifiche tecniche, regole telematiche, fonti di autorità
  competente, provvedimenti CNF o fonti operative pubbliche, devono essere
  mappate nel registro e rese visibili in Ricerca Legale.
- Le fonti transitorie, come la legge fallimentare previgente, possono essere
  mostrate solo con avviso e non sostituiscono la fonte vigente.
- Codice deontologico e ordinamento forense sono trasversali ma devono essere
  agganciati a modelli in cui incidono davvero: incarico, preventivo, compenso,
  segreto, conflitto, informazione al cliente, mandato, rinuncia/revoca,
  condotta processuale e rapporti con ex clienti o controparti.

## Audit eseguito

- Script: `scripts/audit_template_atti_legal_sources.py --fail-on-issues`
- Report JSON completo:
  `artifacts/template-atti/template-atti-official-sources-audit-2026-06-06.json`
- Report Markdown completo:
  `artifacts/template-atti/template-atti-official-sources-audit-2026-06-06.md`
- Esito: 1512/1512 righe modello OK tra catalogo unificato e compilatore atti,
  0 problemi modello, 0 problemi fonte.

## Matrice fonte per macro-area

| Area | Fonti principali documentate |
| --- | --- |
| Civile ordinario, memorie, impugnazioni | Codice civile, Codice di procedura civile, D.Lgs. 149/2022, D.Lgs. 164/2024, D.M. 44/2011, D.M. 217/2023, art. 196-quater disp. att. c.p.c., specifiche PCT/PST, art. 163, 167, 171-ter, 281-decies e ss. c.p.c. |
| Cautelare, monitorio, possessorio | Codice di procedura civile, artt. 633 e ss., 669-bis e ss., 700, 670, 671, 703 c.p.c., D.M. 44/2011, D.M. 217/2023 e specifiche PCT/PST. |
| Esecuzioni e notifiche | Codice di procedura civile, D.Lgs. 149/2022, D.Lgs. 164/2024, D.M. 44/2011, D.M. 217/2023, specifiche PCT/PST, L. 53/1994, D.P.R. 68/2005, CAD art. 48, BDAG/PVP dove rilevano vendite e procedure. |
| Penale | Codice penale, Codice di procedura penale, D.Lgs. 150/2022, D.M. 217/2023, specifiche PDP/PPT del Ministero della Giustizia. |
| Amministrativo e appalti | Codice del processo amministrativo, Decreto Presidente Consiglio di Stato 22 maggio 2020, regole tecnico-operative PAT 2025, D.Lgs. 36/2023, ANAC PCP e precontenzioso. |
| Tributario | D.Lgs. 546/1992, D.Lgs. 220/2023, D.M. 163/2013 e specifiche MEF/Giustizia Tributaria per il Processo Tributario Telematico. |
| ADR, mediazione e negoziazione | D.Lgs. 28/2010, D.L. 132/2014, D.Lgs. 149/2022, D.Lgs. 216/2024, D.M. 150/2023, registro ministeriale organismi e modifica CDF Titolo IV/62-bis pubblicata in GU 1 settembre 2025. |
| Famiglia, minori, volontaria giurisdizione | Codice civile, Codice di procedura civile, L. 898/1970, L. 184/1983, D.Lgs. 154/2013, L. 76/2016, D.Lgs. 149/2022. |
| Lavoro | Codice di procedura civile rito lavoro, L. 300/1970, L. 604/1966, D.Lgs. 23/2015, D.Lgs. 81/2015, D.Lgs. 151/2015, D.M. 15 dicembre 2015 e prassi INL sul tentativo obbligatorio licenziamento GMO. |
| Bancario e finanziario | TUB, TUF, ABF Banca d'Italia, ACF Consob. |
| Assicurazioni e responsabilità civile | Codice assicurazioni private, D.M. 215/2024, provvedimento IVASS sull'Arbitro Assicurativo, Codice della strada e D.P.R. 495/1992 per sinistri e sanzioni stradali. |
| Consumo e comunicazioni | Codice del consumo, delibere AGCOM ConciliaWeb 203/18/CONS e 194/23/CONS, autorità competenti per settore. |
| Privacy e dati personali | GDPR su Garante Privacy/EUR-Lex e Codice privacy nazionale. |
| Proprietà intellettuale | Codice proprietà industriale, UIBM/MIMIT per deposito telematico, legge diritto d'autore e SIAE come fonte operativa collegata per repertori e gestione diritti. |
| Crisi e concorsuale | Codice della crisi d'impresa e dell'insolvenza, D.Lgs. 136/2024, Portale Vendite Pubbliche/BDAG quando rilevano vendite e flussi; legge fallimentare solo come fonte transitoria. |
| Immigrazione e protezione internazionale | D.Lgs. 286/1998, D.Lgs. 25/2008, Ministero dell'Interno, Commissioni territoriali e Commissione nazionale per il diritto di asilo. |
| Locazioni | L. 392/1978, L. 431/1998, Agenzia Entrate/RLI Web, registrazione entro 30 giorni, adempimenti successivi e cedolare secca. |
| Studio, incarichi, compensi e deontologia | L. 247/2012, D.M. 55/2014, L. 49/2023, CDF artt. 24, 25, 25-bis, 26, 27, 28, 29, 68 e modifiche GU 2025/2026. |

## Fonti web ufficiali consultate

- Normattiva: codici, leggi, decreti legislativi, decreti correttivi, fonti
  nazionali vigenti e fonti transitorie marcate come tali.
- Portale dei Servizi Telematici del Ministero della Giustizia: specifiche PCT
  e deposito penale telematico, BDAG/PVP per vendite e procedure.
- Giustizia Amministrativa: decreto e regole tecnico-operative PAT aggiornate.
- Giustizia Tributaria/MEF: D.M. 163/2013 e specifiche tecniche PTT.
- Gazzetta Ufficiale: comunicati CNF su Codice deontologico 2025 e art. 25-bis
  2026.
- Consiglio Nazionale Forense: Codice deontologico forense e articoli
  specifici.
- Garante Privacy ed EUR-Lex: GDPR.
- Banca d'Italia ABF, Consob ACF, IVASS Arbitro Assicurativo, AGCOM e ANAC:
  fonti delle autorità competenti.
- Ministero delle Imprese e del Made in Italy/UIBM: deposito telematico per
  marchi, brevetti, disegni, modelli, istanze connesse e rinnovi.
- SIAE: fonte operativa collegata per repertori, tutela e gestione dei diritti
  d'autore.
- Agenzia delle Entrate: RLI Web, registrazione contratti di locazione,
  adempimenti successivi, ricevute e cedolare secca.
- Ministero dell'Interno: protezione internazionale, Commissioni territoriali e
  Commissione nazionale per il diritto di asilo.

## Regola RAG/Lex

Il RAG Legal deve indicizzare questa nota, il registro Python e i report audit.
Lex AI può usare le fonti per suggerire controlli e contenuti redazionali, ma
deve distinguere sempre norma certa, regola tecnica, fonte deontologica, fonte
di autorità, fonte transitoria e punto da verificare dall'avvocato. Le stesse
fonti sono pubblicate nella Ricerca Legale come schede `template-atti-source:*`
con URL, autorità, data di consultazione, ruolo, modello collegato e limiti.
