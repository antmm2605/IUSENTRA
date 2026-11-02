"""Le materie della biblioteca «Codici e leggi» pertinenti al fascicolo, per la ricerca nel pannello.

Le materie sono quelle della classificazione deterministica degli atti
(`lex.normativa.materie`). Il tipo del fascicolo indica la materia principale;
l'area della pratica, quando è scritta, aggiunge la materia sostanziale.
La procedura civile accompagna ogni contenzioso civile perché ne regola il rito.
"""

from __future__ import annotations

from lex.normativa import materie as m

PER_TIPO: dict[str, tuple[str, ...]] = {
    "CIVILE": (m.CIVILE, m.PROC_CIVILE),
    "LAVORO": (m.LAVORO, m.PROC_CIVILE),
    "FAMIGLIA": (m.FAMIGLIA, m.CIVILE, m.PROC_CIVILE),
    "SUCCESSIONI": (m.CIVILE, m.PROC_CIVILE),
    "PENALE": (m.PENALE,),
    "AMMINISTRATIVO": (m.AMMINISTRATIVO,),
    "TRIBUTARIO": (m.TRIBUTARIO,),
    "STRAGIUDIZIALE": (m.CIVILE, m.PROC_CIVILE),
    "CONSULENZA": (m.CIVILE,),
}

# Parole dell'area della pratica → materia della biblioteca.
PER_AREA: tuple[tuple[str, str], ...] = (
    ("lavor", m.LAVORO), ("previden", m.LAVORO), ("famigl", m.FAMIGLIA), ("minor", m.FAMIGLIA),
    ("penal", m.PENALE), ("amministr", m.AMMINISTRATIVO), ("appalt", m.AMMINISTRATIVO),
    ("tribut", m.TRIBUTARIO), ("fiscal", m.TRIBUTARIO), ("societ", m.IMPRESA), ("crisi", m.IMPRESA),
    ("fallim", m.IMPRESA), ("banc", m.BANCA), ("assicur", m.BANCA), ("consum", m.CONSUMO),
    ("privacy", m.DIGITALE), ("ambient", m.AMBIENTE), ("edili", m.AMBIENTE), ("immigra", m.IMMIGRAZIONE),
    ("circolaz", m.TRASPORTI), ("sinistr", m.TRASPORTI), ("locaz", m.CIVILE), ("condomin", m.CIVILE),
)


def materie_del_fascicolo(tipo: str, area_pratica: str = "") -> list[str]:
    scelte: list[str] = []
    area = " ".join(str(area_pratica or "").split()).lower()
    for indizio, materia in PER_AREA:
        if indizio in area and materia not in scelte:
            scelte.append(materia)
    for materia in PER_TIPO.get(" ".join(str(tipo or "").split()).upper(), ()):
        if materia not in scelte:
            scelte.append(materia)
    return scelte


__all__ = ["materie_del_fascicolo"]
