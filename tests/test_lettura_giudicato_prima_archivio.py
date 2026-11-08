"""«Da archiviare» non vuol dire passata in giudicato (collaudo 08/11/2026, RG 2962/2023 Giudice di Pace di Palmi).

La sentenza decisa il 04/05/2026 e pubblicata il 13/05/2026 accoglie l'opposizione: la Lettura diceva «nessun passaggio,
solo l'archiviazione» mentre la controparte può ancora appellare per sei mesi dalla pubblicazione (art. 327 c.p.c.), che
è il deposito in cancelleria (art. 133 c.p.c.), non la data della decisione in calce.
"""

from __future__ import annotations

from datetime import date

from pct.fascicolo_lettura.prossimi_passi import stato_passi

# Decisa il 04/05/2026 («Così deciso…» in calce), pubblicata il 13/05/2026 («Sentenza n. 376/2026 pubbl. il 13/05/2026»).
SENTENZE = {"sentenze": [{"etichetta": "Sentenza", "data": "2026-05-04", "data_pubblicazione": "2026-05-13",
                          "nome": "Atto_3217226.pdf"}]}
CIVILE = {"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "civile"}


def test_termine_dalla_pubblicazione_non_dalla_decisione():
    """13/05/2026 + sei mesi = 13/11/2026, + 31 giorni di sospensione feriale = lunedì 14/12/2026 (artt. 133, 327 c.p.c.)."""
    stato = stato_passi(CIVILE, SENTENZE, date(2026, 11, 8))
    assert stato["attivi"] is False
    assert "art. 324 c.p.c." in stato["motivo"] and "art. 327 c.p.c." in stato["motivo"]
    assert "pubblicata il 13/05/2026" in stato["motivo"] and "fino al 14/12/2026" in stato["motivo"]
    assert "07/12/2026" not in stato["motivo"]


def test_motore_dei_termini_conferma_il_14_dicembre():
    from pct.termine_lungo_sentenza import scadenza_termine_lungo

    assert scadenza_termine_lungo(date(2026, 5, 13), lavoro=False)["deadline"] == "2026-12-14"
    assert scadenza_termine_lungo(date(2026, 10, 7), lavoro=True)["deadline"] == "2027-04-07"


def test_lavoro_senza_sospensione_feriale():
    stato = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "lavoro"},
                        {"sentenze": [{"data": "2026-10-07", "data_pubblicazione": "2026-10-07"}]}, date(2026, 11, 8))
    assert "fino al 07/04/2027" in stato["motivo"] and "senza sospensione feriale" in stato["motivo"]


def test_senza_pubblicazione_letta_si_chiede_di_verificarla_senza_inventare_date():
    stato = stato_passi(CIVILE, {"sentenze": [{"data": "2026-05-04"}]}, date(2026, 11, 8))
    assert "non è letta" in stato["motivo"] and "art. 133 c.p.c." in stato["motivo"]
    assert "fino al" not in stato["motivo"]


def test_termine_trascorso_o_senza_sentenza_resta_pronto_per_l_archivio():
    trascorso = stato_passi(CIVILE, SENTENZE, date(2027, 1, 10))
    assert trascorso["motivo"].startswith("Fascicolo pronto per l'archivio")
    senza = stato_passi(CIVILE)
    assert senza["motivo"].startswith("Fascicolo pronto per l'archivio")
    amministrativo = stato_passi({**CIVILE, "tipo": "amministrativo"}, SENTENZE, date(2026, 11, 8))
    assert amministrativo["motivo"].startswith("Fascicolo pronto per l'archivio")


def test_la_lettura_dei_documenti_legge_la_data_di_pubblicazione():
    from pct.fascicolo_lettura.documenti import _data_pubblicazione

    fatti = [
        {"categoria": "data", "campo": "provvedimento", "verifica": "verificata", "valore": "2026-05-13",
         "contesto": "Sentenza n. 376/2026 pubbl. il 13/05/2026 RG n. 2962/2023"},
        {"categoria": "data", "campo": "data_atto", "verifica": "verificata", "valore": "2026-05-04",
         "contesto": "Così deciso in PALMI il 04-05-2026"},
    ]
    assert _data_pubblicazione(fatti) == "2026-05-13"
    assert _data_pubblicazione(fatti[1:]) == ""


def test_eventi_del_registro_di_cancelleria_parlano_con_la_descrizione():
    """Collaudo 08/11/2026: la Lettura mostrava «Attività SDP — in attesa di esito», «LD», «J1»."""
    from pct.fascicolo_lettura.cronologia import cronologia

    attivita = [
        {"tipo": "ALTRO", "titolo": "SDP", "descrizione": "DEPOSITO MINUTA SENTENZA DEFINITIVA E PUBBLICAZIONE",
         "esito": "IN_ATTESA", "data": "2026-05-13", "id": "a1"},
        {"tipo": "UDIENZA", "titolo": "Udienza (importata da PolisWeb)", "descrizione": "", "esito": "IN_ATTESA",
         "data": "2024-02-27", "id": "a2"},
    ]
    eventi = {e["fonte_id"]: e for e in cronologia(attivita, [], [], [], [], date(2026, 11, 8))}
    assert eventi["a1"]["titolo"] == "DEPOSITO MINUTA SENTENZA DEFINITIVA E PUBBLICAZIONE"
    assert eventi["a1"]["esito"] == "" and "codice SDP" in eventi["a1"]["dettaglio"]
    assert eventi["a2"]["titolo"] == "Udienza (importata da PolisWeb)" and eventi["a2"]["esito"] == "in attesa di esito"
