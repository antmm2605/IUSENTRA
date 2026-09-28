"""Buste CAdES-BES e PAdES con la chiave nell'HSM del prestatore.

Stesso profilo della firma con smart card (``pct.firma_pkcs11``): attributi firmati
CAdES-BES (content-type, signing-time, message-digest, signingCertificateV2),
firme multiple CAdES parallele nella stessa busta (Specifiche tecniche DGSIA
07/08/2024 art. 15, c. 2), PAdES con timbro visibile e motivo «Per autentica e
sottoscrizione». Al prestatore si manda solo l'impronta SHA-256 da firmare; la
firma ricevuta si verifica con il certificato prima di chiudere la busta.
"""

from __future__ import annotations

import hashlib
import io
import os
from datetime import datetime, timezone

from pct.firma_remota.base import (
    CertificatoRemoto,
    CredenzialiFirmaRemota,
    FirmaRemotaError,
    FirmatarioRemoto,
    verifica_firma_rsa,
)

MOTIVO = "Per autentica e sottoscrizione"


def controlla_validita(certificato: CertificatoRemoto) -> None:
    """Certificato scaduto o non ancora valido: nessuna firma (D.M. 44/2011 art. 12)."""
    cert = certificato.x509()
    adesso = datetime.now(timezone.utc)
    if cert.not_valid_after_utc < adesso:
        raise FirmaRemotaError(
            f"Il certificato di firma remota è scaduto il {cert.not_valid_after_utc:%d/%m/%Y}: rinnovalo presso il prestatore."
        )
    if cert.not_valid_before_utc > adesso:
        raise FirmaRemotaError("Il certificato di firma remota non è ancora valido.")


def _firma_dati(firmatario: FirmatarioRemoto, credenziali: CredenzialiFirmaRemota,
                certificato: CertificatoRemoto, dati: bytes) -> bytes:
    impronta = hashlib.sha256(dati).digest()
    firma = firmatario.firma_impronta(credenziali, impronta, certificato)
    verifica_firma_rsa(certificato.der, impronta, firma)
    return firma


def _luogo(luogo: str) -> str:
    from visible_signature import resolve_visible_signature_place

    return resolve_visible_signature_place(
        city=luogo or os.getenv("PCT_STUDIO_CITY", ""),
        province=os.getenv("PCT_STUDIO_PROVINCIA", ""),
        address=os.getenv("PCT_STUDIO_INDIRIZZO", ""),
    )


def _con_timbro(documento: bytes, certificato: CertificatoRemoto, *, modo: str, luogo: str, modo_data: str) -> bytes:
    from visible_signature import prepare_document_for_signature

    cert = certificato.x509()
    return prepare_document_for_signature(
        documento,
        intestatario=certificato.intestatario,
        data_firma=datetime.now().astimezone(),
        luogo=_luogo(luogo),
        issuer=certificato.emittente,
        serial=format(cert.serial_number, "X"),
        mode=modo,
        datetime_mode=modo_data,
    )


def firma_cades(firmatario: FirmatarioRemoto, credenziali: CredenzialiFirmaRemota, documento: bytes, *,
                visible_signature_mode: str = "laterale", visible_signature_place: str = "",
                visible_signature_datetime_mode: str = "data_ora") -> tuple[bytes, CertificatoRemoto]:
    """Busta .p7m con il documento incluso; se il documento è già una CAdES, firma parallela."""
    from pct.firma_pkcs11 import _build_cades_bes, _cades_embedded_content_for_parallel_signature, build_cades_signed_attrs_der

    certificato = firmatario.certificato(credenziali)
    controlla_validita(certificato)
    busta_esistente = None
    contenuto = _cades_embedded_content_for_parallel_signature(documento)
    if contenuto is not None:
        busta_esistente, documento = documento, contenuto
    else:
        documento = _con_timbro(documento, certificato, modo=visible_signature_mode, luogo=visible_signature_place,
                                modo_data=visible_signature_datetime_mode)
    attributi = build_cades_signed_attrs_der(hashlib.sha256(documento).digest(), cert_der=certificato.der)
    firma = _firma_dati(firmatario, credenziali, certificato, attributi)
    busta = _build_cades_bes(documento, firma, certificato.der, attributi, detached=False,
                             certificate_chain_der=certificato.catena, existing_cades=busta_esistente)
    return busta, certificato


