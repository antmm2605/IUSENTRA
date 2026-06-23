"""Helpers for PCT deposit metadata signature handoff."""
from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

from pct.busta import (
    DATI_ATTO_FILENAME,
    DATI_ATTO_FIRMATO_FILENAME,
    INDICE_BUSTA_FILENAME,
    INDICE_DOCUMENTI_FILENAME,
)
from pct.firma import busta_cades_valida, estrai_contenuto_cades
from web.services.local_pec_runtime import LOCAL_SIGNER_BASE_URL


def documenti_busta_nomi(atto_path: str, allegati_busta: list[Any]) -> list[str]:
    """Return the technical and operational filenames expected inside Atto.msg."""
    nomi = [INDICE_BUSTA_FILENAME, DATI_ATTO_FIRMATO_FILENAME, Path(atto_path).name]
    nomi.extend(Path(str(getattr(allegato, "percorso", ""))).name for allegato in allegati_busta)
    nomi.append(INDICE_DOCUMENTI_FILENAME)
    return [nome for nome in nomi if nome]


def dati_atto_signature_gate(
    form: Any,
    busta: Any,
    *,
    id_deposito: str,
    timestamp: str,
    pec_dest: str,
    tipo_atto: str,
    oggetto_pec: str,
    corpo_pec: str,
    documenti_busta: list[str],
) -> tuple[bytes | None, Any | None]:
    """Validate signed DatiAtto.xml or return a JSON payload and HTTP status."""
    dati_atto_xml = busta.crea_dati_atto_xml_per_firma()
    dati_atto_sha256 = hashlib.sha256(dati_atto_xml).hexdigest().upper()
    dati_atto_firmato_b64 = str(form.get("dati_atto_firmato_b64", "") or "").strip()
    if dati_atto_firmato_b64:
        try:
            dati_atto_firmato = base64.b64decode(dati_atto_firmato_b64, validate=True)
        except Exception:
            return None, {"ok": False, "errore": "DatiAtto.xml.p7m non valido: la firma ricevuta non è base64 corretto.", "_status": 400}
        if not busta_cades_valida(dati_atto_firmato):
            return None, {
                "ok": False,
                "errore": "DatiAtto.xml.p7m non contiene una firma CAdES valida. Ripeti la firma dal PC locale.",
                "_status": 400,
            }
        expected_hash = str(form.get("dati_atto_sha256", "") or "").strip().upper()
        if expected_hash and expected_hash != dati_atto_sha256:
            return None, {
                "ok": False,
                "errore": (
                    "DatiAtto.xml.p7m non corrisponde alla busta corrente: "
                    "la firma è stata prodotta su metadati diversi. Ripeti la firma e l'invio."
                ),
                "_status": 400,
            }
        if estrai_contenuto_cades(dati_atto_firmato) != dati_atto_xml:
            return None, {
                "ok": False,
                "errore": (
                    "DatiAtto.xml.p7m non contiene il DatiAtto.xml generato per questa busta. "
                    "Ripeti la firma dal PC locale senza cambiare documenti o selezione."
                ),
                "_status": 400,
            }
        return dati_atto_firmato, None
    if form.get("local_pec_confirmed") == "1":
        return None, {
            "ok": False,
            "errore": "Conferma invio non accettata: DatiAtto.xml.p7m firmato non è stato ritrasmesso al server.",
            "_status": 400,
        }
    audit_firma = busta.audit_conformita_pst()
    return None, {
        "ok": False,
        "requires_local_signature": True,
        "package_ready": False,
        "id_deposito": id_deposito,
        "busta_id": busta.id_busta,
        "busta_timestamp": timestamp,
        "dati_atto_sha256": dati_atto_sha256,
        "pec_dest": pec_dest,
        "tipo_atto": tipo_atto,
        "timestamp": timestamp,
        "oggetto_pec": oggetto_pec,
        "corpo_pec": corpo_pec,
        "documenti_busta": documenti_busta,
        "busta_audit": audit_firma,
        "messaggio": (
            "DatiAtto.xml deve essere firmato digitalmente prima di creare Atto.enc. "
            "Inserisci il PIN: il software firmerà il metadato ministeriale e riprenderà la stessa fase."
        ),
        "next_actions": [
            "Firma DatiAtto.xml con Local Signer.",
            "Rigenera Atto.msg con IndiceBusta.xml e DatiAtto.xml.p7m.",
            "Cifra Atto.msg in Atto.enc AES256 prima della PEC reale.",
        ],
        "local_signature": {
            "endpoint": f"{LOCAL_SIGNER_BASE_URL}/firma",
            "filename": DATI_ATTO_FILENAME,
            "output_filename": DATI_ATTO_FIRMATO_FILENAME,
            "busta_id": busta.id_busta,
            "busta_timestamp": timestamp,
            "dati_atto_sha256": dati_atto_sha256,
            "requires_pin": True,
            "payload": {
                "documento": base64.b64encode(dati_atto_xml).decode("ascii"),
                "nome": DATI_ATTO_FILENAME,
                "visible_signature_mode": "nessuna",
                "visible_signature_datetime_mode": "nessuna",
            },
        },
        "_status": 200,
    }
