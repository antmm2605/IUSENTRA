"""Verifica AdES dei documenti con liste UE firmate, su richiesta esplicita."""

from __future__ import annotations

import asyncio
import io
import threading
import time
from datetime import datetime, timezone

import aiohttp
from asn1crypto import cms
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.ades.report import AdESPassed
from pyhanko.sign.validation.ades import ades_lta_validation, ades_with_time_validation
from pyhanko.sign.validation.policy_decl import PdfSignatureValidationSpec, SignatureValidationSpec
from pyhanko.sign.validation.qualified.assess import QcPrivateKeyManagementType
from pyhanko.sign.validation.qualified.eutl_fetch import EU_LOTL_LOCATION, bootstrap_lotl_signers
from pyhanko.sign.validation.qualified.eutl_parse import LOTL_RULE, validate_and_parse_lotl
from pyhanko.sign.validation.qualified.tsp import (
    CAServiceInformation, QTSTServiceInformation, QcCertType, TSPRegistry, TSPTrustManager,
)
from pyhanko_certvalidator.context import CertValidationPolicySpec
from pyhanko_certvalidator.policy_decl import CertRevTrustPolicy, REQUIRE_REVINFO

from scripts.check_eidas_tl import _metadata, _registro_con_cessioni


_CACHE_LOCK = threading.Lock()
_REGISTRY: tuple[TSPRegistry, dict] | None = None
_REGISTRY_UNTIL = 0.0


async def _download_registry() -> tuple[TSPRegistry, dict]:
    """Convalida LOTL e annota precisamente ogni TL nazionale utilizzabile."""
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(
        timeout=timeout, headers={"User-Agent": "IUSENTRA-eIDAS/1.0 Mozilla/5.0"},
    ) as client:
        async with client.get(EU_LOTL_LOCATION) as response:
            response.raise_for_status()
            lotl = await response.text()
        signers = await bootstrap_lotl_signers(lotl, client)
        parsed = validate_and_parse_lotl(lotl, signers)
        if parsed.errors:
            raise ValueError(f"La LOTL contiene {len(parsed.errors)} errori di parsing.")
        references = [
            ref for ref in parsed.references
            if len(ref.territory) == 2
            and ref.territory != "UK"  # La LOTL conserva una copia storica pre-Brexit.
            and LOTL_RULE not in ref.scheme_rules
        ]
        if not references or not any(ref.territory == "IT" for ref in references):
            raise ValueError("La LOTL non contiene il riferimento italiano.")
        if len({ref.territory for ref in references}) != len(references):
            raise ValueError("La LOTL contiene riferimenti nazionali ambigui.")

        async def fetch(ref):
            if not ref.tlso_certs:
                raise ValueError(f"Riferimento TL incompleto per {ref.territory}.")
            try:
                if not ref.location_uri.startswith("https://"):
                    raise ValueError("URL TL non HTTPS")
                async with client.get(ref.location_uri) as response:
                    response.raise_for_status()
                    return await response.text()
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
                # Copia ufficiale della Commissione; la firma XML rimane
                # comunque obbligatoria e verificata con i TLSO della LOTL.
                ec_url = (
                    "https://eidas.ec.europa.eu/efda/api/v2/browse/eidas/tl/"
                    f"download/{ref.territory}"
                )
                async with client.get(ec_url) as response:
                    response.raise_for_status()
                    return await response.text()

        # Download concorrente, parsing e inserimento nel registro sequenziali.
        semaphore = asyncio.Semaphore(6)

        async def bounded_fetch(ref):
            async with semaphore:
                return await fetch(ref)

        xmls = await asyncio.gather(*(bounded_fetch(ref) for ref in references), return_exceptions=True)
        registry = TSPRegistry()
        verified = []
        unavailable = []
        next_updates = []
        for ref, xml in zip(references, xmls):
            try:
                if isinstance(xml, BaseException):
                    raise xml
                metadata = _metadata(xml)  # NextUpdate obbligatorio e non scaduto.
                parsed_registry, _, _ = _registro_con_cessioni(xml, ref.tlso_certs)
                for authority in parsed_registry.known_certificate_authorities:
                    for service in parsed_registry.applicable_service_definitions(authority, None):
                        if isinstance(service, CAServiceInformation):
                            registry.register_ca(service)
                for authority in parsed_registry.known_timestamp_authorities:
                    for service in parsed_registry.applicable_service_definitions(authority, None):
                        if isinstance(service, QTSTServiceInformation):
                            registry.register_tst(service)
                verified.append(ref.territory)
                next_updates.append(datetime.fromisoformat(
                    metadata["next_update"].replace("Z", "+00:00")
                ))
            except Exception:
                unavailable.append(ref.territory)
        if "IT" not in verified:
            raise ValueError("La Trusted List italiana non è verificabile.")
        return registry, {
            "paesi_verificati": sorted(verified),
            "paesi_non_disponibili": sorted(unavailable),
            "paesi_storici_esclusi": ["UK"],
            "valida_fino": min(next_updates).isoformat(),
        }


