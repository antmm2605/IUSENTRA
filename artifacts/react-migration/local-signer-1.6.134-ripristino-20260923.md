# Local Signer 1.6.134 — ripristino motore accettato e cofirma CAdES parallela

Data: 23/09/2026 (Europe/Rome).

## Perimetro

L’intervento riguarda esclusivamente il Local Signer, il modulo PKCS#11 distribuito, i pacchetti installabili e i test collegati. Non è stato eseguito alcun invio PEC, deposito reale o utilizzo del PIN dell’avvocato.

## Baseline verificata

Fonte immutabile consultata in sola lettura: `/opt/iusentra/backups/deposito-accettato-20260909_195010`.

- Sorgente accettato `tools/local_signer.py` 1.6.131: SHA-256 `088e75b19d1421dca502c2db68f40c2e4be620eca4fd6decd10e17651a5bdf7e`.
- Installer accettato `SetupLocalSigner-1.6.131.exe`: SHA-256 `b80e46de0e29a030e6ba779a4516097ef3bbcd449fd63af3a9e6b56163df4eb7`.
- Il blocco `_windows_store_sign_raw` della 1.6.134 coincide con quello della 1.6.131 dopo la sola normalizzazione CRLF/LF: SHA-256 comune `70890cde51112a1d37c13a7cce7ec27ca147736d8d1c827f060f436ab7827daa`.
- Il motore ripristinato usa `RSACertificateExtensions.GetRSAPrivateKey(...).SignData(...)` tramite PowerShell per ogni firma, come nel collaudo accettato. Il worker persistente introdotto nella 1.6.133 non è più usato dal percorso crittografico Windows.

## Correzioni mantenute e aggiunte

Sono rimasti i guardrail non crittografici successivi alla baseline: conservazione del formato PAdES/CAdES richiesto nei fallback, distribuzione/hot-update dei moduli firma e filtro della finestra tecnica Bit4Id.

La cofirma CAdES ora:

- firma il contenuto incapsulato originario;
- conserva tutti i `SignerInfo` e certificati precedenti;
- aggiunge il nuovo `SignerInfo` nello stesso `SignedData`;
- non crea una seconda busta `.p7m` annidata;
- rifiuta buste detached, prive di firme/certificati o già annidate;
- non modifica il contenuto già firmato per applicare una rappresentazione grafica;
- conserva la busta originale nel percorso batch, compreso il comando storico `replace_existing_signature`.

`pct/firma_pkcs11.py`, `local_signer_mod/firma_pkcs11.py` e la copia distribuita sono byte-per-byte allineati: SHA-256 `596b8cbeb71602c780bfe0de362375cec21a27f8423e63cc4a0ca32cf574d699`.

## Pacchetto 1.6.134

- Sorgente e copia distribuita: SHA-256 `d700224d097a0b1366aa54a80deb3421a948f438171502cb424a883f66f54f6e`.
- `SetupLocalSigner-1.6.134.exe`: SHA-256 `6fad9acbf358c23b40479c3beb04642cc11acf9196c6224718d9af61efa64c40`.
- Alias `SetupLocalSigner.exe`: stessa impronta dell’installer versionato.
- `InstallaLocalSigner-1.6.134.ps1`: SHA-256 `5d8e33e5572fc1806e68796ee10cd3418058b9e1dbb58979ec1e4c1b5dc3e172`.
- `InstallaLocalSigner-1.6.134.command`: SHA-256 `4bb33ff8a95d50c99530e69946ef8f92d1d2ea2a885ec7943ea9701de0db5d4c`.
- `InstallaLocalSigner-1.6.134.run`: SHA-256 `d261d990aaf36760c52ac93966d3c828601a43a81fa4b0897d148033f5e849ca`.

## Verifiche automatiche

- `python -m pytest tests/test_local_signer_deposito_regression.py tests/test_local_signer.py -q`: 277 test raccolti, esito positivo.
- `python -m pytest tests/test_polisweb.py -q`: 109 test raccolti, esito positivo.
- `python -m pytest tests/test_build_dist.py tests/test_local_signer_installer_atomic.py -q`: 17 test raccolti, esito positivo.
- I nuovi test costruiscono due firme CAdES con certificati distinti, verificano due firmatari paralleli sullo stesso contenuto, la conservazione del primo firmatario, la verifica crittografica e lo stesso comportamento nel percorso Windows Store e nel batch.
- La sorgente distribuita, il modulo distribuito, l’alias Windows e l’installer versionato sono allineati dai test di packaging.

## Limite della prova

Stato: **non verificato su macchina reale** con smart card/token e PIN dell’avvocato. I test automatici non sostituiscono il collaudo materiale. Prima di dichiarare il rilascio accettato occorre installare `SetupLocalSigner-1.6.134.exe` sul PC dello studio e verificare almeno: firma multipla PAdES, aggiunta di una seconda firma PAdES, aggiunta di una firma CAdES con due firmatari paralleli, salvataggio nel fascicolo e riabilitazione del passo successivo. Nessuna PEC deve essere inviata durante questa prova.