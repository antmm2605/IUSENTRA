"""Il presidio non chiede di verificare il collegamento di un'udienza da remoto già tenuta (collaudo 08/11/2026).

Fascicolo Alessi (RG 2539/2025 Velletri): l'udienza del 07/10/2026 si è tenuta e la sentenza è dello stesso giorno, ma il
Presidio del fascicolo proponeva ancora «Verificare link audiovisivo e comunicazione dell'udienza».
"""

from __future__ import annotations

from datetime import date

import pct.fascicolo_operational_presidio as presidio


def _azioni(monkeypatch, *date_udienza: str):
    monkeypatch.setattr(presidio, "oggi_roma", lambda: date(2026, 11, 8))
    documenti = {"actions": [{"type": "udienza_127_bis", "dateIso": giorno} for giorno in date_udienza]}
    settore = presidio._pec_sector(documenti, [], [], fid="F1")
    return [azione for azione in settore.get("actions") or [] if azione.get("id", "").endswith("link-udienza-127-bis")
            or "link audiovisivo" in str(azione.get("title"))]


def test_udienza_remota_gia_tenuta_non_genera_verifiche(monkeypatch):
    assert _azioni(monkeypatch, "2026-10-07") == []


def test_udienza_remota_futura_resta_da_verificare_con_la_data(monkeypatch):
    azioni = _azioni(monkeypatch, "2026-10-07", "2027-01-20")
    assert len(azioni) == 1 and "20/01/2027" in azioni[0]["reason"]