def _trusted_registry() -> tuple[TSPRegistry, dict]:
    global _REGISTRY, _REGISTRY_UNTIL
    with _CACHE_LOCK:
        if _REGISTRY is not None and time.monotonic() < _REGISTRY_UNTIL:
            return _REGISTRY
        registry = asyncio.run(asyncio.wait_for(_download_registry(), timeout=120))
        remaining = (
            datetime.fromisoformat(registry[1]["valida_fino"]) - datetime.now(timezone.utc)
        ).total_seconds()
        _REGISTRY, _REGISTRY_UNTIL = registry, time.monotonic() + min(3600, max(0, remaining))
        return registry


def _validation_spec(registry: TSPRegistry) -> SignatureValidationSpec:
    return SignatureValidationSpec(
        cert_validation_policy=CertValidationPolicySpec(
            trust_manager=TSPTrustManager(registry),
            revinfo_policy=CertRevTrustPolicy(REQUIRE_REVINFO),
        ),
    )


def _verdict(result, *, format_name: str, signer_number: int) -> dict:
    status = result.api_status
    passed = result.ades_subindic == AdESPassed.OK
    qualification = getattr(status, "qualification_result", None)
    qstatus = getattr(qualification, "status", None)
    qualified_cert = bool(passed and qstatus and qstatus.qualified)
    qscd = bool(
        qualified_cert and qstatus.qc_key_security in {
            QcPrivateKeyManagementType.QSCD,
            QcPrivateKeyManagementType.QSCD_DELEGATED,
            QcPrivateKeyManagementType.QSCD_BY_POLICY,
        }
    )
    qtype = qstatus.qc_type if qstatus else None
    qualified_signature = qualified_cert and qscd and qtype == QcCertType.QC_ESIGN
    qualified_seal = qualified_cert and qscd and qtype == QcCertType.QC_ESEAL
    if qualified_signature:
        verdict = "firma_qualificata"
    elif qualified_seal:
        verdict = "sigillo_qualificato"
    elif qualified_cert:
        verdict = "certificato_qualificato"
    elif result.ades_subindic.name in {"HASH_FAILURE", "SIG_CRYPTO_FAILURE"}:
        verdict = "firma_non_valida"
    else:
        verdict = "non_determinabile"
    return {
        "numero": signer_number,
        "formato": format_name,
        "esito": verdict,
        "ades_subindicazione": result.ades_subindic.name,
        "integrita": bool(status and status.intact and status.valid),
        "catena_fidata": bool(status and status.trusted),
        "revoca_verificata": passed,
        "certificato_qualificato": qualified_cert,
        "qscd": qscd,
        "tipo_certificato": qtype.name if qtype else None,
        "errore": result.failure_msg,
    }


async def _validate(data: bytes, filename: str, spec: SignatureValidationSpec) -> list[dict]:
    if data.startswith(b"%PDF-"):
        reader = PdfFileReader(io.BytesIO(data))
        signatures = reader.embedded_signatures
        if not signatures:
            return []
        pdf_spec = PdfSignatureValidationSpec(spec)
        results = []
        for number, sig in enumerate(signatures, start=1):
            result = await ades_lta_validation(sig, pdf_spec)
            results.append(_verdict(result, format_name="PAdES", signer_number=number))
        return results
    if filename.lower().endswith((".p7m", ".p7s", ".sig", ".pkcs7")):
        try:
            info = cms.ContentInfo.load(data, strict=True)
        except (ValueError, TypeError) as exc:
            raise ValueError("Il file non contiene una busta CAdES leggibile.") from exc
        if info["content_type"].native != "signed_data":
            raise ValueError("Il file non è una busta CAdES SignedData.")
        signed = info["content"]
        if signed["encap_content_info"]["content"].native is None:
            raise ValueError("Firma detached: serve anche il documento originale associato.")
        if not signed["signer_infos"]:
            raise ValueError("La busta CAdES non contiene firmatari verificabili.")
        results = []
        for number, signer in enumerate(signed["signer_infos"], start=1):
            one_signer = signed.copy()
            one_signer["signer_infos"] = cms.SignerInfos([signer])
            result = await ades_with_time_validation(one_signer, validation_spec=spec)
            results.append(_verdict(result, format_name="CAdES", signer_number=number))
        return results
    raise ValueError("Formato non supportato dalla verifica eIDAS documentale.")


def verifica_documento_eidas(data: bytes, filename: str) -> dict:
    """Esito puntuale, senza alterare lo stato operativo del deposito/firma."""
    if not data or len(data) > 50 * 1024 * 1024:
        raise ValueError("Documento vuoto o troppo grande per la verifica online (50 MB).")
    registry, coverage = _trusted_registry()
    signatures = asyncio.run(asyncio.wait_for(
        _validate(data, filename, _validation_spec(registry)), timeout=90,
    ))
    return {
        "fonte_fiducia": "LOTL UE e Trusted List nazionali firmate",
        "copertura": coverage,
        "verifica_al": datetime.now(timezone.utc).isoformat(),
        "firme": signatures,
    }
