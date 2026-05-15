# Legal Source Engine per Lex AI

## 1. Scopo

IUSENTRA necessita di un Legal Source Engine nativo che permetta a Lex AI di rispondere a domande giuridiche usando fonti giuridiche ufficiali, passaggi recuperati e citazioni verificabili.

Il Legal Source Engine non e' un chatbot generico. E' un layer di ricerca giuridica fondato sulle fonti: seleziona fonti, recupera passaggi, normalizza documenti, valida citazioni e consente a Lex AI di produrre solo bozze di risposta motivate da evidenze.

La prima implementazione e' deliberatamente sicura: documenti di design, contratti, registry, adapter scheletro, modello citazionale, answer policy, dogfood, scorecard e test. Non effettua crawling live, non attiva rete, non ingerisce dati di produzione e non modifica workflow esistenti.

## 2. Categorie di fonti

### Normativa primaria

- Normattiva
- Gazzetta Ufficiale
- banche dati regionali di normativa

### Giurisprudenza

- Corte Costituzionale
- Corte di Cassazione
- Giustizia Amministrativa
- Banca Dati di Merito

### Diritto europeo e sovranazionale

- EUR-Lex
- HUDOC / Corte Europea dei Diritti dell'Uomo

### Autorita amministrative e prassi

- Agenzia Entrate
- Garante Privacy
- ANAC
- AGCM
- AGCOM come possibile fonte futura

### Materiali parlamentari

- Camera dei Deputati
- Senato della Repubblica

## 3. Non-obiettivi

Il Legal Source Engine:

- non e' consulenza legale automatica;
- non sostituisce la revisione dell'avvocato;
- non invia automaticamente PEC;
- non effettua depositi telematici automatici;
- non fa scraping di produzione;
- non ingerisce dati cliente;
- non risponde senza citazioni;
- non usa banche dati private o a pagamento salvo licenza configurata esplicitamente;
- non bypassa i permessi IUSENTRA;
- non modifica workflow di produzione IUSENTRA.

## 4. Priorita delle fonti

Ordine di preferenza:

1. Testo ufficiale e banche dati ufficiali.
2. PDF certificato o pubblicazione ufficiale.
3. Open data o API ufficiali.
4. Pagine ufficiali di autorita.
5. Materiali preparatori parlamentari.
6. Commenti solo se chiaramente marcati come non autoritativi.

I commenti e le fonti non ufficiali non possono essere presentati come diritto vincolante.

## 5. Proposta di data model

Entita concettuali:

- `LegalSource`: fonte ufficiale o fonte governata registrata.
- `LegalDocument`: documento giuridico normalizzato.
- `LegalDocumentVersion`: versione storica o vigente di un documento.
- `LegalAct`: atto normativo.
- `LegalArticle`: articolo di un atto normativo.
- `LegalParagraph`: comma, periodo o sotto-sezione.
- `LegalCase`: pronuncia giurisprudenziale.
- `LegalAuthorityDocument`: documento di autorita amministrativa o prassi.
- `ParliamentaryDocument`: atto o materiale parlamentare.
- `LegalReference`: riferimento estratto da query o documento.
- `LegalCitation`: citazione strutturata usata in output.
- `SourceFetch`: tentativo di fetch o acquisizione, con provenienza e checksum.
- `IngestionRun`: run di ingestione incrementale.
- `SourcePolicy`: regole per fonte, rete, licenza, rate limit e citazioni.
- `RetrievedLegalPassage`: passaggio recuperato con citazione.
- `LegalAnswerDraft`: bozza di risposta da validare.
- `SourceResearchManuscript`: manoscritto di ricerca della fonte.
- `SourceScorecard`: scorecard di maturita e rischio.
- `DogfoodScenario`: scenario dry-run con fixture.
- `DogfoodResult`: esito dogfood strutturato.

## 6. Requisiti citazionali

Ogni risposta deve citare:

- nome fonte;
- categoria fonte;
- giurisdizione;
- tipo documento;
- autorita o corte, se applicabile;
- titolo;
- numero, se disponibile;
- data;
- articolo, comma o sezione, se disponibile;
- fonte di pubblicazione;
- numero pubblicazione, se disponibile;
- data di versione, se rilevante;
- URL o identificativo stabile;
- URN, ELI, CELEX, ECLI o HUDOC ID, se disponibili;
- timestamp di recupero.

Una citazione minima e' sufficiente solo se contiene almeno fonte, nome fonte, tipo documento, un localizzatore stabile o titolo/numero/URL, e una data/versione/timestamp.

## 7. Policy di retrieval

La ricerca segue questa priorita:

1. Lookup per identificativo esatto: URN, ELI, CELEX, ECLI, HUDOC ID, numero provvedimento.
2. Lookup per legge, articolo, data o versione.
3. Ricerca full-text su indice locale.
4. Ricerca semantica su indice locale.
5. Reranking dopo il retrieval.

Il reranking pesa:

- priorita della fonte;
- ufficialita;
- stabilita dell'identificativo;
- qualita citazionale;
- pertinenza del passaggio;
- freschezza o data di versione.

