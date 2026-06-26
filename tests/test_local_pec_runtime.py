from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.deposito_pec_contract import oggetto_deposito_pec_conforme
from pct.pst_cifratura import carica_certificato_cifratura, cifra_atto_msg_aes256, crea_certificato_cifratura_test
from web.services.local_pec_runtime import build_local_pec_payload


def _pec_cfg():
    return SimpleNamespace(
        indirizzo="studio@example.pec.it",
        smtp_host="smtp.example.pec.it",
        smtp_port=465,
        use_ssl=True,
        use_tls=False,
    )


def _atto_enc_cms_payload(tmp_path: Path) -> bytes:
    info = crea_certificato_cifratura_test(tmp_path / "certificato-runtime-test.cer")
    cert = carica_certificato_cifratura(info.path)
    return cifra_atto_msg_aes256(b"Atto.msg test con IndiceBusta.xml", cert)


def _verified_audit(payload: bytes) -> dict[str, object]:
    return {
        "uses_real_encryption": True,
        "atto_enc_cms_valid": True,
        "dati_atto_signed": True,
        "dati_atto_filename": "DatiAtto.xml.p7m",
        "indice_busta_generated": True,
        "atto_msg_indice_busta_valid": True,
        "busta_verifica_valida": True,
        "atto_enc_sha256": hashlib.sha256(payload).hexdigest().upper(),
    }


def test_oggetto_deposito_pec_rispetta_sintassi_ministeriale():
    assert oggetto_deposito_pec_conforme("DEPOSITO Ricorso A vs. B")
    assert oggetto_deposito_pec_conforme("DEPOSITO TELEMATICO - RICORSO - RG 123/2026")
    assert not oggetto_deposito_pec_conforme("DEPOSITO")
    assert not oggetto_deposito_pec_conforme("DEPOSITO   ")
    assert not oggetto_deposito_pec_conforme("RICORSO - deposito")


def test_payload_local_pec_rifiuta_atto_enc_non_cms(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    atto_enc.write_bytes(b"ATTO-ENC-NON-MINISTERIALE")

    with pytest.raises(ValueError, match="CMS EnvelopedData ministeriale"):
        build_local_pec_payload(
            pec_cfg=_pec_cfg(),
            destinatario="tribunale@example.pec.it",
            oggetto="DEPOSITO TELEMATICO - RICORSO",
            corpo="Deposito",
            attachment_path=str(atto_enc),
            attachment_name="Atto.enc",
        )


def test_payload_local_pec_rifiuta_oggetto_non_ministeriale_con_atto_enc(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    payload_bytes = _atto_enc_cms_payload(tmp_path)
    atto_enc.write_bytes(payload_bytes)

    with pytest.raises(ValueError, match="deve iniziare con 'DEPOSITO'"):
        build_local_pec_payload(
            pec_cfg=_pec_cfg(),
            destinatario="tribunale@example.pec.it",
            oggetto="RICORSO - Tribunale",
            corpo="Deposito",
            attachment_path=str(atto_enc),
            attachment_name="Atto.enc",
            busta_audit=_verified_audit(payload_bytes),
        )


def test_payload_local_pec_include_atto_enc_cms_base64(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    payload_bytes = _atto_enc_cms_payload(tmp_path)
    atto_enc.write_bytes(payload_bytes)

    payload = build_local_pec_payload(
        pec_cfg=_pec_cfg(),
        destinatario="tribunale@example.pec.it",
        oggetto="DEPOSITO TELEMATICO - RICORSO",
        corpo="Deposito",
        attachment_path=str(atto_enc),
        attachment_name="Atto.enc",
        busta_audit=_verified_audit(payload_bytes),
    )

    attachment = payload["payload"]["attachments"][0]
    assert attachment["filename"] == "Atto.enc"
    assert attachment["ministerial_busta_verified"] is True
    assert attachment["sha256"] == hashlib.sha256(payload_bytes).hexdigest().upper()
    assert base64.b64decode(attachment["content_base64"], validate=True) == atto_enc.read_bytes()


def test_payload_local_pec_rifiuta_atto_enc_cms_senza_audit_busta(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    atto_enc.write_bytes(_atto_enc_cms_payload(tmp_path))

    with pytest.raises(ValueError, match="verifica ministeriale completa"):
        build_local_pec_payload(
            pec_cfg=_pec_cfg(),
            destinatario="tribunale@example.pec.it",
            oggetto="DEPOSITO TELEMATICO - RICORSO",
            corpo="Deposito",
            attachment_path=str(atto_enc),
            attachment_name="Atto.enc",
        )


def test_payload_local_pec_usa_username_smtp_separato_dal_mittente(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    payload_bytes = _atto_enc_cms_payload(tmp_path)
    atto_enc.write_bytes(payload_bytes)
    cfg = _pec_cfg()
    cfg.username = "utente-login-pec"

    payload = build_local_pec_payload(
        pec_cfg=cfg,
        destinatario="tribunale@example.pec.it",
        oggetto="DEPOSITO TELEMATICO - RICORSO",
        corpo="Deposito",
        attachment_path=str(atto_enc),
        attachment_name="Atto.enc",
        busta_audit=_verified_audit(payload_bytes),
    )

    assert payload["payload"]["from"] == "studio@example.pec.it"
    assert payload["payload"]["indirizzo"] == "studio@example.pec.it"
    assert payload["payload"]["username"] == "utente-login-pec"
