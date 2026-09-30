# Campi SICID — 30/09/2026

Perimetro: esclusivamente i dodici tipi elencati in
`pct/deposito_sicid_campi.py`, richiesti dall'utente. Nessuna modifica a firma,
posizione della firma, PEC, invio locale, generatore XML o dati dei fascicoli.

Fonte: [XSD SICI 12/05/2026](https://pst.giustizia.it/PST/it/paginadettaglio.page?contentId=ACC4871),
pacchetto versionato in `docs/specs/ministero/xsd/2026-05-12-sici`.
`sicid_v7/Parte.xsd`: istanze aggiuntive facoltative (`minOccurs=0`),
assenti per PrecisazioneConclusioni e Preverbale. `base_v7/tipi-atti.xsd`:
`numeroCCI` nel solo riferimento concorsuale; attributo `sub` facoltativo.
Gli eventi 171-ter n.1/2/3 e 183-ter sono già generati dalla scelta del tipo.
Il tipo generale MemorieCartabia conserva il generatore esistente e non
inventa una specifica istanza: lo schema ammette l'assenza del gruppo.

Causa: il catalogo importato interpretava un controllo abilitato come un
campo libero obbligatorio, senza considerare la pertinenza XSD e gli eventi
già generati. Correzione condivisa tra catalogo/API React e validazione:
CCI non mostrato, Istanza manuale non richiesta, sub-procedimento facoltativo.
Gli altri tipi mantengono integralmente i requisiti precedenti.

Baseline accettata consultata e impronte confrontate: validazione invariata
dal backup del 09/09 prima della patch; catalogo già evoluto. `pct/busta.py`
e tutti i file di firma/PEC rimangono invariati. Backup sorgenti precedente
sul server: `/opt/iusentra/backups/campi-sicid-20260930/*.before.py`.

Persistenza: nessuna migrazione, nessun nuovo dato né scrittura sui fascicoli.
Il catalogo tecnico condiviso alimenta le API esistenti per SQLite/PostgreSQL.
Qualifica professionale, RG, anno, ufficio e altri requisiti restano governati.

Prova produzione: browser Chrome reale autenticato, fascicolo 58B00837,
selezione dei dodici tipi senza salvataggio, firma o invio. In tutti i casi
il pannello mostra Completi e Sub-procedimento sotto Dati facoltativi;
CCI e Istanza manuale assenti. Pagina dell'utente non modificata.

Guardrail: 31 test mirati superati, inclusi dodici XML realmente validati
contro gli XSD attivi senza i tre campi, conservazione degli eventi automatici,
permanenza del requisito Istanza sugli altri tipi e del blocco per RG mancante.
Nessuna simulazione di firma, deposito accettato o invio PEC. Ruff superato.

Prova locale su 8080: selezionati tutti i dodici tipi nel browser reale, fascicolo controllato FF8E5A4B; nessun CCI o Istanza manuale, sub facoltativo. Nessun salvataggio o invio. Release 2.434.4 in consolidamento. Il test nuovo è incluso automaticamente nella fase deposito del runner shardabile.

Il gate ui-support è stato eseguito ma non è applicabile a questa correzione del codice prodotto: segnala i file di dominio e i bump obbligatori come fuori perimetro tooling. Nessuna dipendenza cambiata; packaging (10 test), baseline Python e Ruff superati. Non sono stati alterati i controlli del gate.

## Invio di un solo documento
Verificato base_v2/tipi-allegati.xsd: dentro IndiceBusta, AttoPrincipale ha occorrenza 1 e gli altri allegati 0..n. L'indice può essere facoltativo in alcuni tipi XSD, ma quando presente non può contenere solo AllegatoSemplice. IUSENTRA produce già l'indice con il riferimento al documento operativo principale. Il browser reale online e locale mostrano la selezione di un solo PDF come 1 atto principale, 0 allegati. Nessuna modifica alla classificazione. I dodici test verificano inoltre il riferimento unico e il rifiuto XSD di un indice privo di AttoPrincipale. Un file probatorio resta un allegato: necessita dell'atto accompagnatorio, non va trasformato in atto processuale solo perché è l'unico file scelto.

