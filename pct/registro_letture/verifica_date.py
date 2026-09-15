"""Le date lette: si scrivono bene, si interpretano e si giudicano.

Una data letta da un documento o da una PEC vale solo se è una data del
calendario, se sta nell'orizzonte del fascicolo e se non contraddice ciò che
il gestionale sa da un'altra fonte (la data di ricezione della PEC, la data di
deposito del portale). L'OCR confonde lo zero con la O, l'uno con la l, il
cinque con la S: dentro un token a forma di data la correzione è certa, fuori
non si tocca nulla. Ogni giudizio porta un codice e un motivo in italiano.

Formato di riferimento: giorno/mese/anno, come nei provvedimenti e nelle
comunicazioni di cancelleria (D.M. 44/2011, specifiche DGSIA: DataDeposito e
DataUdienza sono giorno-mese-anno).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from legal_ocr.formulario.date import mese_canonico, normalizza_data_ocr

MESI = {
    "gen": 1, "gennaio": 1, "feb": 2, "febbraio": 2, "mar": 3, "marzo": 3, "apr": 4, "aprile": 4,
    "mag": 5, "maggio": 5, "giu": 6, "giugno": 6, "lug": 7, "luglio": 7, "ago": 8, "agosto": 8,
    "set": 9, "sett": 9, "settembre": 9, "ott": 10, "ottobre": 10, "nov": 11, "novembre": 11, "dic": 12, "dicembre": 12,
}
_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")
_DATA_NUMERICA = re.compile(r"^(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})$")
_DATA_ESTESA = re.compile(r"^(\d{1,2}|primo|1[º°])\s+([a-zà-ù]+)\.?\s+(\d{4})$", re.IGNORECASE)
_DATA_NEL_TESTO = re.compile(r"(?<![\w€])[\dOoIl|ÌSsBZz]{1,2}\s*[./-]\s*[\dOoIl|ÌSsBZz]{1,2}\s*[./-]\s*[\dOoIl|ÌSsBZz]{2,4}(?![\w])")
ORIZZONTE_FUTURO_ANNI = 3
ORIZZONTE_PASSATO_ANNI = 30
TOLLERANZA_CONFRONTO_GIORNI = 0


def interpreta_data(valore: Any) -> date | None:
    """Data da ISO, da gg/mm/aaaa (anche con anno a due cifre) o da «12 marzo 2026»."""
    if isinstance(valore, datetime):
        return valore.date()
    if isinstance(valore, date):
        return valore
    testo = " ".join(str(valore or "").split()).strip()
    if not testo:
        return None
    iso = _DATA_ISO.match(testo)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None
    numerica = _DATA_NUMERICA.match(testo)
    if numerica:
        giorno, mese, anno = (int(numerica.group(1)), int(numerica.group(2)), numerica.group(3))
        anno_int = int(anno)
        if len(anno) == 2:
            anno_int += 2000 if anno_int <= 49 else 1900
        elif len(anno) == 3:
            return None
        try:
            return date(anno_int, mese, giorno)
        except ValueError:
            return None
    estesa = _DATA_ESTESA.match(testo)
    if estesa:
        mese = MESI.get(estesa.group(2).casefold()) or MESI.get(mese_canonico(estesa.group(2)))
        if not mese:
            return None
        giorno_letto = estesa.group(1).casefold()
        giorno = 1 if giorno_letto in {"primo", "1º", "1°"} else int(giorno_letto)
        try:
            return date(int(estesa.group(3)), mese, giorno)
        except ValueError:
            return None
    return None


def _scambia_giorno_mese(valore: str) -> date | None:
    numerica = _DATA_NUMERICA.match(" ".join(str(valore or "").split()))
    if not numerica:
        return None
    return interpreta_data(f"{numerica.group(2)}/{numerica.group(1)}/{numerica.group(3)}")


def data_it(valore: date | None) -> str:
    return valore.strftime("%d/%m/%Y") if valore else ""


@dataclass(slots=True)
class GiudizioData:
    valore_letto: str
    valore_normalizzato: str
    data: date | None
    stato: str  # valida | sospetta | non_valida
    codici: list[str] = field(default_factory=list)
    motivi: list[str] = field(default_factory=list)
    valore_proposto: str = ""
    gravita: str = "bassa"

    @property
    def valore_iso(self) -> str:
        return self.data.isoformat() if self.data else ""

    @property
    def valore_it(self) -> str:
        return data_it(self.data)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valore_letto": self.valore_letto, "valore_normalizzato": self.valore_normalizzato, "valore_iso": self.valore_iso,
            "valore_it": self.valore_it, "stato": self.stato, "codici": list(self.codici), "motivi": list(self.motivi),
            "valore_proposto": self.valore_proposto, "gravita": self.gravita,
        }


_GRAVITA_ORDINE = {"bassa": 0, "media": 1, "alta": 2}


def valuta_data(
    valore: Any,
    *,
    oggi: date | None = None,
    anno_riferimento: int | None = None,
    data_minima: date | None = None,
    data_confronto: date | None = None,
    etichetta_confronto: str = "",
    tolleranza_giorni: int = TOLLERANZA_CONFRONTO_GIORNI,
) -> GiudizioData:
    """Giudica una data letta: valida, sospetta (con motivo e proposta) o non valida."""
    oggi = oggi or date.today()
    letto = " ".join(str(valore or "").split()).strip()
    normalizzato = normalizza_data_ocr(letto)
    giudizio = GiudizioData(valore_letto=letto, valore_normalizzato=normalizzato, data=None, stato="valida")

    def segnala(codice: str, motivo: str, gravita: str, proposta: str = "") -> None:
        giudizio.codici.append(codice)
        giudizio.motivi.append(motivo)
        if _GRAVITA_ORDINE[gravita] >= _GRAVITA_ORDINE[giudizio.gravita]:
            giudizio.gravita = gravita
        if proposta and not giudizio.valore_proposto:
            giudizio.valore_proposto = proposta
        if giudizio.stato == "valida":
            giudizio.stato = "sospetta"

    if normalizzato != letto:
        segnala("corretta_da_ocr", f"L'OCR ha letto «{letto}»: dentro la data lettere al posto delle cifre, interpretata come «{normalizzato}».", "bassa", normalizzato)
    data = interpreta_data(normalizzato)
    if data is None:
        componenti = _DATA_NUMERICA.match(normalizzato)
        if componenti and 1 <= int(componenti.group(2)) <= 12:
            giudizio.stato = "non_valida"
            giudizio.codici.append("giorno_inesistente")
            giudizio.motivi.append(f"«{normalizzato}» non esiste nel calendario: il mese {int(componenti.group(2))} non ha il giorno {int(componenti.group(1))}.")
            giudizio.gravita = "alta"
            return giudizio
        scambiata = _scambia_giorno_mese(normalizzato)
        if scambiata is not None:
            giudizio.stato = "non_valida"
            segnala("giorno_mese_invertiti", f"«{normalizzato}» non è una data del calendario; invertendo giorno e mese diventa {data_it(scambiata)}.", "alta", data_it(scambiata))
            giudizio.stato = "non_valida"
            return giudizio
        giudizio.stato = "non_valida"
        giudizio.codici.append("non_interpretabile")
        giudizio.motivi.append(f"«{letto}» non è una data leggibile nel formato giorno/mese/anno.")
        giudizio.gravita = "alta"
        return giudizio
    giudizio.data = data
    anno_massimo = oggi.year + ORIZZONTE_FUTURO_ANNI
    anno_minimo = (anno_riferimento - 2) if anno_riferimento else (oggi.year - ORIZZONTE_PASSATO_ANNI)
    if data.year > anno_massimo:
        segnala("anno_futuro", f"La data {data_it(data)} è oltre {ORIZZONTE_FUTURO_ANNI} anni nel futuro: probabile cifra letta male nell'anno.", "alta")
    elif data.year < anno_minimo:
        motivo = (f"La data {data_it(data)} precede di oltre due anni l'anno di ruolo {anno_riferimento}." if anno_riferimento
                  else f"La data {data_it(data)} è più vecchia di {ORIZZONTE_PASSATO_ANNI} anni.")
        segnala("anno_remoto", motivo, "media")
    if data_minima and data < data_minima:
        segnala("prima_del_fascicolo", f"La data {data_it(data)} precede l'apertura del fascicolo ({data_it(data_minima)}): per un termine o un'udienza non è plausibile.", "media")
    if data_confronto is not None:
        scarto = abs((data - data_confronto).days)
        if scarto > max(0, int(tolleranza_giorni)):
            etichetta = etichetta_confronto or "la data nota da un'altra fonte"
            scambiata = _scambia_giorno_mese(normalizzato)
            proposta = data_it(data_confronto)
            if scambiata is not None and scambiata == data_confronto:
                segnala("giorno_mese_invertiti", f"La data letta {data_it(data)} coincide con {etichetta} ({proposta}) solo invertendo giorno e mese.", "alta", proposta)
            else:
                segnala("incoerente_con_fonte", f"La data letta {data_it(data)} non coincide con {etichetta} ({proposta}): scarto di {scarto} giorni.", "media", proposta)
    return giudizio


def date_nel_testo(testo: str) -> list[str]:
    """Le date scritte nel testo, numeriche o estese, nell'ordine in cui compaiono (senza correggerle)."""
    trovate: list[str] = []
    for match in _DATA_NEL_TESTO.finditer(str(testo or "")):
        if any(carattere.isdigit() for carattere in match.group(0)):
            trovate.append(match.group(0))
    for match in re.finditer(r"\b(\d{1,2}|primo)\s+(" + "|".join(sorted(MESI, key=len, reverse=True)) + r")\.?\s+(\d{4})\b", str(testo or ""), re.IGNORECASE):
        trovate.append(re.sub(r"\s+", " ", match.group(0)))
    visti: set[str] = set()
    uniche: list[str] = []
    for voce in trovate:
        if voce not in visti:
            visti.add(voce)
            uniche.append(voce)
    return uniche


def orizzonte_fascicolo(fascicolo: Any, *, oggi: date | None = None) -> dict[str, Any]:
    """Anno di riferimento e data minima plausibile per le date processuali del fascicolo."""
    oggi = oggi or date.today()
    anno = 0
    try:
        anno = int(str(getattr(fascicolo, "anno_rg", "") if not isinstance(fascicolo, dict) else fascicolo.get("anno_rg", "") or 0).strip() or 0)
    except ValueError:
        anno = 0
    apertura = interpreta_data(getattr(fascicolo, "data_apertura", "") if not isinstance(fascicolo, dict) else fascicolo.get("data_apertura", ""))
    if not anno and apertura:
        anno = apertura.year
    data_minima = (apertura - timedelta(days=365)) if apertura else None
    return {"oggi": oggi, "anno_riferimento": anno or None, "data_minima": data_minima}


__all__ = [
    "GiudizioData", "MESI", "ORIZZONTE_FUTURO_ANNI", "ORIZZONTE_PASSATO_ANNI", "data_it", "date_nel_testo",
    "interpreta_data", "normalizza_data_ocr", "orizzonte_fascicolo", "valuta_data",
]
