from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest

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


def test_payload_local_pec_include_atto_enc_cms_base64(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    atto_enc.write_bytes(_atto_enc_cms_payload(tmp_path))

    payload = build_local_pec_payload(
        pec_cfg=_pec_cfg(),
        destinatario="tribunale@example.pec.it",
        oggetto="DEPOSITO TELEMATICO - RICORSO",
        corpo="Deposito",
        attachment_path=str(atto_enc),
        attachment_name="Atto.enc",
    )

    attachment = payload["payload"]["attachments"][0]
    assert attachment["filename"] == "Atto.enc"
    assert base64.b64decode(attachment["content_base64"], validate=True) == atto_enc.read_bytes()


def test_payload_local_pec_usa_username_smtp_separato_dal_mittente(tmp_path):
    atto_enc = tmp_path / "Atto.enc"
    atto_enc.write_bytes(_atto_enc_cms_payload(tmp_path))
    cfg = _pec_cfg()
    cfg.username = "utente-login-pec"

    payload = build_local_pec_payload(
        pec_cfg=cfg,
        destinatario="tribunale@example.pec.it",
        oggetto="DEPOSITO TELEMATICO - RICORSO",
        corpo="Deposito",
        attachment_path=str(atto_enc),
        attachment_name="Atto.enc",
    )

    assert payload["payload"]["from"] == "studio@example.pec.it"
    assert payload["payload"]["indirizzo"] == "studio@example.pec.it"
    assert payload["payload"]["username"] == "utente-login-pec"
