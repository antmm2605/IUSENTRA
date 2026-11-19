from types import SimpleNamespace

from pct.registro_letture import Oggetto, RegistroLetture
from pct.fascicolo_lettura.depositi import depositi
from web.services.correlazioni_ricevute_archivio import (
    _reinvio_autocertificazione,
    depositi_da_archivio,
    registra_ricevute,
)


def test_riusa_busta_e_catena_certificata_senza_riscrivere_il_deposito(tmp_path, monkeypatch):
    deposito = SimpleNamespace(id="D1", id_deposito_esterno="12345", stato="ACCETTATO_CANCELLERIA")
    fascicolo = SimpleNamespace(id="F1", numero_rg="002848", anno_rg="2026", depositi_pct=[deposito])
    comune = {"collegata": True, "event_type": "pct_deposito"}
    ancora = {
        **comune, "id": "finale", "mime_sha256": "a" * 64,
        "archive_receipt_reference": {"fascicolo_id": "F1", "deposito_id": "D1", "idbusta": "12345", "strategy": "idbusta_finale"},
        "deposit_lifecycle": {
            "current_stage": {"id": "accettazione_deposito"},
            "correlation": {"idbusta": "12345", "source_message_id": "&lt;id@test.example&gt;"},
            "receipt": {"outcome_code": 2, "numero_ruolo_certificato": "2848/2026", "occurred_at": "2026-09-30T08:41:20+02:00"},
        },
    }
    consegna = {
        **comune, "id": "consegna", "mime_sha256": "b" * 64,
        "archive_receipt_reference": {
            "fascicolo_id": "F1", "deposito_id": "D1", "strategy": "identificativo_xml_esito_ministeriale",
            "anchor_message_id": "finale", "provider_message_id": "id@test.example",
            "anchor_mime_sha256": ancora["mime_sha256"], "mime_sha256": "b" * 64,
        },
        "deposit_lifecycle": {"current_stage": {"id": "consegna_pec"}, "receipt": {"occurred_at": "29/09/2026 16:51:52T16:51:52"}},
    }
    non_correlata = {**consegna, "id": "estranea", "mime_sha256": "c" * 64}
    messaggi = [consegna, ancora, non_correlata]
    registro = RegistroLetture(tmp_path / "letture.sqlite")
    registro.registra_inventario("studio", "F1", [
        Oggetto(tipo="pec", oggetto_id=m["id"], sha256=m["mime_sha256"]) for m in messaggi
    ])
    assert registra_ricevute(fascicolo, registro, "studio", messaggi) == 2
    assert registra_ricevute(fascicolo, registro, "studio", messaggi) == 0
    monkeypatch.setattr("web.services.registro_letture_runtime.registro_corrente", lambda: registro)
    monkeypatch.setattr("web.services.registro_letture_runtime.tenant_corrente", lambda: "studio")
    copia, = depositi_da_archivio(fascicolo)
    assert copia.fonti_ricevute == {"consegna": "consegna", "cancelleria": "finale"}
    assert copia.consegne_archivio == (("2026-09-29T14:51:52+00:00", "consegna"),)
    assert copia.data_accettazione == "2026-09-30T06:41:20+00:00"
    assert not hasattr(deposito, "fonti_ricevute")


def test_reinvio_documentato_non_diventa_una_seconda_azione_di_deposito():
    richiesta = {
        "id": "richiesta", "collegata": True, "mime_sha256": "a" * 64,
        "received_at": "2026-06-10T09:39:00+02:00",
        "eventi": [{"fonte_evento": "Comunicazione.xml", "richiesta_autocertificazione_cu": True}],
    }
    comune = {"document_name": "AUTOCERTIFICAZIONE_DELLA_SITUAZIONE_REDDITUALE"}
    rifiuto = {"id": "rifiuto", "deposit_lifecycle": {
        "current_stage": {"id": "rifiuto_deposito"},
        "receipt": {**comune, "occurred_at": "2026-06-10T12:37:00+02:00",
                    "esito_ministeriale": {"codice_esito": -1},
                    "description": "Indicare l'ultima dichiarazione dei redditi"},
    }}
    accettazione = {"id": "accettata", "mime_sha256": "b" * 64, "deposit_lifecycle": {
        "current_stage": {"id": "accettazione_deposito"},
        "receipt": {**comune, "occurred_at": "2026-06-11T11:01:00+02:00",
                    "esito_ministeriale": {"codice_esito": 2}},
    }}
    consegna = {"id": "consegna", "mime_sha256": "c" * 64,
                "deposit_lifecycle": {"current_stage": {"id": "consegna_pec"}},
                "archive_receipt_reference": {"strategy": "identificativo_xml_esito_ministeriale",
                                              "anchor_message_id": "accettata",
                                              "receipt_at": "2026-06-10T16:31:00+02:00"}}
    associazioni = {"rifiuto": ("D1", "001"), "accettata": ("D2", "002"), "consegna": ("D2", "002")}
    fonti = [richiesta, rifiuto, accettazione]
    assert not _reinvio_autocertificazione(fonti, associazioni)
    prova = _reinvio_autocertificazione([*fonti, consegna], associazioni)["rifiuto"]
    assert prova["nuova_busta"] == "002"
    assert set(prova["fonti"]) == {"richiesta", "accettata", "consegna"}
    voce = {"stato": "RIFIUTATO_CANCELLERIA", "id": "D1"}
    assert depositi([voce])["falliti"]
    esito = depositi([{**voce, "reinvio_accettato": prova}])
    assert not esito["falliti"]
    assert esito["tutti"][0]["stato"] == "RIFIUTATO_CANCELLERIA"
    assert esito["tutti"][0]["attesa"].endswith("busta 002")
    assert not _reinvio_autocertificazione([*fonti, consegna, {**richiesta, "id": "altra"}], associazioni)
