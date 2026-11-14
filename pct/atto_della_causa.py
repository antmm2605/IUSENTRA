"""Se un provvedimento presente nel fascicolo è un atto di questa causa o un precedente prodotto.

Un obbligo processuale (notificare la sentenza, impugnarla, eseguirla) nasce solo dal provvedimento
del procedimento iscritto nel fascicolo: un'altra sentenza allegata al ricorso come giurisprudenza
(art. 115 c.p.c.: il giudice decide sulle prove proposte; i precedenti sono argomenti, non atti del
giudizio) non fa decorrere nessun termine e non si notifica. La causa si riconosce:

- dal numero di ruolo generale (art. 168 c.p.c.; art. 36 disp. att. c.p.c.: il fascicolo d'ufficio
  porta il numero di iscrizione a ruolo), che il provvedimento riporta in intestazione;
- dalla data: un provvedimento sottoscritto prima dell'anno di iscrizione a ruolo non può decidere
  una causa iscritta dopo.

Esiti: vero (stesso ruolo), falso (ruolo diverso o data anteriore all'iscrizione), indeterminato
(nessun ruolo leggibile e data compatibile): solo i primi due cambiano gli obblighi; il terzo resta
com'era. Modulo puro (collaudo 10/11/2026, difetto G-8).
"""

from __future__ import annotations

import re
from typing import Iterable

# «RG n. 161/2026», «N.RG 4202 / 2024», «n. XXX/2022 R.G.», «Numero registro generale 10072/2023».
_RG_DOPO = re.compile(
    r"(?:\bR\.?\s*G\.?(?:\s*N\.?)?|\bN\.?\s*R\.?\s*G\.?|ruolo\s+generale|registro\s+generale)\s*(?:n\.?|nr\.?|numero)?\s*[:.]?\s*"
    r"(?P<numero>0*[0-9X]{1,7})\s*[/-]\s*(?P<anno>(?:19|20)\d{2})",
    re.IGNORECASE,
)
_RG_PRIMA = re.compile(r"\bn\.?\s*(?P<numero>0*[0-9X]{1,7})\s*/\s*(?P<anno>(?:19|20)\d{2})\s*R\.?\s*G\b", re.IGNORECASE)


def stesso_numero_ruolo(primo: str, secondo: str) -> bool:
    """Confronta gli identificativi di ruolo anche con zeri aggiunti dal registro."""
    primo = re.sub(r"\s+", "", str(primo or "")).casefold()
    secondo = re.sub(r"\s+", "", str(secondo or "")).casefold()
    return bool(primo and secondo) and primo.lstrip("0") == secondo.lstrip("0")


def ruoli_in_intestazione(testo: str, *, caratteri: int = 1500) -> list[tuple[str, str]]:
    """I numeri di ruolo scritti nell'intestazione (numero, anno); «XXX» resta per i testi anonimizzati."""
    testata = str(testo or "")[:caratteri]
    ruoli: list[tuple[str, str]] = []
    for espressione in (_RG_DOPO, _RG_PRIMA):
        for trovato in espressione.finditer(testata):
            voce = (trovato.group("numero").lstrip("0").upper() or "0", trovato.group("anno"))
            if voce not in ruoli:
                ruoli.append(voce)
    return ruoli


def provvedimento_della_causa(*, ruoli: Iterable[tuple[str, str]], date_atto: Iterable[str],
                              numero_rg: str, anno_rg: str | int) -> tuple[bool | None, str]:
    """(esito, motivo): il provvedimento appartiene al procedimento del fascicolo?"""
    numero = str(numero_rg or "").strip().lstrip("0").upper()
    anno = str(anno_rg or "").strip()
    ruoli = [(str(n).upper(), str(a)) for n, a in ruoli]
    if numero and anno and anno.isdigit():
        if any(n == numero and a == anno for n, a in ruoli):
            return True, f"Il provvedimento riporta il ruolo del fascicolo (RG {numero}/{anno})."
        if ruoli:
            letti = ", ".join(f"{n}/{a}" for n, a in ruoli)
            return False, f"Il provvedimento riporta un altro ruolo (RG {letti}), non quello del fascicolo ({numero}/{anno}): è un precedente prodotto."
    if anno.isdigit():
        anni = sorted({str(d)[:4] for d in date_atto if str(d)[:4].isdigit()})
        if anni and all(int(a) < int(anno) for a in anni):
            return False, (f"Il provvedimento è datato {anni[-1]}, prima dell'iscrizione a ruolo del fascicolo ({anno}): "
                           "non può decidere questa causa.")
    return None, ""


__all__ = ["provvedimento_della_causa", "ruoli_in_intestazione", "stesso_numero_ruolo"]
