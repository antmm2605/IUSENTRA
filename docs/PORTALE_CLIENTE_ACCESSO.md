# Portale Cliente — accesso sicuro (magic-link + OTP)

Stato: **primitiva di accesso (backend)**. Aggiunge un accesso a due fattori per
il Portale Cliente, costruito con la stessa filosofia del login guard dello
studio. L'invio dell'OTP sul canale (email/SMS/PEC) e l'aggancio alla sessione
del portale sono il wiring successivo; la primitiva qui è completa e testata.

## Flusso

```
studio → issue_magic_link(tenant, client, matter)  → (grant_id, token in chiaro UNA volta)
cliente clicca il magic-link → start_otp(grant_id, token)
        → magic-link verificato (monouso, TTL) → genera OTP → status "otp_sent"
cliente inserisce OTP → verify_otp(grant_id, code)
        → OTP verificato (TTL, max tentativi) → status "granted"
```

## Garanzie di sicurezza (`pct/client_portal_access.py`)

- **Token opaco**: magic-link generato con `secrets.token_urlsafe`, **salvato solo come hash** (mai in chiaro), con **TTL** (default 15 min) e **monouso** (consumato al primo uso valido).
- **OTP a tentativi limitati**: codice numerico salvato solo come hash, **TTL** (default 10 min), **max tentativi** (default 5); superata la soglia la sfida è **bloccata** e nemmeno l'OTP corretto la sblocca (anti forza bruta).
- **Confronti a tempo costante** (`hmac.compare_digest`).
- **Nessun segreto in chiaro** nello store (verificato da test): solo `magic_hash`/`otp_hash`.
- **Storage-agnostico**: `AccessStore` iniettabile (in produzione tenant-aware); `InMemoryAccessStore` per test/sviluppo.
- **Risoluzione lato server**: tenant/cliente/pratica vivono nel grant emesso dallo studio; il cliente non li sceglie mai.
- **Revoca**: `revoke(grant_id)` invalida il grant.

## API del manager

| Metodo | Effetto |
|---|---|
| `issue_magic_link(*, tenant_id, client_id, matter_id)` | emette grant, ritorna `(grant_id, token)` (token da inviare una sola volta) |
| `start_otp(grant_id, token)` | verifica magic-link (monouso/TTL), genera OTP, ritorna `AccessResult.otp_code` da consegnare via canale |
| `verify_otp(grant_id, code)` | verifica OTP (TTL + tentativi); su successo concede l'accesso |
| `revoke(grant_id)` | revoca il grant |

## Prossimi PR

- Store tenant-aware persistente + consegna OTP sul canale configurato (email/SMS/PEC).
- Aggancio alla sessione del Portale Cliente (sopra il subsystem `client_portal` esistente) e alle viste "stato pratica semplificato" e "documenti condivisi".
- Endpoint pubblici `/api/v1/ui/client-portal/public/access/*` (richiesta magic-link, verifica OTP) con rate limit.
