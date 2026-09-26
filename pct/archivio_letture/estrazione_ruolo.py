"""I numeri di ruolo letti nel testo: R.G. 1234/2026, R.G.N.R. 5678/2025.

Nel processo amministrativo il numero di registro generale del ricorso
(art. 5 all. 2 c.p.a., norme di attuazione) si scrive «N. 01729/2025 REG.RIC.»
nell'intestazione dei provvedimenti e «ricorso numero di registro generale 1729
del 2025» nell'epigrafe: è il ruolo della causa. Il numero del provvedimento
(«REG.PROV.COLL.», «REG.PROV.CAU.») non è un ruolo e non si legge.
"""

from __future__ import annotations

import re

from legal_ocr.formulario.confusioni import a_cifre
from pct.registro_letture.fatti_repository import Fatto

_SEGNO = r"[\dOoIl|ÌSsBZz]"
_RUOLO = re.compile(
    rf"(?<![\w])(?P<sigla>R\.?\s*G\.?\s*N\.?\s*R\.?|N\.?\s*R\.?\s*G\.?|R\.?\s*G\.?(?:\s*A\.?\s*C\.?|\s*L\.?)?|ruolo\s+generale)\s*(?:n\.?|numero)?\s*(?P<numero>{_SEGNO}{{1,7}})\s*/\s*(?P<anno>{_SEGNO}{{2,4}})(?![\w])",
    re.IGNORECASE,
)

_RUOLO_AMMINISTRATIVO = re.compile(
    rf"(?:\bN\.?\s*(?P<numero>{_SEGNO}{{1,6}})\s*/\s*(?P<anno>{_SEGNO}{{4}})\s*REG\.?\s*RIC\.?"
    rf"|\bricorso\s+numero\s+di\s+registro\s+generale\s+(?P<numero2>{_SEGNO}{{1,6}})\s+del\s+(?P<anno2>{_SEGNO}{{4}}))",
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
    trovati = sorted([*_RUOLO.finditer(testo), *_RUOLO_AMMINISTRATIVO.finditer(testo)], key=lambda m: m.start())
    for match in trovati:
        amministrativo = match.re is _RUOLO_AMMINISTRATIVO
        grezzo_numero = match.group("numero") or (match.group("numero2") if amministrativo else "")
        grezzo_anno = match.group("anno") or (match.group("anno2") if amministrativo else "")
        numero, anno = a_cifre(grezzo_numero or ""), _anno(grezzo_anno or "")
        if not numero.isdigit() or not anno:
            continue
        sigla = "REGRIC" if amministrativo else re.sub(r"[\s.]", "", match.group("sigla")).upper()
        campo = "numero_ruolo_penale" if "NR" in sigla and sigla.startswith("RGN") else "numero_ruolo"
        valore = f"{int(numero)}/{anno}"
        if (campo, valore) in visti:
            continue
        visti.add((campo, valore))
        sostituzioni = sum(1 for carattere in grezzo_numero + grezzo_anno if not carattere.isdigit())
        fatti.append(Fatto(
            categoria="ruolo", campo=campo, valore=valore, valore_letto=" ".join(match.group(0).split()), etichetta=f"{'R.G.N.R.' if campo.endswith('penale') else 'R.G.'} {valore}",
            contesto=" ".join(testo[max(0, match.start() - 240):match.end() + 80].split()), posizione=match.start(), origine=origine,
            confidenza=max(0.3, 1.0 - 0.2 * sostituzioni),
            prove=[{"codice": "forma", "esito": "ok" if sostituzioni <= 1 else "attenzione", "dettaglio": f"{sostituzioni} segni corretti" if sostituzioni else "nessuna correzione"}],
        ))
    return fatti


__all__ = ["estrai_ruoli"]
