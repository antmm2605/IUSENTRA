"""Verifica visiva 02/11/2026 (area Fascicoli): copertina, export, etichette in italiano."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.fascicoli import StatoFascicolo, TipoFascicolo
from web.bootstrap.export_routes import _enum_export, _stato_export
from web.services.fascicolo_copertina import contesto_copertina
from web.services.react_fascicoli_bridge import (
    _portal_source_label,
    _portal_sync_label,
    _source_label_for_document,
)


def _fascicolo(**valori):
    base = {"stato": StatoFascicolo.IN_CORSO, "tipo": TipoFascicolo.LAVORO, "avvocato_referente": "", "data_prossima_udienza": ""}
    base.update(valori)
    return SimpleNamespace(**base)


def test_copertina_stato_tipo_e_titolare_in_italiano():
    contesto = contesto_copertina(_fascicolo(), "Avv. Mario Rossi", oggi=date(2026, 11, 2))
    assert contesto["stato_label"] == "In corso"
    assert contesto["tipo_label"] == "Lavoro"
    # Senza referente registrato vale l'avvocato titolare dello studio, come in Anagrafica.
    assert contesto["titolare"] == "Avv. Mario Rossi"
    assert contesto_copertina(_fascicolo(avvocato_referente="Avv. Bianchi"), "Avv. Mario Rossi")["titolare"] == "Avv. Bianchi"


def test_copertina_udienza_passata_non_e_prossima():
    oggi = date(2026, 11, 2)
    assert contesto_copertina(_fascicolo(data_prossima_udienza="2026-10-07"), oggi=oggi)["udienza_label"] == "Ultima udienza"
    assert contesto_copertina(_fascicolo(data_prossima_udienza="07/10/2026"), oggi=oggi)["udienza_label"] == "Ultima udienza"
    assert contesto_copertina(_fascicolo(data_prossima_udienza="2026-11-02"), oggi=oggi)["udienza_label"] == "Prossima udienza"
    assert contesto_copertina(_fascicolo(data_prossima_udienza="2027-01-13T11:00:00+01:00"), oggi=oggi)["udienza_label"] == "Prossima udienza"


def test_export_stato_da_archiviare_non_genera_errore():
    # «Da archiviare» è lo stato derivato dell'elenco: DEFINITO pronto per l'archivio.
    assert _stato_export("DA_ARCHIVIARE") == (StatoFascicolo.DEFINITO, True)
    assert _stato_export("IN_CORSO") == (StatoFascicolo.IN_CORSO, False)
    assert _stato_export("") == (None, False)
    assert _stato_export("SCONOSCIUTO") == (None, False)
    assert _enum_export(TipoFascicolo, "lavoro") is TipoFascicolo.LAVORO
    assert _enum_export(TipoFascicolo, "TUTTI") is None


def test_provenienza_documento_mai_chiave_tecnica():
    for chiave, attesa in (
        ("CARICAMENTO_STUDIO", "Studio"),
        ("PEC_CANCELLERIA", "PEC di cancelleria"),
        ("APERTURA_FASCICOLO_VELOCE", "Apertura del fascicolo"),
        ("NUOVA_FONTE_IGNOTA", "Nuova fonte ignota"),
        ("", "Studio"),
    ):
        etichetta = _source_label_for_document(SimpleNamespace(fonte_documento=chiave, classificazione_portale=""))
        assert etichetta == attesa
        assert "_" not in etichetta


def test_fonte_e_allineamento_portale_in_italiano():
    assert _portal_source_label("IMPORT_PRATICHE") == "Importazione pratiche"
    assert _portal_source_label("PST") == "Portale Servizi Telematici"
    assert _portal_source_label("") == ""
    assert _portal_sync_label("IMPORTATO") == "importato dal portale"
    assert _portal_sync_label("") == "solo dati dello studio"
    assert "_" not in _portal_sync_label("DA_VERIFICARE")


def test_opzioni_attivita_in_italiano():
    from pct.fascicoli import EsitoAttivita, TipoAttivita
    from web.services.react_fascicoli_bridge import _option

    etichette = {_option(item)["value"]: _option(item)["label"] for item in [*TipoAttivita, *EsitoAttivita]}
    assert etichette["ISCRIZIONE_A_RUOLO"] == "Iscrizione a ruolo"
    assert etichette["CTU"] == "CTU"
    assert etichette["IN_ATTESA"] == "In attesa"
    assert all("_" not in label for label in etichette.values())


def test_note_attivita_senza_identificativi_tecnici():
    from web.services.react_fascicoli_bridge import _activity_notes_for_user

    nota = _activity_notes_for_user(
        "Fonte: documento indicizzato. Scadenza/agenda collegate: B805D75C Udienza riunita alle 10:45. "
        "Operazione eventi-unici-5b7701463f9a4641a47c25d9e7760581. Prove: fat_377d197e9bcd, fat_98c3e919"
    )
    assert "B805D75C" not in nota and "eventi-unici" not in nota and "fat_" not in nota
    assert "Udienza riunita alle 10:45." in nota


def test_registro_operativo_senza_codici_di_profilo_e_slot():
    from web.services.react_fascicoli_bridge import _operational_audit_text

    assert _operational_audit_text("Profilo PROC_LAV_RETRIB_001 applicato.") == "Profilo procedurale applicato."
    assert "DOCUMENTI_RETRIBUTIVI" not in _operational_audit_text("Slot DOCUMENTI_RETRIBUTIVI collegato al documento 9B74.")
    assert _operational_audit_text("Documento consultato: Ricorso.pdf") == "Documento consultato: Ricorso.pdf"
