"""
Firma digitale CAdES in-device tramite token PKCS#11 (Aruba Key, Namirial, ecc.).

La chiave privata non lascia MAI il dispositivo: la firma avviene interamente
all'interno del token, come richiesto dalla normativa per i certificati qualificati.

Architettura:
  - FirmaPKCS11  : firma documenti via token; stessa interfaccia di FirmaDigitale
  - lista_token()         : enumera i token presenti SENZA PIN (sola lettura)
  - libreria_disponibile(): restituisce la prima libreria PKCS#11 trovata

Requisiti (opzionali — importati solo se si usa PKCS#11):
  pip install python-pkcs11 asn1crypto

Configurazione Docker/Linux:
  - Installa pcscd + opensc sul HOST: apt install pcscd opensc
  - Inserisci Aruba Key nella porta USB
  - Monta il socket pcscd nel container:
      volumes:
        - /run/pcscd/pcscd.comm:/run/pcscd/pcscd.comm
  - Imposta PCT_PKCS11_LIBRARY=/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so
  - Imposta PCT_PKCS11_PIN=<PIN-dispositivo> oppure lascia vuoto e inseriscilo
    nella UI ad ogni firma (approccio consigliato — il PIN non viene salvato)

Variabili d'ambiente:
  PCT_PKCS11_LIBRARY  percorso alla .so/.dll PKCS#11
  PCT_PKCS11_SLOT     slot ID (default: 0 oppure primo slot con token)
  PCT_PKCS11_LABEL    etichetta del certificato nel token (opzionale)
"""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ── Percorsi di default per librerie PKCS#11 ────────────────────────────────
_LIBRERIE_DEFAULT: List[str] = [
    # Windows — Bit4id / Aruba Key
    r"C:\Windows\System32\bit4xpki.dll",
    r"C:\Windows\SysWOW64\bit4xpki.dll",
    r"C:\Program Files\Bit4id\MinVa\bit4xpki.dll",
    r"C:\Program Files (x86)\Bit4id\MinVa\bit4xpki.dll",
    r"C:\Program Files\Bit4id\bit4xpki.dll",
    r"C:\Program Files (x86)\Bit4id\bit4xpki.dll",
    r"C:\Program Files\Bit4id\MinVa\windows\bit4xpki.dll",
    r"C:\Program Files (x86)\Bit4id\MinVa\windows\bit4xpki.dll",
    # Windows — Namirial / provider vari
    r"C:\Windows\System32\OkiPKCS11.dll",
    r"C:\Windows\SysWOW64\OkiPKCS11.dll",
    r"C:\Program Files\Namirial\pkcs11.dll",
    r"C:\Program Files (x86)\Namirial\pkcs11.dll",
    r"C:\Windows\System32\cvP11.dll",
    r"C:\Windows\System32\cvcP11.dll",
    r"C:\Windows\SysWOW64\cvP11.dll",
    r"C:\Windows\SysWOW64\cvcP11.dll",
    # Linux — OpenSC (funziona con Aruba Key via pcscd)
    "/usr/lib/x86_64-linux-gnu/opensc-pkcs11.so",
    "/usr/lib/opensc-pkcs11.so",
    "/usr/lib/arm-linux-gnueabihf/opensc-pkcs11.so",
    "/usr/lib64/opensc-pkcs11.so",
    # Linux — p11-kit proxy
    "/usr/lib/x86_64-linux-gnu/pkcs11/p11-kit-trust.so",
    # macOS — OpenSC
    "/usr/local/lib/opensc-pkcs11.so",
    "/Library/OpenSC/lib/opensc-pkcs11.so",
    # Windows — fallback storici
    r"C:\Windows\System32\aetpkss1.dll",
    r"C:\Windows\System32\bit4opki.dll",
    r"C:\Windows\System32\cmP11.dll",
]

_ENV_LIBRARY = "PCT_PKCS11_LIBRARY"
_ENV_SLOT    = "PCT_PKCS11_SLOT"
_ENV_LABEL   = "PCT_PKCS11_LABEL"


