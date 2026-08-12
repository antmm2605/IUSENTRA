from __future__ import annotations

from types import SimpleNamespace

from pct import deposito_compatibilita


def test_indice_busta_interno_al_dati_atto_e_conforme(monkeypatch):
    monkeypatch.setattr(
        deposito_compatibilita,
        "_file_info",
        lambda _path: {
            "exists": True,
            "name": "Atto.enc",
            "size_bytes": 128,
            "sha256": "A" * 64,
            "cms_enveloped_data": True,
        },
    )
    audit = {
        "uses_real_encryption": True,
        "atto_enc_cms_valid": True,
        "required_encryption_algorithm": "AES256",
        "transport_mode": "atto_enc_da_atto_msg_cifrato_aes256",
        "indice_busta_xml_generated": True,
        "dati_atto_indice_busta_interno": True,
        "atto_msg_indice_busta_valid": True,
        "busta_verifica_valida": True,
        "dati_atto_signed": True,
        "indice_documenti_generated": True,
        "atto_enc_sha256": "A" * 64,
    }

    report = deposito_compatibilita.build_deposito_compatibility_report(
        id_deposito="PROVA001",
        pec_dest="tribunale.vicenza@civile.ptel.giustiziacert.it",
        oggetto_pec="DEPOSITO TELEMATICO - RICORSO - Tribunale di Vicenza",
        corpo_pec="Atto.enc Ricorso.pdf.p7m",
        documenti_busta=[
            "DatiAtto.xml.p7m",
            "Ricorso.pdf.p7m",
            "IndiceDocumentiDepositati.PDF",
        ],
        attachment_path="Atto.enc",
        busta_audit=audit,
        validation=SimpleNamespace(to_dict=lambda: {}),
    )

    indice = next(item for item in report["checks"] if item["code"] == "INDICE_BUSTA_XML")
    assert indice["status"] == "ok"
    assert indice["detail"] == "IndiceBusta ministeriale incluso nel DatiAtto.xml.p7m."
    assert report["percentuale"] == 100
    assert report["blockers"] == 0
