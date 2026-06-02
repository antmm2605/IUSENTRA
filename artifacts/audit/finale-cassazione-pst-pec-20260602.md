# Audit finale - mappatura PST, Cassazione, SIVG, richieste copie e PEC penale

Data: 2 giugno 2026.

## Perimetro

- Local Signer/PST per Cassazione civile e penale.
- Lettura reale tabella Cassazione penale con PIN inserito dall'utente.
- Lettura reale volontaria giurisdizione/SIVG `63/2025/VG` sul Tribunale di Roma.
- Mappatura e prova live read-only richieste copie con interrogazioni, namespace, classi catalogo e parser contenuti.
- Classificazione PEC penale da `depositoattipenali.ca.reggiocalabria@giustiziacert.it`.
- Classificazione PEC penale da `notifichepenali.ca.reggiocalabria@penale.ptel.giustiziacert.it`.
- Presidio SIECIC quando il PST richiede `idRuoloJPW`.

## Prove reali

| Verifica | Esito | Evidenza |
| --- | --- | --- |
| Ricerca esatta `12756/2026` su `JPW_CASSPE` | Superata | `1` fascicolo; `NRGREALE=202601275600`; ruolo `RICORSO ORDINARIO`; sezione `PRIMA SEZIONE`; iscrizione `2026-04-14`; udienza `2026-07-09`. |
| Ricerca annuale Cassazione penale 2026 su `JPW_CASSPE` | Superata | `1` numero ruolo valido trovato: `12756/2026`. |
| Ricerca esatta `63/2025/VG` su Tribunale di Roma `JPW_SIVG` | Superata | `1` fascicolo; ufficio IUSENTRA `0760010`; codice PST `0580910098`; namespace `urn:CONS-SIVG-BE`; sezione `PRIMA SEZIONE SEPARAZIONI VOLONTARIA FAMIGLIA`; giudice valorizzato. |
| Tentativo `63/2025/VG` su Tribunale di Palmi | Non usato come prova positiva | La tabella `JPW_SIVG` è stata raggiunta, ma il portale ha restituito `available=0`; il caso corretto indicato dall'utente è Roma. |
| Ricerca annuale SICID/SIGP senza numero ruolo | Vincolo ministeriale rispettato | SOAP Fault `CONVENUTO`; nessun filtro fittizio introdotto. |
| Ricerca SIECIC senza ruolo ministeriale | Vincolo ministeriale rispettato | SOAP Fault `Parameter not resolved 'idRuoloJPW'`; il sistema ora accetta il ruolo autorizzato se presente e avvisa se manca. |
| Richieste copie read-only su `GLRM/JPW_SICID` | Superata | Interrogazione `RicercaRichieste` su namespace `urn:RichiestaCopie-consultazioni-distr`; risposta SOAP 200 con `available=0`, nessuna richiesta copie visibile al certificato in quel momento. |
| PEC deposito ricorso Cassazione penale Reggio Calabria | Superata | Famiglia `cassazione_penale`; evento `deposito_ricorso_cassazione_penale`; estratti `1365/2016 RG_APP` e `1364/2011 RG_NR`; lettura del messaggio originale allegato richiesta. |
| PEC notifiche penali Corte di Appello Reggio Calabria | Superata | Oggetto `generale/2016/001365/Corte di Appello ...`; famiglia `deposito_penale_pdp`; evento `comunicazione_penale_pdp`; estratto `1365/2016 RG_APP`; nessuna scadenza automatica senza contenuto fonte. |

## Correzioni applicate

- `tools/local_signer.py` usa `QP_Ricorsi` per `JPW_CASSPE` e `QC_Ricorsi` per `JPW_CASSCI`.
- La ricerca esatta Cassazione invia `NRGREALE` e non `RicercaInformazioniFascicoloPerTipo`.
- La ricerca annuale Cassazione usa `DATAISCR_DA` e `DATAISCR_AL`.
- Il parser qbuilder espone il numero ruolo visibile della Cassazione (`12756/2026`) senza sostituirlo con l'identificativo tecnico.
- La ricerca volontaria giurisdizione usa `JPW_SIVG` / `urn:CONS-SIVG-BE` e `tipo=VG`, come confermato dal test reale `63/2025/VG` su Roma.
- SIECIC supporta `idRuoloJPW` quando arriva dal flusso autorizzato e produce un messaggio operativo se il ruolo manca.
- Le richieste copie sono mappate come consultazione separata: interrogazioni `RicercaRichieste` e `ProfiloRichiesta`, namespace qbuilder `urn:RichiestaCopie-consultazioni-distr`, WSDL `urn:RichiestaCopie`, classi catalogo e parser di riepilogo/profilo/contenuti; il router non avvia invii o pagamenti automatici.
- Aggiunto test esatto sul deposito atti penali Cassazione da giustiziacert.
- Aggiunto test esatto sul formato penale `generale/<anno>/<numero>/Corte di Appello` da `penale.ptel.giustiziacert.it`.

## Test eseguiti

| Comando | Esito |
| --- | --- |
| `python -m py_compile tools\local_signer.py pct\pec_legal_workflow.py` | OK |
| `python -m pytest -q tests\test_local_signer.py -k "cassazione or siecic or qbuilder or richieste_copie" --tb=short` | OK, 34/34 |
| `python -m pytest -q tests\test_local_signer.py -k "richieste_copie" --tb=short` | OK, 4/4 |
| `python -m pytest -q tests\test_portali_telematici_matrix.py --tb=short` | OK, 15/15 |
| `python -m pytest -q tests\test_pec_legal_workflow.py::test_deposito_atti_penali_cassazione_da_giustiziacert_resta_penale tests\test_pec_legal_workflow.py::test_deposito_ricorso_cassazione_penale_estrae_rg_app_e_rg_nr --tb=short` | OK, 2/2 |
| `python -m pytest -q tests\test_pec_legal_workflow.py --tb=short` | OK, 12/12 |

## Rischi residui

- Per SIECIC non è stato inventato `idRuoloJPW`: serve un ruolo/incarico ministeriale restituito dal portale o da un flusso autorizzato.
- Per Cassazione civile resta da provare una ricerca live esatta con un numero ruolo civile realmente consultabile dal certificato; la mappatura `QC_Ricorsi` è già presidiata da catalogo/test.
- Per richieste copie la chiamata live read-only è certificata; in quel momento non risultavano richieste già presentate o comunque visibili al certificato (`available=0`), quindi non c'erano righe reali da elencare. Questo esito non indica un guasto del servizio o della mappatura.
- Per le PEC penali provate da testo, senza EML/allegato reale la prova valida router, estrazione e azione proposta; la lettura del contenuto allegato resta da verificare su messaggio reale transitato nello studio.