def _build_cades_bes(
    documento: bytes,
    signature_bytes: bytes,
    cert_der: bytes,
    signed_attrs_der: bytes,
    *,
    detached: bool = False,
) -> bytes:
    """
    Costruisce una busta CAdES-BES DER valida a partire da firma, certificato
    e SignedAttributes già preparati.
    """
    try:
        from asn1crypto import cms, algos, core, x509 as _ax509
    except ImportError as exc:
        raise ImportError(
            "asn1crypto non installato. Eseguire: pip install asn1crypto"
        ) from exc

    cert_asn1 = _ax509.Certificate.load(cert_der)
    tbs = cert_asn1["tbs_certificate"]
    signed_attrs_obj = cms.CMSAttributes.load(signed_attrs_der)

    signer_info = cms.SignerInfo({
        "version": cms.CMSVersion(1),
        "sid": cms.SignerIdentifier({
            "issuer_and_serial_number": cms.IssuerAndSerialNumber({
                "issuer": tbs["issuer"],
                "serial_number": tbs["serial_number"],
            }),
        }),
        "digest_algorithm": algos.DigestAlgorithm({
            "algorithm": algos.DigestAlgorithmId("sha256"),
        }),
        "signed_attrs": signed_attrs_obj,
        "signature_algorithm": algos.SignedDigestAlgorithm({
            "algorithm": algos.SignedDigestAlgorithmId("sha256_rsa"),
        }),
        "signature": core.OctetString(signature_bytes),
    })

    encap_content_info = {"content_type": cms.ContentType("data")}
    if not detached:
        encap_content_info["content"] = documento

    signed_data = cms.SignedData({
        "version": cms.CMSVersion(1),
        "digest_algorithms": cms.DigestAlgorithms([
            algos.DigestAlgorithm({
                "algorithm": algos.DigestAlgorithmId("sha256"),
            }),
        ]),
        "encap_content_info": encap_content_info,
        "certificates": cms.CertificateSet([
            cms.CertificateChoices(
                name="certificate",
                value=cert_asn1,
            ),
        ]),
        "signer_infos": cms.SignerInfos([signer_info]),
    })

    content_info = cms.ContentInfo({
        "content_type": cms.ContentType("signed_data"),
        "content": signed_data,
    })

    return content_info.dump()


def _score_library(lib_path: str) -> int:
    try:
        import pkcs11
    except Exception:
        return 1 if Path(lib_path).exists() else 0

    try:
        lib = pkcs11.lib(lib_path)
    except Exception:
        return 0

    try:
        slots = list(lib.get_slots(token_present=True))
        return 3 if slots else 1
    except Exception:
        return 1


def _candidate_libraries() -> List[str]:
    candidati: List[str] = []

    def _add(path: str) -> None:
        valore = str(path or "").strip()
        if valore and Path(valore).exists() and valore not in candidati:
            candidati.append(valore)

    env_lib = os.environ.get(_ENV_LIBRARY, "")
    _add(env_lib)
    for lib in _LIBRERIE_DEFAULT:
        _add(lib)
    return candidati


def libreria_disponibile() -> Optional[str]:
    """
    Restituisce il percorso della prima libreria PKCS#11 trovata sul sistema.

    Controlla prima la variabile d'ambiente PCT_PKCS11_LIBRARY, poi le
    posizioni di default comuni (OpenSC, Aruba, Namirial).
    """
    env_lib = os.environ.get(_ENV_LIBRARY, "")
    if env_lib and Path(env_lib).exists():
        return env_lib

    candidati = _candidate_libraries()
    if not candidati:
        return None

    candidati_ordinati = sorted(
        candidati,
        key=_score_library,
        reverse=True,
    )
    return candidati_ordinati[0]


# ── TokenInfo ────────────────────────────────────────────────────────────────

