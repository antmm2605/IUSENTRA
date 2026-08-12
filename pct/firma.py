"""
Gestione firma digitale CAdES (.p7m) e PAdES per il PCT.

Formati supportati:
  - P12/PFX  (PKCS#12): file unico con certificato + chiave + chain, protetto da password.
  - PEM:      due file separati — .crt (certificato) + .key (chiave privata).
              La chiave può essere cifrata (con password) o in chiaro.

Il backend viene selezionato a partire dalla configurazione esplicita salvata
nello studio.
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.hazmat.primitives.serialization import pkcs7
from visible_signature import prepare_document_for_signature, resolve_visible_signature_place


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

        La scelta segue `backend_preferito` e solo in modalità `auto`
        ricade sul backend rilevato tecnicamente.

        Per PKCS#11 (Aruba Key) usare il backend dedicato FirmaPKCS11
        o il flusso in-device del Local Signer.

        Raises:
            FileNotFoundError: se nessun formato è configurato/disponibile.
        """
        fmt = getattr(cfg, "backend_firma_effettivo", None) or cfg.formato_attivo
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
        if fmt == "pkcs11":
            raise ValueError(
                "Backend PKCS#11 selezionato. "
                "Usare pct.firma.crea_signer_da_config(..., pin=...) oppure il flusso Local Signer."
            )
        raise FileNotFoundError(
            "Nessun certificato di firma configurato. "
            "Configurare P12 (PCT_FIRMA_P12) oppure PEM (PCT_FIRMA_CERT + PCT_FIRMA_KEY) "
            "oppure token PKCS#11 (Aruba Key) nel pannello Impostazioni → Firma Digitale."
        )

    @classmethod
    def da_config(cls, cfg) -> "FirmaDigitale":
        """Alias italiano di from_config() — compatibilità con web/app.py."""
        return cls.from_config(cfg)

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

    def _prepare_pdf_for_visible_signature(
        self,
        documento: bytes,
        *,
        visible_signature_mode: str = "laterale",
        visible_signature_place: str = "",
        visible_signature_datetime_mode: str = "data_ora",
    ) -> bytes:
        luogo = resolve_visible_signature_place(
            city=visible_signature_place or os.getenv("PCT_STUDIO_CITY", ""),
            province=os.getenv("PCT_STUDIO_PROVINCIA", ""),
            address=os.getenv("PCT_STUDIO_INDIRIZZO", ""),
        )
        issuer_cn = ""
        try:
            issuer_cn_attrs = self._certificate.issuer.get_attributes_for_oid(NameOID.COMMON_NAME)
            if issuer_cn_attrs:
                issuer_cn = str(issuer_cn_attrs[0].value or "").strip()
        except Exception:
            issuer_cn = ""
        return prepare_document_for_signature(
            documento,
            intestatario=self.intestatario,
            data_firma=datetime.now().astimezone(),
            luogo=luogo,
            issuer=issuer_cn,
            serial=format(getattr(self._certificate, "serial_number", 0), "X"),
            mode=visible_signature_mode,
            datetime_mode=visible_signature_datetime_mode,
        )

    def firma_cades(
        self,
        documento: bytes,
        detached: bool = True,
        *,
        visible_signature_mode: str = "laterale",
        visible_signature_place: str = "",
        visible_signature_datetime_mode: str = "data_ora",
    ) -> bytes:
        """
        Firma un documento in formato CAdES (.p7m).

        Args:
            documento: Contenuto del documento da firmare
            detached: Se True crea firma detached (busta .p7m separata)

        Returns:
            Documento firmato in formato CAdES
        """
        if not detached:
            documento = self._prepare_pdf_for_visible_signature(
                documento,
                visible_signature_mode=visible_signature_mode,
                visible_signature_place=visible_signature_place,
                visible_signature_datetime_mode=visible_signature_datetime_mode,
            )
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

    def firma_pades(
        self,
        pdf_path: str,
        output_path: str,
        *,
        visible_signature_mode: str = "laterale",
        visible_signature_place: str = "",
        visible_signature_datetime_mode: str = "data_ora",
    ) -> str:
        """
        Firma un PDF in formato PAdES (firma incorporata nel PDF).

        Args:
            pdf_path: Percorso al PDF da firmare
            output_path: Percorso dove salvare il PDF firmato

        Returns:
            Percorso al PDF firmato
        """
        tmp_visible_path: str | None = None
        try:
            from pyhanko.sign import signers, fields
            from pyhanko.sign.fields import SigFieldSpec
            from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter

            source_path = pdf_path
            original_pdf = Path(pdf_path).read_bytes()
            prepared_pdf = self._prepare_pdf_for_visible_signature(
                original_pdf,
                visible_signature_mode=visible_signature_mode,
                visible_signature_place=visible_signature_place,
                visible_signature_datetime_mode=visible_signature_datetime_mode,
            )
            if prepared_pdf != original_pdf:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_visible:
                    tmp_visible.write(prepared_pdf)
                    tmp_visible_path = tmp_visible.name
                source_path = tmp_visible_path

            signer = signers.SimpleSigner(
                signing_cert=self._certificate,
                signing_key=self._private_key,
                cert_registry=signers.SimpleCertificateStore.build(self._chain),
            )
            with open(source_path, "rb") as inf:
                writer = IncrementalPdfFileWriter(inf)
                fields.append_signature_field(writer, SigFieldSpec("Signature"))
                meta = signers.PdfSignatureMetadata(field_name="Signature")
                with open(output_path, "wb") as outf:
                    signers.sign_pdf(writer, meta, signer=signer, output=outf)
        except ImportError:
            raise RuntimeError(
                "pyhanko non installato. Eseguire: pip install pyhanko"
            )
        finally:
            if tmp_visible_path:
                try:
                    os.unlink(tmp_visible_path)
                except FileNotFoundError:
                    pass
        return output_path

    def salva_documento_firmato(
        self,
        documento: bytes,
        output_path: str,
        formato: str = "cades",
        *,
        visible_signature_mode: str = "laterale",
        visible_signature_place: str = "",
        visible_signature_datetime_mode: str = "data_ora",
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
            detached = not documento.startswith(b"%PDF")
            try:
                firmato = self.firma_cades(
                    documento,
                    detached=detached,
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                    visible_signature_datetime_mode=visible_signature_datetime_mode,
                )
            except TypeError as exc:
                if "visible_signature_datetime_mode" not in str(exc):
                    raise
                firmato = self.firma_cades(
                    documento,
                    detached=detached,
                    visible_signature_mode=visible_signature_mode,
                    visible_signature_place=visible_signature_place,
                )
            out = output_path if output_path.endswith(".p7m") else output_path + ".p7m"
            with open(out, "wb") as f:
                f.write(firmato)
            return out
        elif formato == "pades":
            suffix = Path(output_path).suffix or ".pdf"
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(documento)
                tmp_path = tmp.name
            try:
                try:
                    return self.firma_pades(
                        tmp_path,
                        output_path,
                        visible_signature_mode=visible_signature_mode,
                        visible_signature_place=visible_signature_place,
                        visible_signature_datetime_mode=visible_signature_datetime_mode,
                    )
                except TypeError as exc:
                    if (
                        "visible_signature_mode" not in str(exc)
                        and "visible_signature_place" not in str(exc)
                        and "visible_signature_datetime_mode" not in str(exc)
                    ):
                        raise
                    return self.firma_pades(tmp_path, output_path)
            finally:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass
        else:
            raise ValueError(f"Formato non supportato: {formato}. Usare 'cades' o 'pades'.")


def crea_signer_da_config(cfg, pin: Optional[str] = None):
    """
    Factory unica del backend firma a partire dalla configurazione studio.

    - PKCS#11: restituisce `FirmaPKCS11` e richiede il PIN a runtime.
    - P12/PEM: restituisce `FirmaDigitale`.
    """
    backend = getattr(cfg, "backend_firma_effettivo", None) or cfg.formato_attivo
    if backend == "pkcs11":
        if not pin:
            raise ValueError("PIN obbligatorio per usare il backend PKCS#11.")
        from pct.firma_pkcs11 import FirmaPKCS11
        return FirmaPKCS11.da_config(cfg, pin=pin)
    return FirmaDigitale.da_config(cfg)


# ============================================================
# Analisi firme digitali — lettura certificati da .p7m / PDF
# ============================================================

def analizza_firma_documento(data: bytes, nome_file: str = "") -> list[dict]:
    """
    Analizza le firme digitali presenti in un documento CAdES (.p7m) o PAdES (PDF).

    Returns:
        Lista di dict, uno per ogni firmatario trovato, con le chiavi:
        intestatario, cn, org, emittente, emittente_cn, valido_dal, valido_al,
        scaduto, avviso_imminente, giorni_restanti, seriale, algoritmo, formato.
        Lista vuota se nessuna firma trovata o formato non supportato.
    """
    nome_lower = (nome_file or "").lower()
    if nome_lower.endswith(".p7m") or _is_cades(data):
        return _analizza_cades(data)
    if nome_lower.endswith(".pdf") or data[:4] == b"%PDF":
        return _analizza_pades(data)
    return []


def _is_cades(data: bytes) -> bool:
    """Controlla se i byte sono un envelope CAdES/PKCS#7 SignedData."""
    try:
        from asn1crypto import cms
        ci = cms.ContentInfo.load(data)
        return ci["content_type"].native == "signed_data"
    except Exception:
        return False


def busta_cades_valida(data: bytes) -> bool:
    """
    Verifica che il payload sia una busta CAdES/PKCS#7 realmente firmata.

    Non basta che il file abbia estensione ``.p7m``: deve contenere
    ``SignedData`` con almeno un firmatario e almeno un certificato.
    """
    try:
        from asn1crypto import cms

        ci = cms.ContentInfo.load(data)
        if ci["content_type"].native != "signed_data":
            return False
        signed_data = ci["content"]
        signer_infos = signed_data["signer_infos"]
        certs = signed_data["certificates"]
        return bool(signer_infos) and certs is not None and len(certs) > 0
    except Exception:
        return False


def attributi_cades_bes_mancanti(data: bytes) -> list[str]:
    """Elenca gli attributi CAdES-BES assenti da uno o piu' firmatari."""
    try:
        from asn1crypto import cms

        ci = cms.ContentInfo.load(data)
        if ci["content_type"].native != "signed_data":
            return ["signed_data"]
        signer_infos = ci["content"]["signer_infos"]
        if not signer_infos:
            return ["firmatario"]
        required = {
            "content_type": "content-type",
            "message_digest": "message-digest",
            "signing_time": "signing-time",
            "1.2.840.113549.1.9.16.2.47": "signingCertificateV2",
        }
        missing: set[str] = set()
        for signer_info in signer_infos:
            present: set[str] = set()
            for attr in signer_info["signed_attrs"] or []:
                present.add(str(attr["type"].native or ""))
                present.add(str(attr["type"].dotted or ""))
            missing.update(label for oid, label in required.items() if oid not in present)
        return sorted(missing)
    except Exception:
        return ["profilo CAdES-BES"]


def profilo_cades_bes_valido(data: bytes) -> bool:
    """Verifica il profilo usato da Studio Telematico per DatiAtto.xml.p7m."""
    return busta_cades_valida(data) and not attributi_cades_bes_mancanti(data)


def estrai_contenuto_cades(data: bytes) -> bytes | None:
    """Estrae il contenuto incapsulato da una busta CAdES/PKCS#7 signed-data."""
    try:
        from asn1crypto import cms

        ci = cms.ContentInfo.load(data)
        if ci["content_type"].native != "signed_data":
            return None
        signed_data = ci["content"]
        content = signed_data["encap_content_info"]["content"]
        if content.native is None:
            return None
        if isinstance(content.native, bytes):
            return content.native
        return bytes(content.contents)
    except Exception:
        return None


def _dn_campo(asn1_name, campo_hf: str) -> str:
    """Estrae un campo dal Distinguished Name tramite human_friendly label."""
    try:
        hf = asn1_name.human_friendly  # es. "Common Name: Mario Rossi, Organization: ..."
        for parte in hf.split(","):
            parte = parte.strip()
            if parte.lower().startswith(campo_hf.lower() + ":"):
                return parte.split(":", 1)[-1].strip()
    except Exception:
        pass
    return ""


def _analizza_cades(data: bytes) -> list[dict]:
    """Estrae info certificati da un envelope CAdES (.p7m) con asn1crypto."""
    try:
        from asn1crypto import cms
        from datetime import datetime, timezone
    except ImportError:
        return []

    try:
        ci = cms.ContentInfo.load(data)
        if ci["content_type"].native != "signed_data":
            return []
        sd = ci["content"]
        certs_raw = sd["certificates"]
        sinfos = sd["signer_infos"]
        now = datetime.now(tz=timezone.utc)
        risultati = []

        for sinfo in sinfos:
            cert = None
            firma_dt = None
            sid = sinfo["sid"]
            # Abbina il certificato al firmatario tramite issuer+serial
            if sid.name == "issuer_and_serial_number":
                ias = sid.chosen
                serial_target = ias["serial_number"].native
                for c_entry in certs_raw:
                    c = c_entry.chosen
                    if c.serial_number == serial_target:
                        cert = c
                        break
            # Fallback: primo certificato non-CA
            if cert is None:
                for c_entry in certs_raw:
                    c = c_entry.chosen
                    if not c.ca:
                        cert = c
                        break
            if cert is None and len(certs_raw) > 0:
                cert = certs_raw[0].chosen
            if cert is None:
                continue

            # Date di validità
            not_after = cert.not_valid_after
            not_before = cert.not_valid_before
            if not_after.tzinfo is None:
                not_after = not_after.replace(tzinfo=timezone.utc)
            if not_before.tzinfo is None:
                not_before = not_before.replace(tzinfo=timezone.utc)
            delta = (not_after - now).days
            scaduto = delta < 0
            avviso = not scaduto and delta <= 30

            # Nomi soggetto / emittente
            cn_val = _dn_campo(cert.subject, "Common Name") or _dn_campo(cert.subject, "CN")
            org_val = _dn_campo(cert.subject, "Organization") or _dn_campo(cert.subject, "O") or None
            emittente_cn = _dn_campo(cert.issuer, "Common Name") or _dn_campo(cert.issuer, "CN")
            emittente_org = _dn_campo(cert.issuer, "Organization") or _dn_campo(cert.issuer, "O") or None

            # Algoritmo di firma
            algo = ""
            try:
                algo_raw = sinfo["signature_algorithm"]["algorithm"].native or ""
                algo = algo_raw.upper().replace("_WITH_", " + ").replace("WITHRSAENCRYPTION", "")
                if not algo:
                    algo = "RSA + SHA-256"
            except Exception:
                algo = "RSA + SHA-256"

            try:
                signed_attrs = sinfo["signed_attrs"]
                if signed_attrs is not None:
                    for attr in signed_attrs:
                        if attr["type"].native != "signing_time":
                            continue
                        values = attr["values"]
                        if not values:
                            continue
                        firma_dt = values[0].native
                        if firma_dt is not None and getattr(firma_dt, "tzinfo", None) is None:
                            firma_dt = firma_dt.replace(tzinfo=timezone.utc)
                        break
            except Exception:
                firma_dt = None

            risultati.append({
                "intestatario": cn_val or org_val or "Sconosciuto",
                "cn": cn_val,
                "org": org_val,
                "emittente": emittente_org or emittente_cn or "N/A",
                "emittente_cn": emittente_cn,
                "valido_dal": not_before.strftime("%Y-%m-%d"),
                "valido_al": not_after.strftime("%Y-%m-%d"),
                "scaduto": scaduto,
                "avviso_imminente": avviso,
                "giorni_restanti": delta,
                "seriale": format(cert.serial_number, "X"),
                "algoritmo": algo,
                "formato": "CAdES",
                "data_firma": firma_dt.isoformat() if firma_dt else "",
            })

        return risultati
    except Exception:
        return []


def _analizza_pades(data: bytes) -> list[dict]:
    """Estrae info firme incorporate in un PDF (PAdES) tramite pyhanko."""
    # Verifica rapida presenza firma nel PDF prima di caricare pyhanko
    if b"/Type /Sig" not in data and b"/Type/Sig" not in data:
        return []
    try:
        import io
        from datetime import datetime, timezone
        from pyhanko.pdf_utils.reader import PdfFileReader
        reader = PdfFileReader(io.BytesIO(data))
        embedded = reader.embedded_signatures
        now = datetime.now(tz=timezone.utc)
        risultati = []
        for sig in embedded:
            try:
                cert = sig.signer_cert  # cryptography.x509.Certificate
                not_after = cert.not_valid_after_utc
                not_before = cert.not_valid_before_utc
                delta = (not_after - now).days
                scaduto = delta < 0
                avviso = not scaduto and delta <= 30
                cn_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                cn_val = cn_attrs[0].value if cn_attrs else ""
                org_attrs = cert.subject.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)
                org_val = org_attrs[0].value if org_attrs else None
                issuer_cn_a = cert.issuer.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
                issuer_cn = issuer_cn_a[0].value if issuer_cn_a else ""
                issuer_org_a = cert.issuer.get_attributes_for_oid(x509.NameOID.ORGANIZATION_NAME)
                issuer_org = issuer_org_a[0].value if issuer_org_a else None
                risultati.append({
                    "intestatario": cn_val or org_val or "Sconosciuto",
                    "cn": cn_val,
                    "org": org_val,
                    "emittente": issuer_org or issuer_cn or "N/A",
                    "emittente_cn": issuer_cn,
                    "valido_dal": not_before.strftime("%Y-%m-%d"),
                    "valido_al": not_after.strftime("%Y-%m-%d"),
                    "scaduto": scaduto,
                    "avviso_imminente": avviso,
                    "giorni_restanti": delta,
                    "seriale": format(cert.serial_number, "X"),
                    "algoritmo": "RSA + SHA-256",
                    "formato": "PAdES",
                    "data_firma": "",
                })
            except Exception:
                continue
        return risultati
    except Exception:
        return []
