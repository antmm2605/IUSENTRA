# Portale Cliente — Firma documenti (firma elettronica con evidence pack)

Stato: **prima fase, dietro feature flag**. Questo documento descrive il modello
di firma del Portale Cliente e i suoi limiti, in modo che non venga mai
presentato come qualcosa che non è.

## Cos'è (e cosa NON è) la firma del portale

- La firma applicata internamente dal Portale Cliente è una **firma elettronica
  semplice con pacchetto di evidenze** (CAD D.Lgs. 82/2005, artt. 20-21: valore
  probatorio liberamente valutabile dal giudice, rafforzato dalle evidenze).
- **Non è una firma elettronica qualificata** ai sensi del Regolamento eIDAS
  910/2014. La firma qualificata richiede un prestatore di servizi fiduciari
  qualificato esterno e **non è attiva** in questa fase (vedi provider stub).
- Resta sempre disponibile il **fallback**: scarico del documento, firma
  manuale fuori dal portale e ricarico del documento firmato.

## Feature flag

Tutto il flusso di firma cliente è governato dal flag esistente
**`routes.appV2.clientPortal.signatures`** («Firma semplice con evidenza nel
Portale Cliente»), **default-off**. Con il flag disattivato gli endpoint di
firma rispondono `feature_disabled` e nessuna firma viene applicata. Non sono
richieste migrazioni distruttive per attivarlo o disattivarlo.

## Provider di firma (adapter)

`web/services/client_signature_providers.py` espone un'interfaccia comune
`SignatureProvider` con tre implementazioni intercambiabili:

| Provider | `name` | Tipo | Operativo | Note |
|---|---|---|---|---|
| `InternalGraphicSignatureProvider` | `internal_graphic` | firma grafica/elettronica | sì | applica un timbro di firma visibile sul PDF (nuova versione) + evidence pack |
| `ManualUploadSignatureProvider` | `manual_upload` | upload manuale | sì | fallback: il cliente ricarica il documento firmato a mano |
| `QualifiedSignatureProviderStub` | `qualified_stub` | qualificata remota | **no** | segnaposto non operativo; non dichiara MAI una firma qualificata completata |

Metodi dell'interfaccia: `create_signature_request`, `get_signature_status`,
`download_signed_document`, `cancel_signature_request`. Una futura integrazione
con un provider qualificato esterno si aggiunge implementando l'interfaccia,
senza toccare il flusso del portale.

## Evidence pack (probatorio, lato studio)

`build_signature_evidence_pack(...)` produce il pacchetto di evidenze salvato
con la richiesta firma. Contiene:

- id firma, tipo firma, provider;
- tenant / cliente / pratica / documento risolti **lato server**;
- testo del consenso mostrato + versione, dichiarazione;
- hash SHA-256 del documento originale e (se prodotto) del documento firmato;
- coordinate firma;
- **hash dell'IP** (mai l'IP in chiaro), user agent, **riferimento hash del token** (mai il token in chiaro);
- timestamp server;
- `payloadSha256`: checksum dell'intero pacchetto per rilevare manomissioni.

Privacy by design:

- l'evidence pack **non viene mai restituito al cliente**: `_public_row` lo
  rimuove dai payload pubblici del portale (resta visibile solo lato studio per
  l'audit);
- nei log non finiscono né contenuti documentali né firme né IP/token in chiaro;
- il timbro visibile produce sempre una **nuova versione** del PDF: i byte
  originali non vengono mai mutati;
- su PDF cifrato o corrotto la firma **fallisce in modo sicuro**
  (`SignatureProviderError`), senza stack trace verso il client.

## Coerenza degli stati sulla superficie pubblica

Gli endpoint pubblici del portale (`/api/v1/ui/client-portal/public/*`) sono
autenticati tramite **token opaco** (salvato solo come hash, con scadenza e
revoca), non con le credenziali dello studio. Un accesso senza sessione cliente
valida riceve `401 unauthorized` (coerente fra `dashboard` e
`conversation-export`); un utente studio autenticato ma privo del permesso
riceve `403 forbidden`. In nessun caso vengono rivelati tenant, cliente o
pratica.

## Limiti residui di questa fase

- La UI React di acquisizione documenti d'identità (fotocamera/webcam) e la
  firma grafica su canvas non sono ancora incluse: il backend (provider, timbro
  PDF, evidence pack) è pronto per riceverle.
- Gli endpoint pubblici dedicati ad accettazione preventivo/conferimento con
  evidenze separate sono pianificati come passo successivo: oggi il flusso firma
  riusa l'endpoint `/public/signatures/<id>/complete`.
- La firma qualificata remota richiede l'integrazione di un provider esterno
  qualificato (lo stub non è operativo).