class TokenInfo:
    """Informazioni su un token PKCS#11 rilevato (senza PIN)."""

    def __init__(
        self,
        slot_id: int,
        label: str,
        manufacturer: str,
        model: str,
        serial: str,
        ha_cert: bool,
    ):
        self.slot_id      = slot_id
        self.label        = label
        self.manufacturer = manufacturer
        self.model        = model
        self.serial       = serial
        self.ha_cert      = ha_cert

    def as_dict(self) -> Dict[str, Any]:
        return {
            "slot_id":      self.slot_id,
            "label":        self.label,
            "manufacturer": self.manufacturer,
            "model":        self.model,
            "serial":       self.serial,
            "ha_cert":      self.ha_cert,
        }

    def __repr__(self) -> str:
        return (
            f"<Token slot={self.slot_id} label={self.label!r} "
            f"mfr={self.manufacturer!r} cert={'si' if self.ha_cert else 'no'}>"
        )


def lista_token(library_path: Optional[str] = None) -> List[TokenInfo]:
    """
    Elenca i token PKCS#11 presenti SENZA autenticazione (nessun PIN richiesto).

    Utile per mostrare all'utente quali dispositivi sono collegati prima di
    chiedere il PIN.

    Args:
        library_path: Percorso alla libreria .so/.dll. Se None, viene
                      auto-rilevata con libreria_disponibile().

    Returns:
        Lista di TokenInfo. Vuota se nessun token trovato o libreria assente.
    """
    lib_path = library_path or libreria_disponibile()
    if not lib_path:
        logger.debug("lista_token: nessuna libreria PKCS#11 trovata.")
        return []

    try:
        import pkcs11
        from pkcs11 import Attribute, ObjectClass
    except ImportError:
        logger.warning(
            "python-pkcs11 non installato — impossibile rilevare token. "
            "Eseguire: pip install python-pkcs11"
        )
        return []

    try:
        lib = pkcs11.lib(lib_path)
    except Exception as e:
        logger.warning("lista_token: errore caricamento libreria '%s': %s", lib_path, e)
        return []

    result: List[TokenInfo] = []
    try:
        for slot in lib.get_slots(token_present=True):
            try:
                info = slot.get_token()
                ha_cert = False
                # Prova ad aprire sessione anonima per verificare presenza certificato
                try:
                    with info.open() as sess:
                        certs = list(sess.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
                        ha_cert = len(certs) > 0
                except Exception:
                    pass

                result.append(TokenInfo(
                    slot_id=slot.slot_id,
                    label=info.label.strip(),
                    manufacturer=info.manufacturer_id.strip(),
                    model=info.model.strip(),
                    serial=info.serial.strip() if hasattr(info, "serial") else "",
                    ha_cert=ha_cert,
                ))
            except Exception as e:
                logger.debug("lista_token: errore slot %s: %s", slot, e)
    except Exception as e:
        logger.warning("lista_token: errore enumerazione slot: %s", e)

    return result


# ── FirmaPKCS11 ──────────────────────────────────────────────────────────────

class FirmaPKCS11:
    """
    Firma digitale CAdES (.p7m) tramite token PKCS#11 (Aruba Key, ecc.).

    La chiave privata non lascia mai il dispositivo: l'operazione crittografica
    viene eseguita all'interno del token usando il meccanismo CKM_SHA256_RSA_PKCS.

    Interfaccia compatibile con FirmaDigitale — può essere usata al suo posto
    in DepositoCivile e nelle route di firma.

    Esempio d'uso::

        with FirmaPKCS11(library_path=..., slot_id=0, pin="12345") as f:
            stato = f.verifica_scadenza()
            firmato = f.firma_cades(documento_bytes)
    """

    def __init__(
        self,
        library_path: str,
        slot_id: Optional[int],
        pin: str,
        label: Optional[str] = None,
    ):
        """
        Args:
            library_path: Percorso alla libreria PKCS#11 (.so o .dll).
            slot_id:      Slot ID del token. None = usa il primo slot con token.
            pin:          PIN del token (NON viene salvato su disco).
            label:        Etichetta del certificato nel token (opzionale).
                          Se None viene usato il primo certificato trovato.
        """
        self._lib_path  = library_path
        self._slot_id   = slot_id
        self._pin       = pin
        self._label     = label

        # Lazy-init al primo utilizzo
        self._lib          = None
        self._session      = None
        self._cert_der: Optional[bytes] = None
        self._certificate  = None   # cryptography x509.Certificate

    # ── init libreria ────────────────────────────────────────────────────────

    def _get_lib(self):
        if self._lib is None:
            try:
                import pkcs11
                self._lib = pkcs11.lib(self._lib_path)
            except ImportError:
                raise ImportError(
                    "python-pkcs11 non installato. "
                    "Eseguire: pip install python-pkcs11"
                )
            except Exception as e:
                raise RuntimeError(
                    f"Impossibile caricare libreria PKCS#11 '{self._lib_path}': {e}"
                )
        return self._lib

    def _apri_sessione(self):
        """Apre una sessione autenticata con il PIN."""
        import pkcs11

        lib = self._get_lib()
        slots = lib.get_slots(token_present=True)
        if not slots:
            raise RuntimeError(
                "Nessun token PKCS#11 rilevato. "
                "Inserire l'Aruba Key (o altro token) nella porta USB e riprovare."
            )

        slot = None
        # Cerca per slot_id o label
        for s in slots:
            if self._slot_id is not None and s.slot_id == self._slot_id:
                slot = s
                break
            if self._label:
                try:
                    tok_info = s.get_token()
                    if self._label.strip() in tok_info.label.strip():
                        slot = s
                        break
                except Exception:
                    pass
        if slot is None:
            slot = slots[0]  # primo disponibile

        token = slot.get_token()
        self._session = token.open(user_pin=self._pin, rw=False)
        logger.info(
            "Sessione PKCS#11 aperta: token='%s' slot=%d",
            token.label.strip(), slot.slot_id,
        )

    def _get_session(self):
        if self._session is None:
            self._apri_sessione()
        return self._session

    # ── caricamento certificato ──────────────────────────────────────────────

    def _carica_cert(self) -> None:
        """Legge il certificato di firma dal token (richiede sessione aperta)."""
        from pkcs11 import Attribute, ObjectClass
        from cryptography import x509 as _cx509
        from cryptography.hazmat.backends import default_backend

        sess = self._get_session()
        certs = list(sess.get_objects({Attribute.CLASS: ObjectClass.CERTIFICATE}))
        if not certs:
            raise RuntimeError(
                "Nessun certificato trovato nel token. "
                "Verificare che Aruba Key sia configurata correttamente."
            )

        cert_obj = None
        if self._label:
            for c in certs:
                try:
                    lbl = bytes(c[Attribute.LABEL]).decode("utf-8", errors="replace").strip()
                    if self._label in lbl:
                        cert_obj = c
                        break
                except Exception:
                    pass

        if cert_obj is None:
            cert_obj = certs[0]  # primo certificato (di norma quello di firma)

        self._cert_der = bytes(cert_obj[Attribute.VALUE])
        self._certificate = _cx509.load_der_x509_certificate(
            self._cert_der, default_backend()
        )
        logger.info("Certificato PKCS#11 caricato: %s", self._certificate.subject)

    def _get_cert(self):
        if self._certificate is None:
            self._carica_cert()
        return self._certificate

    # ── proprietà (interfaccia FirmaDigitale) ────────────────────────────────

    @property
    def intestatario(self) -> str:
        """Nome del titolare del certificato."""
        from cryptography import x509 as _cx509
        cert = self._get_cert()
        cn = cert.subject.get_attributes_for_oid(_cx509.NameOID.COMMON_NAME)
        return cn[0].value if cn else "Sconosciuto"

    @property
    def scadenza(self):
        """Data di scadenza del certificato (datetime con tz)."""
        return self._get_cert().not_valid_after_utc

    def verifica_scadenza(self, giorni_preavviso: int = 30) -> dict:
        """
        Verifica validità del certificato (D.M. 44/2011 art. 12).

        Returns:
            dict con campi: valido, scaduto, scadenza, giorni_restanti,
            avviso_imminente, messaggio.
        """
        from datetime import datetime, timezone
        now   = datetime.now(tz=timezone.utc)
        scad  = self.scadenza
        delta = (scad - now).days
        scaduto   = delta < 0
        imminente = not scaduto and delta <= giorni_preavviso

        if scaduto:
            msg = (
                f"CERTIFICATO SCADUTO il {scad.strftime('%d/%m/%Y')} "
                f"({abs(delta)} giorni fa) — deposito non ammesso (D.M. 44/2011 art. 12)."
            )
        elif imminente:
            msg = (
                f"Attenzione: certificato in scadenza tra {delta} giorni "
                f"({scad.strftime('%d/%m/%Y')}). Rinnovare prima del termine."
            )
        else:
            msg = (
                f"Certificato valido fino al {scad.strftime('%d/%m/%Y')} "
                f"({delta} giorni rimanenti)."
            )

        return {
            "valido":           not scaduto,
            "scaduto":          scaduto,
            "scadenza":         scad.strftime("%Y-%m-%d"),
            "giorni_restanti":  delta,
            "avviso_imminente": imminente,
            "messaggio":        msg,
        }

    # ── firma in-device ──────────────────────────────────────────────────────

    def firma_cades(self, documento: bytes, detached: bool = True) -> bytes:
        """
        Firma un documento in formato CAdES-BES (.p7m) usando la chiave in-device.

        La chiave privata NON lascia il token — la firma crittografica avviene
        interamente all'interno del dispositivo (CKM_SHA256_RSA_PKCS).

        Args:
            documento: Contenuto del documento da firmare.
            detached:  True = firma detached (envelope .p7m); False = firma enveloped.

        Returns:
            Busta PKCS#7 DER con firma CAdES-BES.
        """
        from pkcs11 import Attribute, ObjectClass, Mechanism

        sess = self._get_session()
        cert = self._get_cert()

        # 1. Recupera la chiave privata dal token
        priv_keys = list(sess.get_objects({Attribute.CLASS: ObjectClass.PRIVATE_KEY}))
        if not priv_keys:
            raise RuntimeError(
                "Nessuna chiave privata nel token. "
                "Verificare che il certificato di firma sia presente."
            )
        priv_key = priv_keys[0]

        # 2. Calcola il message-digest del documento (SHA-256)
        doc_digest = hashlib.sha256(documento).digest()

        # 3. Costruisce i SignedAttributes (content-type + message-digest)
        signed_attrs_der = self._build_signed_attrs(doc_digest)

        # 4. Firma i SignedAttributes nel token (SHA256_RSA_PKCS hasha internamente)
        #    La chiave privata non lascia MAI il dispositivo.
        try:
            mech = Mechanism.SHA256_RSA_PKCS
        except AttributeError:
            # Fallback: valore CKM numerico
            from pkcs11 import Mechanism as _M
            mech = getattr(_M, "SHA256_RSA_PKCS", 0x40)

        signature_bytes = bytes(priv_key.sign(signed_attrs_der, mechanism=mech))
        logger.debug("Firma PKCS#11 completata: %d byte", len(signature_bytes))

        # 5. Costruisce la busta PKCS#7 CAdES-BES
        return self._build_pkcs7(documento, doc_digest, signed_attrs_der,
                                  signature_bytes, detached)

    def _build_signed_attrs(self, doc_digest: bytes) -> bytes:
        """
        Costruisce i SignedAttributes DER (tag SET 0x31) per la firma CAdES-BES.

        Struttura (RFC 5652 §5.3 + ETSI EN 319 122):
          SignedAttributes ::= SET SIZE (1..MAX) OF Attribute
            Attribute 1: content-type = data (1.2.840.113549.1.9.3)
            Attribute 2: message-digest = SHA-256(documento) (1.2.840.113549.1.9.4)
        """
        from asn1crypto import cms, core

        signed_attrs = cms.CMSAttributes([
            cms.CMSAttribute({
                "type":   cms.CMSAttributeType("content_type"),
                "values": cms.SetOfContentType([cms.ContentType("data")]),
            }),
            cms.CMSAttribute({
                "type":   cms.CMSAttributeType("message_digest"),
                "values": cms.SetOfOctetString([core.OctetString(doc_digest)]),
            }),
        ])
        # .dump() restituisce bytes con tag SET (0x31) — corretto per la firma
        return signed_attrs.dump()

    def _build_pkcs7(
        self,
        documento:          bytes,
        doc_digest:         bytes,
        signed_attrs_der:   bytes,
        signature_bytes:    bytes,
        detached:           bool,
    ) -> bytes:
        """
        Costruisce la busta PKCS#7 SignedData DER conforme a RFC 5652 e CAdES-BES.
        """
        return _build_cades_bes(
            documento=documento,
            signature_bytes=signature_bytes,
            cert_der=self._cert_der,
            signed_attrs_der=signed_attrs_der,
            detached=detached,
        )

    # ── salva documento firmato (interfaccia FirmaDigitale) ─────────────────

    def salva_documento_firmato(
        self,
        documento: bytes,
        output_path: str,
        formato: str = "cades",
    ) -> str:
        """
        Firma e salva un documento (interfaccia compatibile con FirmaDigitale).

        Args:
            documento:   Contenuto del documento da firmare.
            output_path: Percorso di output (viene aggiunto .p7m se non presente).
            formato:     Sempre 'cades' per PKCS#11 (PAdES non supportato).

        Returns:
            Percorso al file firmato.
        """
        if formato != "cades":
            raise ValueError(
                "FirmaPKCS#11 supporta solo formato 'cades' (.p7m). "
                "Per PAdES usare FirmaDigitale con file P12/PEM."
            )
        firmato = self.firma_cades(documento)
        out = output_path if output_path.endswith(".p7m") else output_path + ".p7m"
        with open(out, "wb") as fh:
            fh.write(firmato)
        logger.info("Documento firmato salvato: %s (%d byte)", out, len(firmato))
        return out

    # ── context manager ──────────────────────────────────────────────────────

    def chiudi(self) -> None:
        """Chiude la sessione PKCS#11 e libera le risorse."""
        if self._session is not None:
            try:
                self._session.close()
            except Exception:
                pass
            self._session = None
            logger.debug("Sessione PKCS#11 chiusa.")

    def __enter__(self) -> "FirmaPKCS11":
        return self

    def __exit__(self, *args) -> None:
        self.chiudi()

    # ── factory da config ────────────────────────────────────────────────────

    @classmethod
    def da_config(cls, cfg, pin: Optional[str] = None) -> "FirmaPKCS11":
        """
        Crea FirmaPKCS11 dalla ConfigFirma.

        Args:
            cfg:  ConfigFirma con campi pkcs11_library, pkcs11_slot, pkcs11_label.
            pin:  PIN del token. Se None, viene letto da cfg.pkcs11_pin
                  (non raccomandato: preferire pin passato a runtime dalla UI).
        """
        lib = getattr(cfg, "pkcs11_library", "") or libreria_disponibile()
        if not lib:
            raise FileNotFoundError(
                "Libreria PKCS#11 non trovata. "
                "Installare opensc (apt install opensc) oppure impostare "
                "PCT_PKCS11_LIBRARY nel pannello Impostazioni → Firma Digitale."
            )
        slot_raw = getattr(cfg, "pkcs11_slot", "")
        slot = int(slot_raw) if str(slot_raw).strip().isdigit() else None
        _pin = pin or getattr(cfg, "pkcs11_pin", "") or ""
        return cls(
            library_path=lib,
            slot_id=slot,
            pin=_pin,
            label=getattr(cfg, "pkcs11_label", "") or None,
        )
