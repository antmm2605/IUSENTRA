# Log tecnico — prova Fascicolo d’ufficio

**Aperto:** 29/08/2026 21:55:50 Europe/Rome
**Ambiente:** IUSENTRA locale `http://localhost:8080` · container `iusentra-app` healthy
**Perimetro:** soltanto `Fascicolo d’ufficio → Visualizza fascicolo`; nessun download e nessuna importazione durante questa prova.

## Regola di parità con il Wizard

La UI del pannello passa il codice operativo del registro uffici, con lo stesso ordine del Wizard:

```text
depositOffice.code → depositOffice.ministerialCode → sourceSnapshot.ufficioCodice
```

Per il Tribunale di Vicenza il valore previsto in uscita dalla UI è `0640011`.
Il Local Signer, come nella baseline positiva, lo converte nel proprio identificativo ministeriale `0241160092` soltanto per il protocollo PST. La conversione non indica un diverso ufficio né un diverso rito.

## Configurazione prevista per la singola richiesta

| Voce | Valore atteso |
| --- | --- |
| Endpoint React | `POST /pst/ricerca-snapshot` |
| Parametri batch | `search_only=false`, `include_full_snapshot=true`, `single_interactive_batch=true` |
| Codice richiesto al Local Signer | `0640011` |
| Codice PST nel log | `0241160092` |
| Servizio | `JPW_SICID` |
| Tabella | `SICID_CONTENZIOSO_CIVILE` |
| Prompt certificato/PIN | una sola finestra nativa, gestita dall’avvocato |

## Cronologia della prova

| Ora | Evento | Evidenza | Esito |
| --- | --- | --- | --- |
| 21:55:50 | Registro creato | App locale healthy; bundle React verificato nel container | Pronto per l’avvio utente |
| — | Click `Visualizza fascicolo` | Da acquisire nel log Local Signer | In attesa |
| — | Risposta `POST /pst/ricerca-snapshot` | Codice, servizio, tabella e durata | In attesa |
| — | Catalogo renderizzato | Numero documenti visibili e selezionabili | In attesa |

## Criteri di esito

- Il log deve mostrare `ufficio richiesto=0640011`, `codice_pst=0241160092` e `servizio=JPW_SICID`.
- Il messaggio UI deve riferirsi alla tabella dedotta, non alla precedente `SICID_LAVORO`.
- Il catalogo deve essere valutato sul numero realmente restituito dalla singola richiesta, senza interpretare cinque soli atti come catalogo completo.
