# Pack installazione IUSENTRA

Questa architettura separa in modo ferreo:

- `Product Pack`
- `Studio Local Pack`
- `Update Pack`

L'obiettivo e' evitare fallback opachi, mescolanza tra codice e dati di studio, e aggiornamenti che tocchino memoria privata del cliente senza governo esplicito.

## Regola di piattaforma

Il `SUPERADMIN` installa e governa il prodotto.

Gli studi non governano il `Product Pack` e non possono alterare i pack di installazione della piattaforma. Ogni studio usa solo il proprio `Studio Local Pack` tenant-aware.

Superficie ufficiale:

- `/admin/installazione-pack`

## Product Pack

Il `Product Pack` contiene cio' che puo' essere distribuito a ogni installazione:

- runtime applicativo
- Lex core
- manifest servizi locali
- prompt, policy e knowledge pubblica
- manifest prodotto firmato

Percorsi runtime:

- `data/system/product/manifests/product_pack.json`
- `data/system/product/public_knowledge/`
- `data/system/installation/identity.json`
- `data/system/installation/keys/`

Servizi locali governati:

- `iusentra-web`
- `iusentra-lex`
- `iusentra-embed`
- `iusentra-jobs`
- `iusentra-telematico`
- `iusentra-updater`

Sidecar opzionali, non inclusi come dati nel `Product Pack`:

- `local-deep-research`, attivabile con il profilo Docker `ldr` per ricerche
  pubbliche e non identificative;
- `searxng`, usato da Local Deep Research come motore web privato.

Questi sidecar usano il data root dello studio e non devono contenere memoria
privata redistribuibile come update di prodotto.

## Studio Local Pack

Ogni tenant ha il proprio `Studio Local Pack`, che nasce e resta nel perimetro locale dello studio.

Percorso manifest:

- `data/tenants/<slug>/config/studio_local_pack.json`

Struttura locale governata:

- `studio_data/db/`
- `studio_data/vectors/`
- `studio_data/memory/facts/`
- `studio_data/memory/timeline/`
- `studio_data/memory/profiles/`
- `studio_data/memory/economic/`
- `studio_data/documents/`
- `studio_data/attachments/`
- `studio_data/cache/`
- `studio_data/jobs/`
- `studio_data/backups/`
- `studio_data/audit/`
- `studio_data/keys/`

Compatibilita' governata:

- il pack espone anche i riferimenti ai percorsi runtime correnti del tenant
- il bootstrap e' idempotente
- nessuno studio puo' vedere o governare il pack di un altro tenant

## Update Pack

L'`Update Pack` contiene solo cio' che puo' essere aggiornato come prodotto:

- migrazioni SQL/SQLite
- migrazioni PostgreSQL
- nuovi moduli
- template aggiornati
- knowledge pubblica aggiornata

Percorsi runtime:

- `data/system/updates/current_update_pack.json`
- `data/system/updates/history/`

Ogni manifest update include:

- `from_version`
- `to_version`
- lista migrazioni SQL rilevate sotto `pct/sql/`
- firma HMAC del manifest

## Repository SQL dei manifest

I manifest dei pack non vivono solo su file: hanno anche repository SQL esplicito.

Schema SQLite / SQL locale:

- `pct/sql/20260422_installation_pack.sql`

Schema PostgreSQL:

- `pct/sql/20260422_installation_pack_postgres.sql`

Tabelle:

- `installation_product_pack_manifest`
- `installation_studio_local_pack_manifest`
- `installation_update_pack_manifest`

## Bootstrap applicativo

Il bootstrap applicativo inizializza in modo idempotente:

1. identita' installazione
2. chiavi per installazione
3. `Product Pack`
4. `Studio Local Pack` dei tenant presenti
5. `Update Pack`

La rigenerazione governata e manuale resta esposta dal `SUPERADMIN` nel pannello `Pack installazione`.

Nel pannello `/admin/installazione-pack` i servizi del `Product Pack` indicano la presenza del prodotto distribuibile. Le dipendenze runtime locali, come il provider AI/Ollama, sono mostrate in una sezione separata: un provider locale non pronto non deve trasformare in warning il servizio `Orchestratore Lex` quando i moduli Lex del prodotto sono installati e importabili.

## Chiavi e identita'

Per ogni installazione vengono inizializzate:

- `installation_id`
- `master.key`
- `product_signing.key`
- `database.key`
- `documents.key`
- `backups.key`
- `tokens.key`

Nei manifest non viene salvata la chiave in chiaro, ma solo:

- percorso
- fingerprint
- algoritmo

## Regole operative

- il `SUPERADMIN` e' l'unico attore che governa i pack
- gli studi non possono creare, promuovere o gestire pack di piattaforma
- il `Product Pack` non contiene dati reali dei clienti
- lo `Studio Local Pack` non deve essere redistribuito come update
- l'`Update Pack` tocca il prodotto e le migrazioni, non la memoria privata salvo migrazioni tecniche dichiarate
