# Tranche 26a - Audit Studio / Amministrazione

Generato: 2026-05-08

## Stato attuale /studio

- Route censita nel manifest come `react_bridge` prima della tranche.
- Shell React esistente: `frontend/src/App.tsx` serve `StudioPage` su `/studio`.
- Data client esistente: `frontend/src/studioData.ts` leggeva `GET /api/v1/ui/studio`.
- Bridge precedente: `web/services/react_studio_bridge.py` dichiarava `writes=legacy_routes` e trattava lo hub come collegamento verso moduli/legacy.
- CTA legacy primaria rilevata prima della tranche: `/impostazioni?_legacy=1`.

## Stato attuale /amministrazione

- Route censita nel manifest come `react_bridge` prima della tranche.
- Shell React esistente: `frontend/src/App.tsx` serve `AmministrazionePage` su `/amministrazione`.
- Data client esistente: `frontend/src/amministrazioneData.ts` leggeva `GET /api/v1/ui/amministrazione`.
- Bridge precedente: `web/services/react_amministrazione_bridge.py` dichiarava `writes=legacy_routes`.
- Nessun `LegacyPostForm` nel componente, ma payload e copy erano ancora da hub mascherato.

## Handler legacy

- `/studio`: contratto legacy catturato in `artifacts/react-migration/legacy-contracts/studio.json`.
- `/amministrazione`: contratto legacy catturato in `artifacts/react-migration/legacy-contracts/amministrazione.json`.
- `/impostazioni`, `/impostazioni-studio`, `/impostazioni/calendario`, `/impostazioni/pagamenti`, `/sincronizzazione-calendari`: contratti legacy catturati e mantenuti protetti.

## Template legacy

- I contratti catturati restituiscono redirect a login in assenza di sessione e non espongono template utilizzabili senza autenticazione.
- Le impostazioni sensibili restano template Flask legacy/protetti.

## Permessi richiesti

- API React richiedono `_richiedi_auth`.
- `/amministrazione` richiede `utenti.leggi`.
- `/studio` richiede sessione utente e restituisce permessi operativi aggregati letti da `g.utente_corrente`.

## Link legacy presenti

- Impostazioni generali.
- Impostazioni studio.
- Impostazioni calendario.
- Impostazioni pagamenti.
- Sincronizzazione calendari.
- Servizi telematici.
- Builder Sito Studio.

## CTA legacy primarie presenti

- Prima della tranche: `/studio` aveva una CTA primaria verso `/impostazioni?_legacy=1`.
- `/amministrazione` non usava `LegacyPostForm`, ma lo stato bridge segnalava ancora operativita legacy.

## Moduli già operativi React

- `/utenti`, `/utenti/nuovo`, `/profili`, `/audit`, `/registro-attivita`, `/backup`.
- `/fatturazione`, `/fatturazione/nuova`, `/incassi-pagamenti`.
- `/preventivi`, `/preventivi/nuovo`, `/preventivi/conferimento/nuovo`.
- `/compensi-forensi`, `/tariffario`.

## Moduli ancora legacy

- `/impostazioni`, `/impostazioni-studio`, `/impostazioni/calendario`, `/impostazioni/pagamenti`.
- `/sincronizzazione-calendari`.
- Telematico, portali, firma e deposito.
- `/studio/*` e `/amministrazione/*` restano protetti dal gate.

## Dati sensibili da non esporre

- Password, hash credenziali, token, chiavi API, provider secret, webhook secret.
- OAuth calendario, PEC/SMTP, firma digitale, path assoluti, stack trace.
- Configurazioni telematiche o credenziali portali.

## API già esistenti

- `GET /api/v1/ui/studio`.
- `GET /api/v1/ui/amministrazione`.

## Gap per react_operational_full

- Contratti bridge da portare a `writes=none`, `operational=true`, `secrets_exposed=false`.
- Payload da normalizzare con dati reali aggregati, salute sistema, permessi, moduli operativi e legacy protetti.
- Rimozione CTA primaria legacy su `/studio`.
- Manifest da promuovere a `react_operational_full`.
- Check anti-mascheramento dedicati e report operativo.
