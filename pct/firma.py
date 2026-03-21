"""
Gestione firma digitale CAdES (.p7m) e PAdES per il PCT.

Formati supportati:
  - P12/PFX  (PKCS#12): file unico con certificato + chiave + chain, protetto da password.
  - PEM:      due file separati — .crt (certificato) + .key (chiave privata).
              La chiave può essere cifrata (con password) o in chiaro.

Il formato viene selezionato automaticamente da FirmaDigitale.from_config().
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
        Inizializza il dispositivo di firma da file P12/PFX.

        Args:
            p12_path: Percorso al file PKCS#12 (.p12 o .pfx)
            password: Password del dispositivo di firma
        """
        self.p12_path = Path(p12_path)
        self._private_key = None
        self._certificate = None
        self._chain = []
        self._load_p12(password)

    # ---------------------------------------------------------------- costruttori alternativi

    @classmethod
    def from_pem(
        cls,
        cert_path: str,
        key_path: str,
        key_password: Optional[bytes] = None,
    ) -> "FirmaDigitale":
        """
        Carica firma da file PEM separati (cert + chiave).

        Usare quando il provider non rilascia il P12 ma fornisce .crt + .key.

        Args:
            cert_path:    Percorso al file certificato (.crt / .pem).
            key_path:     Percorso al file chiave privata (.key / .pem).
            key_password: Password della chiave privata (None se non cifrata).
        """
        obj = cls.__new__(cls)
        obj.p12_path = None
        obj._chain = []
        obj._load_pem(cert_path, key_path, key_password)
        return obj

    @classmethod
    def from_config(cls, cfg) -> "FirmaDigitale":
        """
        Crea l'istanza giusta in base alla ConfigFirma disponibile.

        Priorità:
          1. P12 (se p12_path esiste su disco)
          2. PEM (se cert_pem_path + key_pem_path esistono su disco)

        Raises:
            FileNotFoundError: se nessun formato è configurato/disponibile.
        """
        fmt = cfg.formato_attivo
        if fmt == "p12":
            return cls(
                p12_path=cfg.p12_path,
                password=cfg.password.encode() if isinstance(cfg.password, str) else cfg.password,
            )
        if fmt == "pem":
            pwd = None
            if cfg.key_pem_password:
                pwd = cfg.key_pem_password.encode() if isinstance(cfg.key_pem_password, str) else cfg.key_pem_password
            return cls.from_pem(
                cert_path=cfg.cert_pem_path,
                key_path=cfg.key_pem_path,
                key_password=pwd,
            )
        raise FileNotFoundError(
            "Nessun certificato di firma configurato. "
            "Configurare P12 (PCT_FIRMA_P12) oppure PEM (PCT_FIRMA_CERT + PCT_FIRMA_KEY)."
        )

    # ---------------------------------------------------------------- caricamento interno

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

    def _load_pem(
        self,
        cert_path: str,
        key_path: str,
        key_password: Optional[bytes],
    ) -> None:
        """Carica chiave privata e certificato da file PEM separati."""
        with open(cert_path, "rb") as f:
            cert_data = f.read()
        with open(key_path, "rb") as f:
            key_data = f.read()

        self._certificate = x509.load_pem_x509_certificate(cert_data, default_backend())
        self._private_key = serialization.load_pem_private_key(
            key_data,
            password=key_password,
            backend=default_backend(),
        )
        # Estrae certificati intermedi (chain) se presenti nello stesso file cert
        self._chain = []
        try:
            import re
            pem_certs = re.findall(
                rb"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----",
                cert_data,
                re.DOTALL,
            )
            for pem_block in pem_certs[1:]:
                try:
                    ca_cert = x509.load_pem_x509_certificate(pem_block, default_backend())
                    self._chain.append(ca_cert)
                except Exception:
                    pass
        except Exception:
            pass

    # ---------------------------------------------------------------- proprietà

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

    def verifica_scadenza(self, giorni_preavviso: int = 30) -> dict:
        """
        Verifica che il certificato di firma non sia scaduto e avvisa se la scadenza
        è imminente.

        Conforme a D.M. 44/2011 art. 12: il deposito è rifiutato se il certificato
        del firmatario risulta scaduto o revocato al momento dell'apposizione della firma.

        Args:
            giorni_preavviso: Numero di giorni prima della scadenza per mostrare avviso
                              (default: 30 — soglia raccomandata PST)

        Returns:
            dict con chiavi:
              - valido (bool)     : True se il certificato è ancora valido
              - scaduto (bool)    : True se è già scaduto
              - scadenza (str)    : data scadenza ISO (YYYY-MM-DD)
              - giorni_restanti (int): giorni alla scadenza (negativo se scaduto)
              - avviso_imminente (bool): True se < giorni_preavviso alla scadenza
              - messaggio (str)   : messaggio descrittivo
        """
        from datetime import datetime, timezone

        now        = datetime.now(tz=timezone.utc)
        scad       = self.scadenza
        delta      = (scad - now).days
        scaduto    = delta < 0
        imminente  = not scaduto and delta <= giorni_preavviso

        if scaduto:
            msg = (
                f"CERTIFICATO SCADUTO il {scad.strftime('%d/%m/%Y')} "
                f"({abs(delta)} giorni fa). Depositare con questo certificato "
                f"causa rifiuto automatico dal PST (D.M. 44/2011 art. 12)."
            )
        elif imminente:
            msg = (
                f"Attenzione: il certificato scade tra {delta} giorni "
                f"({scad.strftime('%d/%m/%Y')}). Rinnovare prima di quel termine."
            )
        else:
            msg = (
                f"Certificato valido fino al {scad.strftime('%d/%m/%Y')} "
                f"({delta} giorni rimanenti)."
            )

        return {
            "valido":            not scaduto,
            "scaduto":           scaduto,
            "scadenza":          scad.strftime("%Y-%m-%d"),
            "giorni_restanti":   delta,
            "avviso_imminente":  imminente,
            "messaggio":         msg,
        }

    # ---------------------------------------------------------------- firma

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