def firma_pades(firmatario: FirmatarioRemoto, credenziali: CredenzialiFirmaRemota, pdf: bytes, *,
                visible_signature_mode: str = "laterale", visible_signature_place: str = "",
                visible_signature_datetime_mode: str = "data_ora") -> tuple[bytes, CertificatoRemoto]:
    """PDF firmato PAdES (salvataggio incrementale), con timbro visibile alla prima firma."""
    from asn1crypto import cms, x509 as asn1_x509
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from pyhanko.sign import fields, signers
    from pyhanko.stamp import TextStampStyle
    from pyhanko_certvalidator.registry import SimpleCertificateStore
    from pypdf import PdfReader
    from visible_signature import has_pdf_signature, has_visible_signature_stamp, next_pdf_signature_field_name

    from pct.firma_pkcs11 import FirmaPKCS11

    # Registrazione dell'OID signingCertificateV2 come nella firma con dispositivo.
    oid = "1.2.840.113549.1.9.16.2.47"
    cms.CMSAttributeType("content_type")
    cms.CMSAttributeType._map[oid] = "signing_certificate_v2"
    cms.CMSAttributeType._reverse_map["signing_certificate_v2"] = oid

    pdf = FirmaPKCS11._pdf_da_firmare(pdf)
    certificato = firmatario.certificato(credenziali)
    controlla_validita(certificato)
    gia_firmato = has_pdf_signature(pdf)
    if not gia_firmato:
        pdf = _con_timbro(pdf, certificato, modo=visible_signature_mode, luogo=visible_signature_place,
                          modo_data=visible_signature_datetime_mode)
        if not has_visible_signature_stamp(pdf):
            raise FirmaRemotaError("La firma PAdES non è stata applicata: manca il timbro visibile richiesto.")

    firmante = asn1_x509.Certificate.load(certificato.der)
    registro = SimpleCertificateStore()
    registro.register_multiple(asn1_x509.Certificate.load(raw) for raw in certificato.catena)
    lunghezza = certificato.x509().public_key().key_size // 8

    class _FirmaRemota(signers.Signer):
        def __init__(self):
            super().__init__(signing_cert=firmante, cert_registry=registro, prefer_pss=False, embed_roots=False)

        async def async_sign_raw(self, data: bytes, digest_algorithm: str, dry_run: bool = False) -> bytes:
            if dry_run:
                return bytes(max(1, lunghezza))
            if str(digest_algorithm).lower() != "sha256":
                raise FirmaRemotaError("La firma remota usa SHA-256.")
            return _firma_dati(firmatario, credenziali, certificato, data)

    lettore = PdfReader(io.BytesIO(pdf))
    larghezza = int(float(lettore.pages[-1].mediabox.width))
    campo = next_pdf_signature_field_name(lettore)
    metadati = signers.PdfSignatureMetadata(
        field_name=campo, md_algorithm="sha256", location=_luogo(visible_signature_place), reason=MOTIVO,
        name=certificato.intestatario, subfilter=fields.SigSeedSubFilter.PADES,
    )
    timbro = TextStampStyle(stamp_text="%(signer)s\nPer autentica e sottoscrizione\n%(ts)s",
                            timestamp_format="%d/%m/%Y ore %H:%M") if gia_firmato else None
    uscita = io.BytesIO()
    signers.PdfSigner(
        metadati, signer=_FirmaRemota(), stamp_style=timbro,
        new_field_spec=fields.SigFieldSpec(sig_field_name=campo, on_page=-1,
                                           box=(20, 10, max(40, larghezza - 20), 55) if gia_firmato else None),
    ).sign_pdf(IncrementalPdfFileWriter(io.BytesIO(pdf)), output=uscita)
    return uscita.getvalue(), certificato


__all__ = ["MOTIVO", "controlla_validita", "firma_cades", "firma_pades"]
