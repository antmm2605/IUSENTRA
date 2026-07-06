from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.fascicolo_document_presidio import (
    analyze_fascicolo_document_texts,
    duplicate_practice_groups,
)


def _fascicolo(**overrides):
    data = {
        "id": "F1",
        "nome_cliente": "Spagnolo Sara",
        "numero_rg": "3950",
        "anno_rg": "2026",
        "rg_completo": "RG 3950/2026",
        "titolo": "Spagnolo Sara c. MIM",
        "oggetto": "Retribuzione",
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def test_presidio_127_ter_estende_termine_note_notifica_e_costituzione():
    fascicolo = _fascicolo(
        id="F1733",
        nome_cliente="Punturiero Rosa",
        numero_rg="1733",
        anno_rg="2026",
        rg_completo="RG 1733/2026",
        titolo="Punturiero Rosa c. MIM",
    )
    text = """
    TRIBUNALE DI PALMI - N. R.G. 1733/2026.
    Il Giudice, ai sensi dell'art. 127 ter c.p.c. in sostituzione dell'udienza,
    FISSA termine del 10/09/2026 per il deposito di note scritte.
    ONERA parte ricorrente della notificazione del ricorso e del presente decreto
    entro e non oltre 30 giorni prima dell'udienza fissata.
    ASSEGNA al resistente termine sino a 10 giorni prima della scadenza
    per la costituzione in giudizio.
    Punturiero Rosa.
    """

    payload = analyze_fascicolo_document_texts(
        fascicolo,
        {"doc-palmi": text},
        {"doc-palmi": {"filename": "Decreto fissazione udienza (1).PDF"}},
        today=date(2026, 7, 6),
    )

    by_type = {item["type"]: item for item in payload["actions"]}
    assert by_type["note_127_ter"]["dateIso"] == "2026-09-10"
    assert by_type["note_127_ter"]["peremptory"] is True
    assert by_type["notifica_ricorso_decreto"]["dateIso"] == "2026-08-11"
    assert by_type["costituzione_resistente"]["dateIso"] == "2026-08-31"
    assert payload["nextAction"]["type"] == "notifica_ricorso_decreto"


def test_presidio_127_bis_estende_udienza_audiovisiva_e_richiesta_presenza():
    fascicolo = _fascicolo()
    text = """
    TRIBUNALE ORDINARIO DI TORINO - Sezione Lavoro - RGL n. 3950/2026.
    Visti gli artt. 127 bis e 415 c.p.c. fissa udienza del 13/01/2027 ore 11:00
    con collegamento audiovisivo nella stanza virtuale del giudice.
    La parte convenuta dovra' costituirsi almeno 10 giorni prima dell'udienza.
    La parte ricorrente potra' chiedere la trattazione in presenza entro 5 giorni dalla comunicazione.
    Spagnolo Sara c. MIM.
    """

    payload = analyze_fascicolo_document_texts(
        fascicolo,
        {"doc-torino": text},
        {"doc-torino": {"filename": "Decreto fissazione udienza.PDF"}},
        today=date(2026, 7, 6),
    )

    by_type = {item["type"]: item for item in payload["actions"]}
    assert by_type["udienza_127_bis"]["dateIso"] == "2027-01-13"
    assert by_type["udienza_127_bis"]["time"] == "11:00"
    assert by_type["costituzione_convenuto"]["dateIso"] == "2027-01-03"
    assert by_type["richiesta_presenza_127_bis"]["requiresCommunicationDate"] is True


def test_duplicate_practice_groups_usa_cliente_e_rg_normalizzati():
    rows = [
        _fascicolo(id="A", nome_cliente="Spagnolo Sara", numero_rg="3950", anno_rg="2026"),
        _fascicolo(id="B", nome_cliente="spagnolo  sara", numero_rg="3950", anno_rg="2026"),
        _fascicolo(id="C", nome_cliente="Spagnolo Sara", numero_rg="3951", anno_rg="2026"),
    ]

    groups = duplicate_practice_groups(rows)

    assert len(groups) == 1
    assert groups[0]["count"] == 2
    assert groups[0]["ids"] == ["A", "B"]


def test_presidio_documenti_non_espone_id_tecnici_come_fonte():
    payload = analyze_fascicolo_document_texts(
        _fascicolo(),
        {
            "pst:JPW_SIGP:123": (
                "TRIBUNALE DI TORINO RG 3950/2026. "
                "Visti gli artt. 127 bis e 415 c.p.c. fissa udienza del 13/01/2027 ore 11:00."
            )
        },
        {"pst:JPW_SIGP:123": {}},
        today=date(2026, 7, 6),
    )

    assert payload["actions"]
    assert payload["actions"][0]["source"] == "Documento indicizzato del fascicolo"
