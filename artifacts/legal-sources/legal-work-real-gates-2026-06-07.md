# Audit gate reali Lex/Ricerca Legale - 7 giugno 2026

Questo audit registra i gate reali introdotti dopo la verifica dell'utente: un lavoro su Lex/RAG/Ricerca Legale non è chiuso quando compila o quando una fonte è censita, ma solo quando la domanda operativa dell'avvocato produce una risposta utile, leggibile e verificabile.

## Regola applicata

- Ogni blocco consegnato deve avere domanda reale, output atteso, sorgenti interrogate, test o prova locale e stato.
- Se i dati esistono ma Lex risponde `0` o `Non ho trovato dati reali sufficienti`, il gate è rosso.
- Se la risposta elenca solo estratti OCR o metadati senza rischi, lacune e prossimi passi, il gate è rosso.
- Se Ricerca Legale mostra categorie generiche invece di riferimenti nominali, il gate è rosso.

## Gate verificati

| Area | Domanda reale | Esito atteso per l'avvocato | Verifica 7 giugno 2026 |
| --- | --- | --- | --- |
| Riforma civile Cartabia | `Fonte correttiva collegata alla riforma civile Cartabia per controllare rito, decorrenze, famiglia, esecuzione, notifiche e ADR.` | Route fonti ufficiali/pratica legale; D.Lgs. 149/2022, D.Lgs. 164/2024, c.p.c., uso operativo, pratiche collegate e fonte ufficiale. | Verde: `test_lex_risponde_a_domanda_reale_su_correttivo_cartabia_civile_senza_perdersi_sulle_notifiche`; prova manuale mostra D.Lgs. 149/2022 e D.Lgs. 164/2024. |
| Fascicolo attivo/RAG | `Fammi una sintesi del fascicolo attivo: documenti chiave, rischi aperti, cosa manca e prossimi passi.` | Sintesi operativa con inquadramento, documenti chiave, rischi, documenti mancanti e prossimi passi; niente risposta vuota e niente solo estratti OCR. | Verde: nuovi test su fascicolo generico e caso scolastico `Betti C. MIM`; prova manuale produce sezione scolastica/lavoro pubblico con contratti, prescrizione, stato di servizio, buste paga, procura e prossimi passi. |
| PEC prova completa | `Qual è la prova completa di questa notifica?` | Se nel DB ci sono accettazione e consegna, Lex deve mostrare prove complete, ricevute collegate, orari italiani e destinatari. | Verde su test alias tenant e su database reale locale: risolve `tenant-8bf98719c459` e non `antonella-mammola`; risposta reale: `Fascicoli prova notifica ricostruiti: 2 (2 completi)` con accettazione/consegna. |
| PEC ricevute oggi | `Quali PEC ricevute oggi generano scadenze?` | Il confronto della data deve avvenire in ora italiana, non sui primi caratteri della data salvata in UTC. | Verde: `tests/test_pec_control_tower.py` completo. Corretto filtro `deadlines_today` con conversione `Europe/Rome`. |
| Ricerca Legale con precedenti nominativi | Query su PEI, lavoro, appalti, penale/giustizia riparativa | La UI deve esporre sentenze e fonti nominali, non categorie astratte. | Verde: Corte cost. 80/2010, 275/2016, 194/2018, 128/2024; Cons. Stato A.P. 10/2020, 12/2020; Cass. S.U. pen. 5166/2026. |
| Audit matrice pratica | Audit completo matrice pratica legale | 25 aree, riferimenti nominali coperti, web research registrata e campi professionali completi. | Verde: `python scripts\audit_legal_practice_matrix.py --fail-on-incomplete --output-dir artifacts\legal-sources` -> 25 aree, 114 riferimenti, 24 web research, 0 issue, 100%. |

## Correzioni applicate

- Routing Lex: le domande su riforma civile/correttivo Cartabia vanno a fonti ufficiali/pratica legale, non alle notifiche interne.
- Response composer fonti: le schede pratica e i riferimenti nominali entrano nella risposta ufficiale, con fonte, uso, passaggi e domande Lex.
- Response composer fonti/PDF: se la domanda riguarda un R.G., una questione penale o un allegato ufficiale, la risposta sul PDF ufficiale prevale sul catalogo Centro Fonti. Questo evita che Lex risponda con una lista di fonti operative quando deve invece sintetizzare scheda, allegato, norme, udienza e discrepanza R.G.
- Response composer fascicolo: la sintesi non è più un elenco di estratti; produce sezioni operative per avvocato.
- PEC Control Tower: la risoluzione tenant sceglie l'alias autorizzato dello stesso studio con dati giuridici completi, non il primo identificativo trovato.
- PEC prova completa: le prove complete sono ordinate prima delle parziali e mostrano ricevute di accettazione/consegna collegate.
- PEC oggi: la data della PEC viene convertita in ora italiana prima del confronto con `oggi`, così i messaggi vicini alla mezzanotte non spariscono dal presidio.
- Ricerca Legale: filtri materia impediscono che fonti generiche o di altra materia mascherino PEI, deontologia, Cartabia, penale, lavoro e appalti.
- Ricerca Legale: le ricerche per ambiente/immigrazione e concorsi pubblici mantengono i portali/autorità nominati anche quando la query contiene D.Lgs., D.P.R. o rito TAR; le sentenze esatte restano invece filtrate per organo e numero.
- Ricerca Legale: per contenuti correnti come tassi/soglie usura, una scheda nominale non chiude la ricerca se manca contenuto ufficiale o tabella normativa reale; il fallback ufficiale viene mantenuto e i risultati live non vengono tagliati prima della UI.

## Gate rilanciati dopo le correzioni

- `python -m pytest tests\test_react_legal_intelligence_search.py -q --tb=short` -> 35/35 verde.
- `python -m pytest tests\test_lex_operational_knowledge.py::test_rg_questione_penale_usa_archivio_legale_e_allegato_ufficiale tests\test_lex_operational_knowledge.py::test_rg_questione_penale_risponde_a_domande_da_avvocato tests\test_lex_operational_knowledge.py::test_rg_questione_penale_articoli_attiva_web_libero_distinto_dalla_fonte_ufficiale tests\test_lex_operational_knowledge.py::test_rg_questione_penale_non_trascina_fonti_non_pertinenti tests\test_lex_operational_knowledge.py::test_rg_questione_penale_prefisso_template_resta_fonte_ufficiale tests\test_lex_operational_knowledge.py::test_rg_questione_penale_end_to_end_da_legal_updates_db -q --tb=short` -> 16/16 verde.
- `python -m pytest tests\test_lex_operational_knowledge.py tests\test_pec_control_tower.py tests\test_legal_practice_research_matrix.py tests\test_react_legal_intelligence_search.py tests\test_packaging_consistency.py tests\test_openapi_contracts_phase6.py -q --tb=short` -> verde su tutto il perimetro mirato.

## Gate non derogabile per le prossime tranche

Prima di dichiarare completata una tranche Lex/RAG/Ricerca Legale bisogna aggiungere almeno:

1. domanda reale dell'avvocato;
2. output atteso scritto in linguaggio operativo;
3. test automatico che fallisce sulla vecchia risposta;
4. prova locale sul dato reale quando il dato esiste;
5. aggiornamento note operative e audit;
6. solo dopo, commit/push/deploy.
