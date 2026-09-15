"""I numeri di ruolo letti nel testo: R.G. 1234/2026, R.G.N.R. 5678/2025."""

from __future__ import annotations

import re

from legal_ocr.formulario.confusioni import a_cifre
from pct.registro_letture.fatti_repository import Fatto

_SEGNO = r"[\dOoIl|ÌSsBZz]"
_RUOLO = re.compile(
    rf"(?<![\w])(?P<sigla>R\.?\s*G\.?\s*N\.?\s*R\.?|N\.?\s*R\.?\s*G\.?|R\.?\s*G\.?(?:\s*A\.?\s*C\.?|\s*L\.?)?|ruolo\s+generale)\s*(?:n\.?|numero)?\s*(?P<numero>{_SEGNO}{{1,7}})\s*/\s*(?P<anno>{_SEGNO}{{2,4}})(?![\w])",
    re.IGNORECASE,
)


def _anno(grezzo: str) -> str:
    cifre = a_cifre(grezzo)
    if not cifre.isdigit():
        return ""
    if len(cifre) == 4 and 1950 <= int(cifre) <= 2099:
        return cifre
    if len(cifre) == 2:
        return str(int(cifre) + (2000 if int(cifre) <= 49 else 1900))
    return ""


def estrai_ruoli(testo: str, *, origine: str) -> list[Fatto]:
    testo = str(testo or "")
    fatti: list[Fatto] = []
    visti: set[str] = set()
    for match in _RUOLO.finditer(testo):
        numero, anno = a_cifre(match.group("numero")), _anno(match.group("anno"))
        if not numero.isdigit() or not anno:
            continue
        sigla = re.sub(r"[\s.]", "", match.group("sigla")).upper()
        campo = "numero_ruolo_penale" if "NR" in sigla and sigla.startswith("RGN") else "numero_ruolo"
        valore = f"{int(numero)}/{anno}"
        if (campo, valore) in visti:
            continue
        visti.add((campo, valore))
        sostituzioni = sum(1 for carattere in match.group("numero") + match.group("anno") if not carattere.isdigit())
        fatti.append(Fatto(
            categoria="ruolo", campo=campo, valore=valore, valore_letto=" ".join(match.group(0).split()), etichetta=f"{'R.G.N.R.' if campo.endswith('penale') else 'R.G.'} {valore}",
            contesto=" ".join(testo[max(0, match.start() - 80):match.end() + 80].split()), posizione=match.start(), origine=origine,
            confidenza=max(0.3, 1.0 - 0.2 * sostituzioni),
            prove=[{"codice": "forma", "esito": "ok" if sostituzioni <= 1 else "attenzione", "dettaglio": f"{sostituzioni} segni corretti" if sostituzioni else "nessuna correzione"}],
        ))
    return fatti


__all__ = ["estrai_ruoli"]
