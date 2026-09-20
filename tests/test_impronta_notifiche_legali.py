"""Il presidio notifiche non deve rifare il giro se non e' cambiato nulla."""

from __future__ import annotations

from pathlib import Path

from pct import impronta_notifiche_legali as impronta


def _piena(**cambi: str) -> impronta.Impronta:
    base = {
        "pec_notifiche": "pec|3|2026-09-20T07:10:00Z|PRE-9",
        "pec_senza_fascicolo": "pec_orfane|1|2026-09-20T07:10:00Z|MSG-4",
        "fascicoli": "fascicoli|309|2026-09-19T18:00:00Z|482113|12",
        "destinatari": "destinatari|4",
    }
    base.update(cambi)
    return impronta.Impronta(**base)


def test_due_giri_senza_novita_hanno_la_stessa_chiave():
    assert _piena().chiave() == _piena().chiave()
    assert impronta.si_puo_fermare(_piena(), _piena()) is True


def test_una_pec_di_notifica_nuova_risveglia_il_presidio():
    dopo = _piena(pec_notifiche="pec|4|2026-09-20T09:25:00Z|PRE-10")
    assert impronta.si_puo_fermare(dopo, _piena()) is False


def test_un_fascicolo_toccato_risveglia_il_presidio_anche_senza_pec():
    # L'avvocato archivia un fascicolo: la relata cambia, nessuna PEC e' arrivata.
    dopo = _piena(fascicoli="fascicoli|309|2026-09-20T10:00:00Z|482113|13")
    assert impronta.si_puo_fermare(dopo, _piena()) is False


def test_un_documento_allegato_risveglia_il_presidio():
    # Cambia solo il peso di documenti_json: nessun conteggio, nessuna data.
    dopo = _piena(fascicoli="fascicoli|309|2026-09-19T18:00:00Z|491002|12")
    assert impronta.si_puo_fermare(dopo, _piena()) is False


def test_un_destinatario_in_piu_risveglia_il_presidio():
    dopo = _piena(destinatari="destinatari|5")
    assert impronta.si_puo_fermare(dopo, _piena()) is False


def test_una_sorgente_muta_non_ferma_mai_il_presidio():
    """Se una sorgente non si e' lasciata interrogare si lavora lo stesso:
    meglio un giro di troppo che una notifica legale che non arriva."""

    cieca = _piena(fascicoli="")
    assert cieca.completa() is False
    assert impronta.si_puo_fermare(cieca, cieca) is False
    assert impronta.si_puo_fermare(cieca, _piena()) is False
    assert impronta.si_puo_fermare(_piena(), cieca) is False


def test_impronta_salvata_e_riletta(tmp_path: Path):
    assert impronta.scrivi_impronta(tmp_path, _piena(), esito={"scanned": 309, "items": 7}) is True
    riletta, dati = impronta.leggi_impronta(tmp_path)

    assert riletta.chiave() == _piena().chiave()
    assert dati["ultimo_giro"]["scanned"] == 309


def test_versione_sconosciuta_non_viene_creduta(tmp_path: Path):
    percorso = impronta.percorso_impronta(tmp_path)
    percorso.write_text('{"impronta": {"versione": "vecchia", "fascicoli": "x"}}', encoding="utf-8")

    riletta, _ = impronta.leggi_impronta(tmp_path)
    assert riletta.completa() is False
    assert impronta.si_puo_fermare(_piena(), riletta) is False


def test_riattiva_presidio_toglie_il_semaforo(tmp_path: Path):
    impronta.scrivi_impronta(tmp_path, _piena())
    impronta.riattiva_presidio(tmp_path)

    riletta, _ = impronta.leggi_impronta(tmp_path)
    assert impronta.si_puo_fermare(_piena(), riletta) is False


def test_esito_fermo_dice_perche_e_da_quando():
    impronta.scrivi_impronta
    esito = impronta.esito_fermo(
        _piena(),
        {"aggiornato": "2026-09-20T07:10:00Z", "ultimo_giro": {"scanned": 309, "items": 7, "recipients": 4}},
    )

    assert esito["ok"] is True
    assert esito["stato"] == "fermo"
    assert "nessuna PEC" in esito["motivo"]
    # Uno zero senza spiegazione sarebbe indistinguibile da un guasto.
    assert esito["ultimo_giro_utile"]["scanned"] == 309
    assert esito["ultimo_giro_utile"]["quando"] == "2026-09-20T07:10:00Z"
