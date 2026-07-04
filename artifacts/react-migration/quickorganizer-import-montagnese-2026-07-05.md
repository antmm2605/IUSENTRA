# Riparazione import pratiche Montagnese

Data operativa: 05/07/2026, fuso `Europe/Rome`.

Tenant produzione: `studio-legale-giuseppe-montagnese`.

Superficie utente da verificare: `https://app.iusentra.it/fascicoli` e dettaglio fascicolo React.

## Obiettivo

Riparare definitivamente la riesecuzione dell’import Studio Telematico dopo la segnalazione visiva dell’utente:

- i nomi visibili dei documenti devono tornare uguali alle descrizioni mostrate da Studio Telematico;
- il nome file fisico deve restare conservato come dato originale e non diventare titolo utente;
- il contesto del fascicolo deve essere creato automaticamente;
- udienze e appuntamenti della tabella `AGENDA` devono alimentare il calendario IUSENTRA;
- il contesto economico deve essere preparato in automatico durante import/riparazione.

## Regola dati

Fonte di verità strutturata: SQLite tenant `studio.db` in produzione; JSON solo mirror o supporto storico.

Regola documento corretta:

- `Documento.nome`: descrizione Studio Telematico normalizzata con estensione (`NOME_ATTO`, `Subject`);
- `Documento.nome_portale`: stessa descrizione Studio Telematico;
- `Documento.nome_originale`: file fisico del pacchetto (`2026...PDF`, `MSG...eml`);
- `Documento.nome_archivio` e percorso su disco: file fisico reale;
- `Documento.tipo_atto_portale`: descrizione Studio Telematico.

## Codice modificato

- `web/services/quickorganizer_import.py`: riparazione nomi, `source_snapshot`, udienze, Agenda e contesto economico automatici.
- `web/blueprints/api_v1_react.py`: l’esecuzione import passa il repository Agenda reale.
- `web/services/react_fascicoli_bridge.py`: il dettaglio React collega l’Agenda tramite `source_external_id`/profilo fascicolo oltre al numero RG.
- `scripts/audit_quickorganizer_import.py`: audit tenant-aware con Agenda, appuntamenti e contesti economici.

## Guardrail automatici

Eseguiti localmente:

- `python -m pytest tests\test_quickorganizer_import.py -q`: `17/17` passati.
- `python -m pytest tests\test_quickorganizer_import.py tests\test_fascicoli_pagination.py::test_fascicolo_dettaglio_collega_agenda_importata_da_source_external_id tests\test_fascicoli_pagination.py::test_fascicolo_dettaglio_principale_include_quadro_operativo_e_tab_lazy tests\test_react_shell.py::test_react_fascicoli_bridge_usa_repository_reali -q`: `20/20` passati.
- `python -m py_compile web\services\quickorganizer_import.py scripts\audit_quickorganizer_import.py web\services\react_fascicoli_bridge.py web\blueprints\api_v1_react.py`: passato.
- `python scripts\react-migration\generate_api_contracts.py --check`: contratti allineati.
- `python scripts\validate_openapi.py docs\openapi.yaml`: OpenAPI valido.
- `python scripts\verify_openapi_provider.py`: provider verification OK.
- `python -m pytest tests\test_utf8_integrity.py -q`: `4/4` passati.

## Stato produzione

Da completare dopo deploy 2.253.178:

- riesecuzione riparazione sul pacchetto server `/opt/iusentra/data/tenants/studio-legale-giuseppe-montagnese/fascicoli/importazioni/quickorganizer/manual/reimport-missing-files.zip`;
- audit produzione con nomi Studio Telematico, contesti economici e Agenda;
- verifica visiva server su fascicolo Dalla Valle per nomi documento;
- verifica visiva server su un fascicolo con udienza importata;
- verifica visiva server del pannello economico/contesto economico.
