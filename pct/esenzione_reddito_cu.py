"""L'esenzione dal contributo unificato per reddito nelle cause di lavoro: anno e soglia confrontati con la tabella datata.

Art. 9, comma 1-bis, D.P.R. 115/2002: nelle controversie di lavoro, pubblico impiego e previdenza paga il contributo
solo la parte con reddito imponibile IRPEF, risultante dall'ultima dichiarazione, superiore al triplo dell'importo
dell'art. 76; l'importo si adegua ogni due anni con decreto interdirigenziale (art. 77). Tabella datata e versionata:
``patrocinio_limiti_reddito`` di ``pct.normative_tables`` (D.M. 10/05/2023, G.U. n. 130 del 06/06/2023: € 12.838,01;
D.M. 22/04/2025, G.U. n. 159 dell'11/07/2025: € 13.659,64, triplo € 40.978,92 — testo del decreto verificato sulla
Gazzetta Ufficiale il 10/11/2026). La dichiarazione si fa con autocertificazione (art. 46 D.P.R. 445/2000) depositata.

Regola (direttiva del 10/11/2026: fonte certa + lettura certa = dato definitivo): l'autocertificazione **depositata**
che dichiara un reddito non superiore al triplo della soglia **vigente alla data del deposito**, per l'anno dell'ultima
dichiarazione possibile a quella data (anno precedente o quello prima), rende l'esenzione certa. Soglia diversa
(modulo vecchio) o anno incoerente: dubbio vero, con il motivo. Un modulo non depositato non conta. Modulo puro.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any

from pct.soglie_nei_documenti import importi_nel_testo

TABELLA = "patrocinio_limiti_reddito"
NORMA = "art. 9, comma 1-bis, e artt. 76-77 D.P.R. 115/2002"
_INTESTAZIONE = re.compile(r"esenzione\s+dal\s+contributo\s+unificato|autocertificazione\s+(?:della\s+situazione\s+)?reddituale", re.IGNORECASE)
_ANNO = re.compile(r"\banno\s+(?:d[ie]\s+(?:imposta|riferimento)\s+|dei\s+redditi\s+)?(20\d{2})\b|\bredditi\s+(?:dell['’]\s*anno\s+|percepiti\s+nel(?:l['’]\s*anno)?\s+|anno\s+)?(20\d{2})\b", re.IGNORECASE)


_INVITO_RIDEPOSITO = re.compile(
    r"\b(?:si\s+invita|si\s+chiede|invita)\b.{0,160}?\bri[ -]?depositare\b.{0,160}?"
    r"\b(?:autocertificazione|dichiarazione\s+sostitutiva)\b.{0,200}?\bcontributo\s+unificato\b",
    re.IGNORECASE,
)


def invito_rideposito(testo: str) -> bool:
    """Riconosce l'invito relativo al contributo nel testo della comunicazione."""
    return bool(_INVITO_RIDEPOSITO.search(" ".join(testo[:4000].split())))


def _euro(valore: Decimal | float) -> str:
    testo = f"{float(valore):,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return f"€ {testo}"


def righe_soglia() -> list[dict[str, Any]]:
    from pct.normative_tables import canonical_table_definitions

    return sorted(canonical_table_definitions()[TABELLA]["rows"], key=lambda r: r["effective_from"])


def soglia_vigente(giorno: date, righe: list[dict[str, Any]] | None = None) -> dict[str, Any] | None:
    """La riga della tabella in vigore alla data (ultimo decreto pubblicato entro quel giorno)."""
    vigenti = [r for r in (righe or righe_soglia()) if r["effective_from"] <= giorno.isoformat()]
    return vigenti[-1] if vigenti else None


def leggi_autocertificazione(testo: str, righe: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Anno di reddito e soglia dichiarata (il triplo di un limite della tabella) letti nel testo."""
    righe = righe or righe_soglia()
    tripli = {Decimal(str(round(r["amount"] * 3, 2))): r for r in righe}
    testo = str(testo or "")
    if invito_rideposito(testo):
        return {"anno": None, "anni": [], "soglia": None, "decreto_soglia": ""}
    # Dentro una PEC di deposito l'autocertificazione è un allegato: si legge solo il suo testo, non il resto del messaggio.
    inizio = _INTESTAZIONE.search(testo)
    if inizio:
        testo = testo[inizio.start():inizio.start() + 2500]
    importi = importi_nel_testo(testo)
    soglia = next((i for i in sorted(importi, reverse=True) if i in tripli), None)
    if soglia is None:
        soglia = next((i for i in sorted(importi, reverse=True) if Decimal("20000") <= i <= Decimal("60000")), None)
    anni = sorted({int(a or b) for a, b in _ANNO.findall(str(testo or ""))})
    return {"anno": anni[-1] if len(anni) == 1 else None, "anni": anni, "soglia": soglia,
            "decreto_soglia": (tripli.get(soglia) or {}).get("decreto", "") if soglia is not None else ""}


def verifica(*, anno: int | None, soglia: Decimal | None, data_deposito: date | None,
             righe: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """{certa, motivo}: l'autocertificazione è conforme alla soglia vigente al deposito e all'ultima dichiarazione?"""
    if data_deposito is None:
        return {"certa": False, "motivo": "Data del deposito dell'autocertificazione non letta: la soglia vigente non si può scegliere."}
    riga = soglia_vigente(data_deposito, righe)
    if riga is None:
        return {"certa": False, "motivo": "Nessuna soglia registrata per la data del deposito."}
    triplo = Decimal(str(round(riga["amount"] * 3, 2)))
    fonte = f"{riga['decreto']}, {riga['gazzetta']}"
    if soglia is None:
        return {"certa": False, "motivo": f"Nell'autocertificazione non è letta la soglia: quella vigente al deposito è {_euro(triplo)} ({fonte})."}
    if soglia > triplo:
        return {"certa": False, "motivo": (f"L'autocertificazione dichiara un reddito fino a {_euro(soglia)}, oltre la soglia vigente "
                                           f"al deposito del {data_deposito.strftime('%d/%m/%Y')} ({_euro(triplo)}, {fonte}): "
                                           "l'esenzione non risulta.")}
    # Un reddito dichiarato non superiore a una soglia più bassa (modulo con il limite precedente) rispetta a maggior
    # ragione quella vigente: il dubbio, se c'è, è solo sull'anno.
    nota = "" if soglia == triplo else f" (dichiarato fino a {_euro(soglia)}, sotto la soglia vigente di {_euro(triplo)})"
    ammessi = {data_deposito.year - 1, data_deposito.year - 2}
    if anno not in ammessi:
        return {"certa": False, "motivo": (f"Anno di reddito {'illeggibile o non indicato' if anno is None else anno} "
                                           f"nell'autocertificazione{nota}: al deposito del {data_deposito.strftime('%d/%m/%Y')} "
                                           f"l'ultima dichiarazione è dei redditi {data_deposito.year - 2} o {data_deposito.year - 1}; "
                                           "verificare l'anno sull'originale depositato.")}
    return {"certa": True, "soglia": float(triplo), "anno": anno, "decreto": fonte,
            "motivo": (f"Esenzione certa: autocertificazione depositata il {data_deposito.strftime('%d/%m/%Y')}, reddito {anno} "
                       f"non superiore a {_euro(soglia)}"
                       + (", pari al triplo del limite vigente" if soglia == triplo else f", sotto il triplo del limite vigente di {_euro(triplo)}")
                       + f" ({fonte}; {NORMA}).")}


__all__ = ["NORMA", "TABELLA", "leggi_autocertificazione", "righe_soglia", "soglia_vigente", "verifica"]
