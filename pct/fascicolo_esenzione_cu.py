"""L'autocertificazione di esenzione archiviata sotto la voce sbagliata.

Le pratiche importate da un gestionale precedente portano spesso
l'autocertificazione di esenzione dal contributo unificato sotto «spese ed
esborsi» o un'altra voce qualsiasi: l'import ha conservato il file, non il suo
significato. Per l'avvocato il risultato è doppio danno — il contributo
unificato resta «da registrare» per una somma che non è dovuta, e fra le spese
compare una voce che spesa non è.

Qui la si riconosce dal nome del documento e la si riporta dove appartiene.
Il riconoscimento è dal **nome**, non dal contenuto: un'autocertificazione si
chiama come si chiama, e non serve aprirla per sapere a che cosa si riferisce.

Base normativa: art. 9 comma 1-bis e art. 76 D.P.R. 115/2002 (esenzione dal
contributo unificato per le controversie di lavoro e previdenza e per chi è
ammesso al patrocinio a spese dello Stato).
"""

from __future__ import annotations

import re
from typing import Any

#: il nome di un'autocertificazione di esenzione dal contributo unificato
_RE_AUTOCERTIFICAZIONE = re.compile(r"autocertificaz|dichiarazione\s+sostitutiva", re.I)
_RE_ESENZIONE_CU = re.compile(
    r"esenzion\w*.{0,40}(?:\bc\.?\s*u\.?\b|contributo\s+unificato)"
    r"|(?:\bc\.?\s*u\.?\b|contributo\s+unificato).{0,40}esenzion\w*",
    re.I,
)

#: le voci economiche sotto cui l'import puo' aver messo l'autocertificazione
VOCI_SPURIE = ("spese_esborsi", "fondo_spese", "liquidazione_giudice", "parcella")

NOTA_CONTRIBUTO = (
    "Esenzione dal contributo unificato autocertificata nel fascicolo "
    "(art. 9 co. 1-bis e art. 76 D.P.R. 115/2002)."
)
NOTA_VOCE_SPURIA = "Autocertificazione riferita al contributo unificato"


def e_autocertificazione_di_esenzione(nome: str) -> bool:
    """Il nome del documento dice che è un'autocertificazione di esenzione dal CU."""
    testo = " ".join(str(nome or "").split())
    return bool(_RE_AUTOCERTIFICAZIONE.search(testo) and _RE_ESENZIONE_CU.search(testo))


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def voce_spuria_con_esenzione(pagamenti: Any) -> tuple[str, str]:
    """La voce economica che porta per errore l'autocertificazione, e il nome del file.

    Restituisce `("", "")` quando non ce n'è: nulla da spostare.
    """
    if not isinstance(pagamenti, dict):
        return "", ""
    for voce in VOCI_SPURIE:
        riga = pagamenti.get(voce)
        if not isinstance(riga, dict):
            continue
        nome = _testo(riga.get("documento_fonte") or riga.get("documentoFonte"))
        if nome and e_autocertificazione_di_esenzione(nome):
            return voce, nome
    return "", ""


def sposta_esenzione_sul_contributo(pagamenti: Any) -> dict[str, dict[str, Any]]:
    """Le due voci corrette: il contributo non dovuto, e la voce spuria svuotata.

    Dizionario vuoto quando non c'è nulla da spostare — cosi' il chiamante
    distingue «niente da fare» da «fatto».
    """
    voce, nome = voce_spuria_con_esenzione(pagamenti)
    if not voce:
        return {}
    return {
        "contributo_unificato": {
            "kind": "contributo_unificato", "status": "non_previsto", "previsto": False, "pagato": False,
            "importo": None, "natura": "esenzione_contributo_unificato",
            "documento_fonte": nome, "origine": "Import pratiche",
            "updated_by": "IUSENTRA automatico", "note": NOTA_CONTRIBUTO,
        },
        voce: {
            "kind": voce, "status": "non_previsto", "previsto": False, "pagato": False,
            "importo": None, "documento_fonte": NOTA_VOCE_SPURIA,
            "origine": "Import pratiche", "updated_by": "IUSENTRA automatico",
            "note": "Il documento riguarda l'esenzione dal contributo unificato, non questa voce.",
        },
    }


__all__ = [
    "NOTA_CONTRIBUTO", "NOTA_VOCE_SPURIA", "VOCI_SPURIE",
    "e_autocertificazione_di_esenzione", "sposta_esenzione_sul_contributo",
    "voce_spuria_con_esenzione",
]
