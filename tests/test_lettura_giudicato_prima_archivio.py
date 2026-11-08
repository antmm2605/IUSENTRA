"""«Da archiviare» non vuol dire passata in giudicato (collaudo 08/11/2026, RG 2962/2023 Giudice di Pace di Palmi).

La sentenza del 04/05/2026 (pubblicata il 13/05/2026) accoglie l'opposizione: la Lettura diceva «nessun passaggio,
solo l'archiviazione» mentre la controparte può ancora appellare per sei mesi dalla pubblicazione (art. 327 c.p.c.).
"""

from __future__ import annotations

from datetime import date

from pct.fascicolo_lettura.prossimi_passi import stato_passi

SENTENZE = {"sentenze": [{"etichetta": "Sentenza", "data": "2026-05-04", "nome": "Atto_3217226.pdf"}]}


def test_da_archiviare_con_impugnazione_ancora_possibile():
    stato = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "civile"}, SENTENZE, date(2026, 11, 8))
    assert stato["attivi"] is False
    assert "art. 324 c.p.c." in stato["motivo"] and "art. 327 c.p.c." in stato["motivo"]
    # 04/05/2026 + sei mesi + 31 giorni di sospensione feriale = sabato 05/12/2026, prorogato a lunedì (art. 155 c.p.c.)
    assert "non prima del 07/12/2026" in stato["motivo"]


def test_lavoro_senza_sospensione_feriale():
    stato = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "lavoro"},
                        {"sentenze": [{"data": "2026-10-07"}]}, date(2026, 11, 8))
    assert "non prima del 07/04/2027" in stato["motivo"]


def test_termine_trascorso_o_senza_sentenza_resta_pronto_per_l_archivio():
    trascorso = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "civile"}, SENTENZE, date(2027, 1, 10))
    assert trascorso["motivo"].startswith("Fascicolo pronto per l'archivio")
    senza = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "civile"})
    assert senza["motivo"].startswith("Fascicolo pronto per l'archivio")
    amministrativo = stato_passi({"stato_codice": "DEFINITO", "da_archiviare": True, "tipo": "amministrativo"}, SENTENZE, date(2026, 11, 8))
    assert amministrativo["motivo"].startswith("Fascicolo pronto per l'archivio")


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
