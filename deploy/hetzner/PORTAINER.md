# Portainer e deploy Git di IUSENTRA

## Decisione operativa — 08/09/2026

Su CPX42 si conserva lo stack `iusentra`: app React/Flask, Caddy, Redis,
worker OCR, scheduler e profilo audit con PostgreSQL e MinIO. Le dipendenze
di avvio restano governate dal Compose canonico. I dati operativi degli studi
restano SQLite; PostgreSQL audit non viene presentato come database degli studi.
Ollama e gli altri servizi AI restano profili opzionali, senza nuovi worker fittizi.
Il pannello è separato nello stack `iusentra-management`.

## Accesso e persistenza

Portainer CE 2.45.0 è bloccato per digest in `docker-compose.portainer.yml`.
La porta 19000 ascolta solo sul loopback del server. Dal PC:

```powershell
ssh -N -L 127.0.0.1:19000:127.0.0.1:19000 iusentra-hetzner
```

Aprire <http://127.0.0.1:19000>. Credenziale iniziale amministratore nel file
`/opt/iusentra/portainer/admin-password` (600), database Portainer in
`/opt/iusentra/portainer/data`. Non pubblicare questi file. Il socket Docker
conferisce privilegi amministrativi: l'accesso resta riservato al proprietario.

## Flusso di rilascio

GitHub esegue i gate e il backup già previsti. `deploy.sh` riceve `EXPECTED_SHA`,
sincronizza quel commit, costruisce `iusentra-app:<SHA>` e, se l'ambiente server
contiene `IUSENTRA_DEPLOY_DRIVER=portainer`, richiama `portainer_deploy.py`.
Portainer legge il Compose direttamente dal repository pubblico, fissato al tag immutabile `iusentra-release-<SHA>` creato dopo i gate, sullo
stesso SHA, e avvia lo stack con la stessa immagine per app e worker.
Non sono attivi polling o webhook pubblici che possano anticipare la CI.
Un errore Portainer interrompe il deploy senza avviare un secondo deploy Compose.

I mount dati restano quelli del profilo Hetzner. Caddy e il monitoraggio usano
percorsi assoluti del checkout server, sincronizzato allo stesso commit, per
evitare bind verso la directory effimera del clone Portainer. L'ambiente riservato
è montato in sola lettura; solo le variabili referenziate dal Compose vengono
trasferite all'API locale. Nessun token GitHub è necessario per leggere il repo.

## Attivazione e controlli

Attivare il driver solo dopo disponibilità del codice su GitHub, backup verificato,
validazione dei mount e disponibilità dell'immagine. La creazione usa sempre
nome `iusentra` e ambiente Docker locale esistente; non cancella volumi.
Controllare Portainer, app e worker healthy, Caddy, HTTPS `/api/pronto`, SHA
effettivo e unicità di `iusentra-app`. Pulire la cache Docker a fine deploy.

Per un rollback usare un commit precedente verificato e la sua immagine,
preservando dati e configurazione; verificare prima compatibilità delle migrazioni.
Non premere rimozione stack/volumi come procedura di aggiornamento.

## Stato della consegna

Installazione e accesso al pannello verificati nel browser reale. Collegamento Git,
presa in carico dello stack e prova di aggiornamento ancora da verificare.
Test mirati: isolamento variabili, rifiuto valori multilinea, errori senza segreti.
Il primo test locale ha evidenziato il separatore Windows del percorso nella
fixture; corretto usando un percorso POSIX esplicito. Nessun impatto runtime.

## Fonti

- <https://docs.portainer.io/start/install-ce/server/docker/linux>
- <https://docs.portainer.io/advanced/cli>
- <https://docs.portainer.io/advanced/relative-paths>
- <https://github.com/portainer/portainer/blob/2.45.0/api/http/handler/stacks/create_compose_stack.go>
- <https://github.com/portainer/portainer/blob/2.45.0/api/http/handler/stacks/stack_update_git_redeploy.go>

Verifiche tecniche: 13 test Portainer/packaging passati, 6 contratti CI passati,
Ruff passato; Compose candidato validato sul server con ambiente reale senza
stampare segreti. Packaging inizialmente disallineato su frontend/OpenAPI,
poi riallineato alla versione 2.280.2. Build locale senza cache eseguita;
Panoramica autenticata con dati dello studio verificata sulla porta 8080.

Verifica sorgenti Portainer: il resolver richiede un riferimento Git nominato,
non uno SHA isolato. Il deploy usa quindi un tag leggero univoco per commit,
creato dalla CI dopo i gate e controllato prima della chiamata Portainer.

Il deployer Compose di Portainer 2.45.0 richiama sempre la build. Per preservare
l'immagine verificata, `docker-compose.portainer-release.yml` azzera `build`
con `!reset null` e imposta `pull_policy: never` sui tre servizi applicativi.
Il file viene letto da Git come `AdditionalFiles` dopo il Compose canonico.
La CI esegue lo script del commit verificato da un percorso temporaneo esterno
al checkout che lo script stesso sincronizza. Il limite del job comprende
l'attesa dei gate, il backup, la build e i controlli di salute.

Fonti aggiuntive: <https://docs.docker.com/reference/compose-file/merge/> e
<https://github.com/portainer/portainer/blob/2.45.0/pkg/libstack/compose/composeplugin.go>.
