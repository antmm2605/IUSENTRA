"""Catalogo ufficiale degli atti depositabili nel PDP.

Base: tabelle codificate del Portale Deposito atti Penali (tipi atto con
uffici ammessi, fase e atti contestuali; tipi ufficio; tipi parte; fasi),
lette dal portale il 25/09/2026 (versione 6.11.10), più i ruoli ammessi della
tabella 2 del manuale utente. Dati in ``pct/data/cataloghi/pdp_atti_penali.json``.
Il portale propone solo gli atti ammessi per l'ufficio del procedimento e per
il ruolo dei soggetti rappresentati: il catalogo fa lo stesso.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

from .regole_atti import FUORI_TABELLA, e_principale, etichetta_menu, regola_per

PERCORSO = Path(__file__).resolve().parent.parent / "data" / "cataloghi" / "pdp_atti_penali.json"
ATTO_AVOCAZIONE = "PB3"


@dataclass(frozen=True)
class VoceAtto:
    codice: str
    nome: str
    uffici: tuple[str, ...]
    ruoli: tuple[str, ...] | None  # None: il portale non dichiara i ruoli, nessun filtro
    fase: str
    contestuali: tuple[str, ...] | str  # "*" = tutti gli atti ammessi per ufficio e ruolo
    conferma_ricezione: bool
    principale: bool

    @property
    def norma(self) -> str:
        trovata = re.search(r"\(([^()]*\d[^()]*)\)\s*$", self.nome)
        return trovata.group(1) if trovata else ""


@lru_cache(maxsize=1)
def _dati() -> dict[str, Any]:
    return json.loads(PERCORSO.read_text(encoding="utf-8"))


def fonte() -> dict[str, Any]:
    return dict(_dati()["fonte"])


def uffici() -> list[dict[str, str]]:
    return [dict(u) for u in _dati()["uffici"]]


def ruoli() -> list[dict[str, str]]:
    return [dict(r) for r in _dati()["ruoli"]]


def fasi() -> list[dict[str, str]]:
    return [dict(f) for f in _dati()["fasi"]]


def registri() -> list[dict[str, str]]:
    return [dict(r) for r in _dati()["registri"]]


def distretti() -> list[str]:
    return list(_dati()["distretti"])


def etichetta_ufficio(codice: str) -> str:
    return next((u["descrizione"] for u in _dati()["uffici"] if u["codice"] == codice), codice)


def etichetta_ruolo(codice: str) -> str:
    return next((r["descrizione"] for r in _dati()["ruoli"] if r["codice"] == codice), codice)


@lru_cache(maxsize=1)
def voci() -> tuple[VoceAtto, ...]:
    elenco = [
        VoceAtto(
            codice=a["codice"], nome=a["descrizione"], uffici=tuple(a["uffici"]),
            ruoli=tuple(a["ruoli"]) if a.get("ruoli") is not None else None, fase=a.get("fase") or "",
            contestuali=a["contestuali"] if a["contestuali"] == "*" else tuple(a["contestuali"]),
            conferma_ricezione=a.get("gruppo") == "CONFERMARICEZIONE", principale=e_principale(a["codice"]),
        )
        for a in _dati()["atti"]
    ]
    for codice, (nome, uffici_ammessi, ruoli_ammessi) in FUORI_TABELLA.items():
        elenco.append(VoceAtto(codice, nome, uffici_ammessi, ruoli_ammessi, "IP", (), False, True))
    return tuple(elenco)


def voce(codice: str) -> VoceAtto | None:
    chiave = str(codice or "").strip().upper()
    return next((v for v in voci() if v.codice == chiave), None)


def _uffici_effettivi(voce_atto: VoceAtto, avocato_pg: bool) -> set[str]:
    ammessi = set(voce_atto.uffici)
    # Procedimento avocato: alla Procura Generale gli atti del PM, tranne la richiesta di avocazione.
    if avocato_pg and "PM-U" in ammessi and voce_atto.codice != ATTO_AVOCAZIONE:
        ammessi.add("PGCAP-U")
    return ammessi


def ammesso_per_ruoli(voce_atto: VoceAtto, ruoli_soggetti: Iterable[str]) -> bool:
    richiesti = {str(r).strip().upper() for r in ruoli_soggetti if str(r).strip()}
    return not richiesti or voce_atto.ruoli is None or bool(richiesti.intersection(voce_atto.ruoli))


def atti_ammessi(
    ufficio: str,
    ruoli_soggetti: Iterable[str] = (),
    *,
    avocato_pg: bool = False,
    principali: bool | None = None,
    fase: str = "",
    cerca: str = "",
) -> list[VoceAtto]:
    """Gli atti che il PDP lascerebbe scegliere per quell'ufficio e quei soggetti."""
    codice = str(ufficio or "").strip().upper()
    testo = " ".join(str(cerca or "").casefold().split())
    ruoli_lista = list(ruoli_soggetti)
    esito = [
        v for v in voci()
        if codice in _uffici_effettivi(v, avocato_pg)
        and ammesso_per_ruoli(v, ruoli_lista)
        and (principali is None or v.principale == principali)
        and (not fase or v.fase == fase)
        and (not testo or testo in v.nome.casefold() or testo in etichetta_menu(v.codice).casefold())
    ]
    return sorted(esito, key=lambda v: (not v.principale, v.nome.casefold()))


