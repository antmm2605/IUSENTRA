"""Le spese regolate dalla sentenza della causa, come le ha già lette il motore documenti.

Il motore documenti registra in sfondo, per ogni sentenza, il fatto «spese_sentenza» letto dal dispositivo
(``estrazione_esito.py``): regolazione (condanna, compensazione), importo liquidato e distrazione. Il conto
economico lo consulta qui, senza riaprire il PDF nella richiesta.

Vale solo la sentenza **della causa**: il primo numero di ruolo letto nell'intestazione del documento deve essere
quello del fascicolo (come in ``pct/fascicolo_lettura/documenti.py``); una sentenza allegata come precedente non
liquida nulla al cliente.

Norme: art. 91 c.p.c. (condanna alle spese del soccombente), art. 92 c.p.c. (compensazione), art. 93 c.p.c.
(distrazione in favore del difensore antistatario, che deve averla chiesta dichiarando di aver anticipato le spese
e non riscosso gli onorari), art. 2, comma 2, D.M. 55/2014 (rimborso forfettario del 15% del compenso, fra gli
«accessori» che la sentenza riconosce oltre all'importo liquidato).
"""

from __future__ import annotations

import re
from typing import Any, Iterable

VERIFICHE_CERTE = {"verificata", "corretta"}
NORMA_CONDANNA = "art. 91 c.p.c."
NORMA_COMPENSAZIONE = "art. 92 c.p.c."
NORMA_FORFETTARIO = "art. 2, comma 2, D.M. 55/2014"

# Chi è condannato e in favore di chi: il lato «attivo» (chi ha promosso la causa) o «passivo» (chi resiste).
_ATTIVO = r"(?:ricorrent|attor|attric|opponent|appellant|reclamant|istant)"
_PASSIVO = r"(?:convenut|resistent|oppost|appellat|reclamat|amministrazion|minister|comune|ente)"
_CONDANNATO = re.compile(r"\bcondanna\s+(?:in\s+solido\s+)?(?:il|la|l['’]|i|le|gli)?\s*(?:parte\s+|parti\s+)?(\w+)", re.IGNORECASE)
_IN_FAVORE = re.compile(r"\bin\s+favore\s+(?:del|della|dei|delle|dello|di)\s+(?:parte\s+|parti\s+)?(\w+)", re.IGNORECASE)
_OVE_RICHIESTO = re.compile(r"\b(?:ove|se|qualora)\s+richiest", re.IGNORECASE)
_ACCESSORI = re.compile(r"\baccessori\b|\bspese\s+generali\b|\brimborso\s+forfettario\b", re.IGNORECASE)


def _lato(parola: str) -> str:
    if re.match(_ATTIVO, parola or "", re.IGNORECASE):
        return "attivo"
    if re.match(_PASSIVO, parola or "", re.IGNORECASE):
        return "passivo"
    return ""


def beneficiario(frase: str) -> str:
    """Il lato processuale che riceve le spese («attivo» o «passivo»), letto dalla frase del dispositivo."""
    frase = str(frase or "")
    favore = _IN_FAVORE.search(frase)
    if favore and _lato(favore.group(1)):
        return _lato(favore.group(1))
    condannato = _CONDANNATO.search(frase)
    lato = _lato(condannato.group(1)) if condannato else ""
    return {"attivo": "passivo", "passivo": "attivo"}.get(lato, "")


def importo_euro(testo: str) -> float | None:
    """«1.234,56» o «250,00» -> numero; None se illeggibile."""
    pulito = str(testo or "").strip().replace(".", "").replace(",", ".")
    try:
        valore = round(float(pulito), 2)
    except ValueError:
        return None
    return valore if valore > 0 else None


def _valore(fatto: Any, nome: str) -> Any:
    return fatto.get(nome) if isinstance(fatto, dict) else getattr(fatto, nome, None)


def spese_lette(fatti: Iterable[Any], *, rg: str) -> list[dict[str, Any]]:
    """Le regolazioni delle spese lette nelle sentenze della causa, una per documento.

    ``rg`` è il numero di ruolo del fascicolo («2539/2025»): senza, nessuna sentenza è riconoscibile come della causa.
    """
    rg = re.sub(r"\s+", "", str(rg or ""))
    if not rg:
        return []
    fatti = list(fatti)
    per_documento: dict[str, list[Any]] = {}
    for fatto in fatti:
        per_documento.setdefault(str(_valore(fatto, "oggetto_id") or ""), []).append(fatto)
    risultato = []
    for documento_id, prove in per_documento.items():
        certe = [f for f in prove if str(_valore(f, "verifica") or "") in VERIFICHE_CERTE]
        ruoli = sorted((f for f in prove if str(_valore(f, "categoria") or "") == "ruolo"), key=lambda f: int(_valore(f, "posizione") or 0))
        pertinente = bool(ruoli) and re.sub(r"\s+", "", str(_valore(ruoli[0], "valore") or "")) == rg \
            and str(_valore(ruoli[0], "verifica") or "") in VERIFICHE_CERTE
        spese = next((f for f in certe if _valore(f, "campo") == "spese_sentenza"), None)
        if not documento_id or not pertinente or spese is None:
            continue
        parti = str(_valore(spese, "valore") or "").split(";")
        importo = next((importo_euro(p.split("=", 1)[1]) for p in parti if p.startswith("importo=")), None)
        frase = str(_valore(spese, "contesto") or _valore(spese, "valore_letto") or "")
        date = sorted((f for f in certe if _valore(f, "campo") == "data_atto"), key=lambda f: int(_valore(f, "posizione") or 0))
        risultato.append({
            "documento_id": documento_id,
            "regolazione": parti[0] if parti and parti[0] else "non_indicata",
            "importo": importo,
            "distrazione": "distrazione" in parti,
            "distrazione_condizionata": "distrazione" in parti and bool(_OVE_RICHIESTO.search(frase)),
            "accessori": bool(_ACCESSORI.search(frase)),
            "beneficiario": beneficiario(frase),
            "frase": frase,
            "data": str(_valore(date[-1], "valore") or "")[:10] if date else "",
        })
    return risultato


__all__ = ["NORMA_COMPENSAZIONE", "NORMA_CONDANNA", "NORMA_FORFETTARIO", "beneficiario", "importo_euro", "spese_lette"]