La risposta deve usare solo i passaggi recuperati. Se le fonti sono insufficienti, Lex AI deve rifiutare o chiedere di restringere la domanda. La policy distingue normativa, pubblicazione ufficiale, giurisprudenza, prassi/autorita, materiali parlamentari e commenti.

## 8. Policy di aggiornamento

Ogni futura ingestione deve prevedere:

- ingestione incrementale;
- checksum della fonte;
- timestamp ultimo avvistamento;
- tracciamento della versione fonte;
- reindicizzazione solo dei documenti cambiati;
- conservazione delle versioni giuridiche storiche;
- divieto di sovrascrivere versioni storiche giuridicamente rilevanti senza audit trail;
- logging dei fetch della fonte.

Ogni fetch deve essere riprendibile, auditabile, rate-limited, attribuito alla fonte e reversibile.

## 9. Safety policy

Regole inderogabili:

- nessuna risposta giuridica senza passaggi fonte;
- nessuna citazione inventata;
- nessun segreto di produzione;
- nessun dato cliente negli indici delle fonti giuridiche;
- rate limit per fonte;
- retry e backoff per future integrazioni live;
- logging della provenienza;
- audit log per risposte mostrate all'utente;
- warning quando una fonte puo essere incompleta, obsoleta o non ufficiale;
- revisione dell'avvocato richiesta per azioni dispositive o ad alto rischio.

Il motore non deve collegare Lex AI direttamente al database IUSENTRA e non deve bypassare autenticazione, isolamento tenant, RBAC, audit log o service layer esistenti.

## 10. Policy di integrazione Lex AI

Lex AI e' un'interfaccia sopra il Legal Source Engine. Non deve navigare liberamente e non deve rispondere a domande giuridiche senza citazioni.

Integrazione prevista:

1. Lex AI riceve la domanda.
2. Classifica se serve ricerca su fonti giuridiche.
3. Chiama solo tool ristretti sulle fonti giuridiche.
4. Riceve passaggi recuperati e citazioni strutturate.
5. Produce una bozza di risposta.
6. `AnswerPolicy` valida la bozza.
7. Se la validazione citazionale fallisce, Lex AI rifiuta o chiede chiarimenti.

La policy vieta tool larghi come navigazione libera, scraping generico o risposta legale senza evidenze.

## 11. Configurazione prevista

La funzionalita resta disabilitata di default:

```env
IUSENTRA_LEX_AI_LEGAL_SOURCES_ENABLED=false
IUSENTRA_LEGAL_SOURCES_ALLOW_NETWORK=false
IUSENTRA_LEGAL_SOURCES_REQUIRE_CITATIONS=true
IUSENTRA_LEGAL_SOURCES_DATA_DIR=data/legal_sources
IUSENTRA_LEGAL_SOURCES_INDEX_DIR=indexes/legal_sources
IUSENTRA_LEGAL_SOURCES_ARTIFACT_DIR=artifacts/legal_sources
IUSENTRA_LEGAL_SOURCES_RATE_LIMIT_PER_MINUTE=30
IUSENTRA_LEGAL_SOURCES_AUTO_POPULATE=false
IUSENTRA_LEGAL_SOURCES_POPULATE_ON_STARTUP=false
IUSENTRA_LEGAL_SOURCES_ENABLE_ALL_SOURCES=false
IUSENTRA_LEGAL_SOURCES_RUNTIME_CONFIG=data/legal_sources/runtime_config.json
IUSENTRA_SOURCE_NORMATTIVA_ENABLED=false
IUSENTRA_SOURCE_GAZZETTA_UFFICIALE_ENABLED=false
IUSENTRA_SOURCE_CORTE_COSTITUZIONALE_ENABLED=false
IUSENTRA_SOURCE_CASSAZIONE_ENABLED=false
IUSENTRA_SOURCE_GIUSTIZIA_AMMINISTRATIVA_ENABLED=false
IUSENTRA_SOURCE_BANCA_DATI_MERITO_ENABLED=false
IUSENTRA_SOURCE_EURLEX_ENABLED=false
IUSENTRA_SOURCE_HUDOC_ENABLED=false
IUSENTRA_SOURCE_AGENZIA_ENTRATE_ENABLED=false
IUSENTRA_SOURCE_GARANTE_PRIVACY_ENABLED=false
IUSENTRA_SOURCE_ANAC_ENABLED=false
IUSENTRA_SOURCE_AGCM_ENABLED=false
IUSENTRA_SOURCE_CAMERA_ENABLED=false
IUSENTRA_SOURCE_SENATO_ENABLED=false
IUSENTRA_SOURCE_LEGGI_REGIONALI_ENABLED=false
```

La prima modalita operativa locale usa `python -m lex.legal_sources.populate --activate --populate --force --json` per materializzare in cartelle ignorate il registro fonti, i manoscritti, le scorecard, il report dogfood e un indice JSONL di source-card citabili. Questa attivazione non scarica corpora giuridici, non usa rete, non legge dati cliente e non espone route pubbliche.