def contestuali_per(codice: str, ufficio: str, ruoli_soggetti: Iterable[str], *, avocato_pg: bool = False) -> list[VoceAtto]:
    """Atti depositabili insieme a quello principale, già filtrati come fa il PDP."""
    voce_atto = voce(codice)
    if voce_atto is None or not voce_atto.contestuali:
        return []
    if voce_atto.contestuali == "*":
        return [v for v in atti_ammessi(ufficio, ruoli_soggetti, avocato_pg=avocato_pg, principali=False)]
    return [v for v in (voce(c) for c in voce_atto.contestuali) if v is not None]


def scheda(codice: str) -> dict[str, Any]:
    """Tutto quello che serve per preparare quell'atto: uffici, ruoli, dati richiesti."""
    voce_atto = voce(codice)
    if voce_atto is None:
        raise KeyError(f"Atto non presente nel catalogo del PDP: {codice}")
    regola = regola_per(voce_atto.codice)
    return {
        "codice": voce_atto.codice,
        "nome": voce_atto.nome,
        "menu": etichetta_menu(voce_atto.codice),
        "norma": voce_atto.norma,
        "principale": voce_atto.principale,
        "fase": voce_atto.fase,
        "uffici": list(voce_atto.uffici),
        "ruoli": list(voce_atto.ruoli) if voce_atto.ruoli is not None else None,
        "confermaRicezione": voce_atto.conferma_ricezione,
        "procuraSpeciale": regola.procura_speciale,
        "unSoloSoggetto": regola.un_solo_soggetto,
        "contestuali": bool(voce_atto.contestuali),
        "campi": [
            {"chiave": c.chiave, "etichetta": c.etichetta, "tipo": c.tipo, "obbligatorio": c.obbligatorio,
             "opzioni": list(c.opzioni), "nota": c.nota}
            for c in regola.campi
        ],
        "fonte": regola.fonte if (regola.campi or regola.procura_speciale) else "Tabelle codificate del PDP",
    }


def per_nome(nome: str) -> VoceAtto | None:
    """Il tipo atto dal nome mostrato nel PDP (elenchi ed export); prima uguale, poi per prefisso."""
    pulito = " ".join(str(nome or "").casefold().replace("’", "'").split())
    if not pulito:
        return None
    for v in voci():
        if " ".join(v.nome.casefold().split()) == pulito:
            return v
    candidati = [v for v in voci() if " ".join(v.nome.casefold().split()).startswith(pulito[:40])]
    return candidati[0] if len(candidati) == 1 else None


__all__ = [
    "ATTO_AVOCAZIONE", "VoceAtto", "ammesso_per_ruoli", "atti_ammessi", "contestuali_per", "distretti",
    "etichetta_ruolo", "etichetta_ufficio", "fasi", "fonte", "per_nome", "registri", "ruoli", "scheda", "uffici",
    "voce", "voci",
]
