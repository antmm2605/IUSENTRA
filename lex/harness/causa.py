"""Fase dei fatti dentro un fascicolo: il modello unico della causa (pct/ragionamento) come fonte certa.

Quando la domanda arriva da un fascicolo, l'harness non rilegge i fatti dal testo: prende dal modello della causa
rito, ufficio, ruolo del cliente, atti, udienze, termini assegnati e prossimi passi già calcolati, ciascuno con la
sua prova (documento e data). Il modello è costruito in sola lettura (``raccogli_fonti`` + ``ragiona``).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable

_log = logging.getLogger(__name__)


def _it(iso: str) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except ValueError:
        return str(iso or "")


def _prova(fonte: Any) -> str:
    if fonte is None:
        return ""
    nome = getattr(fonte, "nome", "") or getattr(fonte, "oggetto_id", "")
    data = getattr(fonte, "data", "")
    return f"{nome}" + (f", del {_it(data)}" if data else "")


@dataclass
class FattiCausa:
    fascicolo_id: str
    rg: str = ""
    ufficio: str = ""
    ruolo_cliente: str = ""
    rito: str = ""
    atti: list[str] = field(default_factory=list)
    udienze: list[str] = field(default_factory=list)
    termini: list[str] = field(default_factory=list)
    passi: list[str] = field(default_factory=list)
    dubbi: list[str] = field(default_factory=list)

    def sezione(self) -> str:
        righe = ["**Dal fascicolo** (modello della causa di IUSENTRA, ogni punto con il documento da cui è letto)"]
        testa = ", ".join(x for x in (self.ufficio, f"R.G. {self.rg}" if self.rg else "", self.rito,
                                      f"cliente {self.ruolo_cliente}" if self.ruolo_cliente and self.ruolo_cliente != "ignoto" else "") if x)
        if testa:
            righe.append(f"- {testa}.")
        for titolo, voci in (("Atti", self.atti), ("Udienze", self.udienze), ("Termini assegnati", self.termini),
                             ("Prossimi passi", self.passi), ("Dubbi del modello", self.dubbi)):
            if voci:
                righe.append(f"*{titolo}*")
                righe += [f"- {v}" for v in voci]
        return "\n".join(righe)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


def da_causa(causa: Any, *, limite: int = 8) -> FattiCausa:
    """Riduce il modello della causa ai fatti che servono all'analisi, con la prova di ciascuno."""
    f = FattiCausa(str(causa.fascicolo_id), causa.rg, causa.ufficio, causa.ruolo_cliente,
                   getattr(causa.rito, "etichetta", ""))
    for a in [a for a in causa.atti if a.appartenenza == "causa"][:limite]:
        f.atti.append(f"{a.etichetta or a.natura}" + (f" del {_it(a.data)}" if a.data else "") + f" — {a.nome}"
                      + (" (dello studio)" if a.dello_studio else ""))
    for u in causa.udienze[:limite]:
        f.udienze.append(f"{_it(u.data)}" + (f" ore {u.ora}" if u.ora else "") + f", {u.modalita.replace('_', ' ')}"
                         + (f" — da {_prova(u.fonte)}" if u.fonte else ""))
    for t in causa.termini[:limite]:
        f.termini.append(f"{t.adempimento}: entro il {_it(t.scadenza)} (onerato: {t.onerato}"
                         + (", perentorio" if t.perentorio else "") + f") — da {_prova(t.fonte)}")
    for c in [c for c in causa.conclusioni if c.stato in {"da_fare", "dubbio"}][:limite]:
        scad = c.termine.scadenza if c.termine and c.termine.scadenza else ""
        norme = ", ".join(str(n.get("norma", "")) for n in c.norme[:2] if n.get("norma"))
        f.passi.append(f"{c.cosa}" + (f": entro il {_it(scad)}" if scad else "") + (f" ({norme})" if norme else "")
                       + (f" — da {_prova(c.letto)}" if c.letto else "") + (" [dubbio]" if c.stato == "dubbio" else ""))
    f.dubbi = [d.testo for d in causa.dubbi[:4]]
    return f


def fatti_del_fascicolo(fascicolo_id: str, *, costruttore: Callable[[str], Any] | None = None) -> FattiCausa | None:
    """Modello della causa del fascicolo; None se il fascicolo non c'è. Gli errori si registrano, non si nascondono."""
    if not fascicolo_id:
        return None
    try:
        if costruttore is None:
            from pct.ragionamento import ragiona
            from web.services.ragionamento_raccolta import raccogli_fonti

            fonti = raccogli_fonti(fascicolo_id)
            causa = ragiona(fonti) if fonti is not None else None
        else:
            causa = costruttore(fascicolo_id)
    except Exception:
        _log.exception("harness: modello della causa non disponibile per il fascicolo %s", fascicolo_id)
        return None
    return da_causa(causa) if causa is not None else None
