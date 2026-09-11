"""Nessun ``event.currentTarget`` dentro gli aggiornamenti funzionali di stato React.

React azzera ``event.currentTarget`` al termine del gestore. L'aggiornamento
``setX((current) => ...)`` può essere eseguito dopo, durante il render: la lettura
restituisce ``null``, il render va in errore e ``AppErrorBoundary`` ricarica la pagina.
Caso reale: in Nuovo cliente il secondo click su «Crea preventivo iniziale dopo il
salvataggio» ricaricava la pagina. Il valore va letto prima (``const value = ...``).
"""

from __future__ import annotations

import re
from pathlib import Path

SOURCE_ROOT = Path("frontend/src")
_SETTER_UPDATER_RE = re.compile(r"\bset[A-Z]\w*\(\s*\(\s*\w+\s*\)\s*=>")


def _updater_bodies(source: str):
    for match in _SETTER_UPDATER_RE.finditer(source):
        start = source.index("(", match.start())
        depth = 0
        for index in range(start, len(source)):
            char = source[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    yield source[: match.start()].count("\n") + 1, source[start:index]
                    break


def test_nessun_current_target_negli_aggiornamenti_funzionali():
    offenders = [
        f"{path.as_posix()}:{line}"
        for path in sorted([*SOURCE_ROOT.rglob("*.tsx"), *SOURCE_ROOT.rglob("*.ts")])
        for line, body in _updater_bodies(path.read_text(encoding="utf-8"))
        if "currentTarget" in body
    ]
    assert offenders == []


def test_nuovo_cliente_legge_nome_e_stato_della_casella_prima_dell_aggiornamento():
    source = Path("frontend/src/components/NuovoClientePage.tsx").read_text(encoding="utf-8")
    checkbox = source[source.index("const checkbox = (event: ChangeEvent<HTMLInputElement>) => {") :]
    checkbox = checkbox[: checkbox.index("\n  }\n")]
    assert "const { name, checked } = event.currentTarget" in checkbox
    assert "setValues((current) => ({...current, [name]: checked}))" in checkbox
    assert 'name="crea_preventivo_iniziale"' in source
