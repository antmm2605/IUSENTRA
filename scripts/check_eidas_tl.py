"""Controllo periodico della LOTL UE e della Trusted List italiana.

Non considera attendibile una lista ottenuta soltanto via HTTPS: verifica
entrambe le firme XML e prende i certificati TL dalla LOTL firmata.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
from datetime import datetime, timezone

import aiohttp
from lxml import etree
from pyhanko.sign.validation.qualified.eutl_fetch import (
    EU_LOTL_LOCATION,
    bootstrap_lotl_signers,
)
from pyhanko.sign.validation.qualified.eutl_parse import (
    validate_and_parse_lotl,
    trust_list_to_registry,
)

# Impronte pubblicate da AgID il 22/01/2026: solo controllo di rotazione.
# La verifica crittografica usa esclusivamente i certificati della LOTL firmata.
AGID_TL_2026_SHA256 = {
    "TL5": "504df2989c61767678428d20092e81b6a39f92c7ea57f14c4c4b8dde6c2eea4d",
    "TL6": "ddf02ac377a55fbda3709158a15fe1a10330743413ff1de72a91edb6ee285661",
}


def _certificati_2026_nella_lotl(certs: list) -> dict[str, bool]:
    fingerprints = {hashlib.sha256(cert.dump()).hexdigest() for cert in certs}
    return {name: fingerprint in fingerprints for name, fingerprint in AGID_TL_2026_SHA256.items()}


def _metadata(xml: str) -> dict[str, str | int]:
    root = etree.fromstring(
        xml.encode("utf-8"),
        parser=etree.XMLParser(resolve_entities=False, no_network=True),
    )
    ns = {"tsl": "http://uri.etsi.org/02231/v2#"}
    sequence = root.xpath("string(./tsl:SchemeInformation/tsl:TSLSequenceNumber)", namespaces=ns)
    next_update = root.xpath("string(./tsl:SchemeInformation/tsl:NextUpdate/tsl:dateTime)", namespaces=ns)
    if not sequence or not next_update:
        raise ValueError("Metadati obbligatori della Trusted List mancanti.")
    expiry = datetime.fromisoformat(next_update.replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("La Trusted List italiana è scaduta.")
    return {"sequence": int(sequence), "next_update": next_update}


async def check() -> dict:
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as client:
        async with client.get(EU_LOTL_LOCATION) as response:
            response.raise_for_status()
            lotl = await response.text()
        lotl_signers = await bootstrap_lotl_signers(lotl, client)
        references = validate_and_parse_lotl(lotl, lotl_signers).references
        italian = [ref for ref in references if ref.territory == "IT"]
        if len(italian) != 1 or not italian[0].tlso_certs:
            raise ValueError("Riferimento italiano e certificati TL non univoci nella LOTL europea.")
        ref = italian[0]
        certificati_2026 = _certificati_2026_nella_lotl(ref.tlso_certs)
        if not all(certificati_2026.values()):
            raise ValueError("TL5 o TL6 assente dalla LOTL europea firmata: verificare la rotazione AgID.")
        if not ref.location_uri.startswith("https://"):
            raise ValueError("La LOTL non indica un indirizzo HTTPS per la TL italiana.")
        async with client.get(ref.location_uri) as response:
            response.raise_for_status()
            xml = await response.text()
    # Verifica la firma XML prima di usare qualsiasi dato della lista.
    registry, errors = trust_list_to_registry(xml, ref.tlso_certs)
    metadata = _metadata(xml)
    return {
        "source_of_truth": "eu_lotl_signed",
        "territory": "IT",
        "tl_url": ref.location_uri,
        "lotl_signature_valid": True,
        "tl_signature_valid": True,
        "agid_tl5_tl6_in_signed_lotl": certificati_2026,
        "tl_sequence": metadata["sequence"],
        "tl_next_update": metadata["next_update"],
        "registry_type": type(registry).__name__,
        "service_parse_errors": len(errors),
        "qualification_complete": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict-services", action="store_true")
    args = parser.parse_args()
    logging.getLogger("pyhanko.sign.validation.qualified.eutl_parse").setLevel(logging.ERROR)
    try:
        result = asyncio.run(check())
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return int(args.strict_services and not result["qualification_complete"])


if __name__ == "__main__":
    raise SystemExit(main())
