"""
Gestione firma digitale CAdES (.p7m) e PAdES per il PCT.
"""

import os
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.serialization import pkcs7


class FirmaDigitale:
    """Gestione della firma digitale per documenti PCT."""

    def __init__(self, p12_path: str, password: bytes):
        """
        Inizializza il dispositivo di firma.

        Args:
            p12_path: Percorso al file PKCS#12 (.p12 o .pfx)
            password: Password del dispositivo di firma
        """
        self.p12_path = Path(p12_path)
        self._private_key = None
        self._certificate = None
        self._chain = []
        self._load_p12(password)

    def _load_p12(self, password: bytes) -> None:
        """Carica chiave privata e certificato dal file P12."""
        with open(self.p12_path, "rb") as f:
            p12_data = f.read()
        private_key, certificate, chain = pkcs12.load_key_and_certificates(
            p12_data, password, default_backend()
        )
        self._private_key = private_key
        self._certificate = certificate
        self._chain = chain or []

    @property
    def intestatario(self) -> str:
        """Restituisce il nome del titolare del certificato."""
        subject = self._certificate.subject
        cn = subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        return cn[0].value if cn else "Sconosciuto"

    @property
    def scadenza(self):
        """Restituisce la data di scadenza del certificato."""
        return self._certificate.not_valid_after_utc

    def firma_cades(self, documento: bytes, detached: bool = True) -> bytes:
        """
        Firma un documento in formato CAdES (.p7m).

        Args:
            documento: Contenuto del documento da firmare
            detached: Se True crea firma detached (busta .p7m separata)

        Returns:
            Documento firmato in formato CAdES
        """
        builder = pkcs7.PKCS7SignatureBuilder()
        builder = builder.set_data(documento)
        builder = builder.add_signer(
            self._certificate,
            self._private_key,
            hashes.SHA256(),
        )
        for cert in self._chain:
            builder = builder.add_certificate(cert)

        options = [pkcs7.PKCS7Options.DetachedSignature] if detached else []
        signed = builder.sign(serialization.Encoding.DER, options)
        return signed

    def firma_pades(self, pdf_path: str, output_path: str) -> str:
        """
        Firma un PDF in formato PAdES (firma incorporata nel PDF).

        Args:
            pdf_path: Percorso al PDF da firmare
            output_path: Percorso dove salvare il PDF firmato

        Returns:
            Percorso al PDF firmato
        """
        try:
            from pyhanko.sign import signers, fields
            from pyhanko.sign.fields import SigFieldSpec
            from pyhanko.pdf_utils.reader import PdfFileReader
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

            signer = signers.SimpleSigner(
                signing_cert=self._certificate,
                signing_key=self._private_key,
                cert_registry=signers.SimpleCertificateStore.build(self._chain),
            )
            with open(pdf_path, "rb") as inf:
                writer = IncrementalPdfFileWriter(inf)
                fields.append_signature_field(writer, SigFieldSpec("Signature"))
                meta = signers.PdfSignatureMetadata(field_name="Signature")
                with open(output_path, "wb") as outf:
                    signers.sign_pdf(writer, meta, signer=signer, output=outf)
        except ImportError:
            raise RuntimeError(
                "pyhanko non installato. Eseguire: pip install pyhanko"
            )
        return output_path

    def salva_documento_firmato(
        self, documento: bytes, output_path: str, formato: str = "cades"
    ) -> str:
        """
        Firma e salva un documento.

        Args:
            documento: Contenuto del documento
            output_path: Percorso di output
            formato: 'cades' o 'pades'

        Returns:
            Percorso al file firmato
        """
        if formato == "cades":
            firmato = self.firma_cades(documento)
            out = output_path if output_path.endswith(".p7m") else output_path + ".p7m"
            with open(out, "wb") as f:
                f.write(firmato)
            return out
        elif formato == "pades":
            return self.firma_pades(output_path.replace(".pdf", "_unsigned.pdf"), output_path)
        else:
            raise ValueError(f"Formato non supportato: {formato}. Usare 'cades' o 'pades'.")
