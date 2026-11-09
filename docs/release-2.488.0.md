# IUSENTRA 2.488.0 — Guide pratiche per tutti i fascicoli, notifiche ai sensi della L. 53/1994, lettore di tutti i formati, ricevute dei depositi per ogni studio

## Guide pratiche
Verifica del 09/11/2026 sui 308 fascicoli dello studio: 62 non avevano una guida collegata. Ora ne restano senza solo
i fascicoli tecnici (1, il collaudo dell'editor PDF).
- **Regole della materia** (`pct/guida_pratica/regole_materia.py`). Si applicano solo quando il suggeritore ordinario
  non trova nulla: i collegamenti esistenti non cambiano.
  - «Retribuzione» nel lavoro: pubblico impiego se la controparte è una pubblica amministrazione (art. 63 D.Lgs.
    165/2001), lavoro privato altrimenti.
  - Ottemperanza (artt. 112-114 c.p.a.), silenzio sul riconoscimento di un titolo estero, precetto (non
    l'opposizione), ricorso al TAR contro un decreto ministeriale.
  - Carta del docente e cause di lavoro contro la PA senza oggetto: pubblico impiego.
- **Nuove schede**, norme lette sul testo vigente il 09/11/2026:
  - **Atto di precetto, anche contro la PA**: titolo in duplicato informatico o copia attestata conforme (artt. 475 e
    479 c.p.c.); termine non minore di 10 giorni, avvertimenti e giudice dell'esecuzione (art. 480); efficacia 90
    giorni (art. 481); 120 giorni dalla notifica del titolo prima del precetto contro lo Stato e gli enti pubblici non
    economici (art. 14 D.L. 669/1996).
  - **Silenzio del Ministero sul riconoscimento di un titolo conseguito all'estero**: provvedimento entro tre mesi
    dalla documentazione completa (art. 16, comma 6, D.Lgs. 206/2007); ricorso entro un anno (art. 31 c.p.a.), rito
    dell'art. 117 c.p.a.; contributo unificato di € 300.
- **Ottemperanza completata**: allegati corretti (sentenza in copia autentica, certificato di passaggio in giudicato
  dell'art. 124 disp. att. c.p.c., relata), TAR competente per le sentenze del giudice ordinario (art. 113, comma 2,
  c.p.a.), camera di consiglio con termini dimezzati (art. 87), contributo di € 300.
- **Lex**: la guida pratica entra anche nelle domande giuridiche senza fascicolo; i dati dello studio restano esclusi.

## Notifiche ai sensi della L. 53/1994
- **Formule dei decreti** (regole v1.0.4): oltre a «ordina/dispone … notific» ora si riconoscono «ONERA … della
  notificazione», «Manda al ricorrente di notificare», «sia notificato a cura di …», «notificarsi», «a cura di parte».
  Le notifiche a cura della cancelleria restano escluse (artt. 415, 435, 281-undecies c.p.c.).
- **Decreto letto anche fuori dalle fonti dell'evento**: l'ordine di notifica si cerca in tutti gli allegati
  professionali; «FISSA … l’udienza» con apostrofo tipografico è riconosciuto.
- **PEC senza fascicolo**: nessun presidio orfano; nello scadenziario compare la proposta «PEC con ordine di notifica:
  crea o collega il fascicolo RG …». Collegato il fascicolo, il presidio crea la bozza di notifica.

## Lettore di tutti i formati
- `.p7m` annidati fino a 5 livelli, marche temporali `.tsd` (RFC 5544) e `.m7m` aperti nel lettore
  (`pct/buste_firma.py`), nel fascicolo e negli allegati PEC. Nessuna verifica della firma (decisione dell'avvocato).
- `.rar`, `.7z`, `.heic` e formati sconosciuti: pagina «Anteprima non disponibile» con Scarica invece del download
  dentro il riquadro; per gli ZIP l'elenco dei file.
- Documento cifrato senza chiave dello studio: messaggio «Documento cifrato: chiave dei documenti dello studio non
  configurata» invece dell'errore generico.

## Ricevute dei depositi
- Il giro ogni 15 minuti (`polling_esiti_deposito`) controlla ogni studio con i suoi fascicoli, la sua casella e il
  suo archivio PEC (`web/services/polling_depositi_runtime.py`): prima leggeva i percorsi generali, vuoti negli studi.

## Sicurezza
- Ricerca della norma citata: le parole della domanda entrano nell'espressione regolare solo come testo (CodeQL).
- Eccezione CodeQL su `pct/cache.py` con il motivo corretto (copre le chiavi private, non password e token).

## Test
`tests/test_guide_pratiche_20261109.py`, `tests/test_lettore_tutti_i_formati.py`, `tests/test_polling_depositi_studi.py`,
regressioni in `tests/test_legal_notification_rulepack.py`, `tests/test_pec_legal_event_understanding.py`,
`tests/test_pec_audit_pipeline.py`, `tests/test_ricerca_legale_norma_citata.py`, `lex/tests/unit/test_guida_pratica_source.py`.
