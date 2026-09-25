"""Il foglio Excel delle parti che il Formweb importa con «Carica Excel».

Nella scheda «Parti» del deposito il portale accetta, per ricorrenti,
resistenti e controinteressati, il foglio ufficiale «Excel_Parti.xlsx»
(documentazione operativa e modulistica, 2025): colonne Tipologia, Cognome,
Nome, Codice fiscale / P.IVA, PEC, Denominazione; tipologie Persona fisica,
Persona giuridica, Amministrazione, Minore/Incapacita. IUSENTRA parte dal file
ufficiale (``pct/data/pat_moduli/Excel_Parti_2025.xlsx``), ne conserva stili,
colonne e proprietà, toglie le righe di esempio e scrive le parti del
fascicolo. Nessuna libreria esterna: si riscrive solo il foglio.
"""

from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.sax.saxutils import escape

MODELLO = Path(__file__).resolve().parents[1] / "data" / "pat_moduli" / "Excel_Parti_2025.xlsx"
FOGLIO = "xl/worksheets/sheet1.xml"
INTESTAZIONE = ("Tipologia", "Cognome", "Nome", "Codice fiscale / P.IVA", "PEC", "Denominazione")
TIPOLOGIE = {"Persona fisica", "Persona giuridica", "Amministrazione", "Minore/Incapacita"}
_COLONNE = "ABCDEF"


def riga(parte: dict[str, Any]) -> tuple[str, str, str, str, str, str]:
    tipologia = str(parte.get("tipologia") or "Persona fisica")
    if tipologia not in TIPOLOGIE:
        raise ValueError(f"Tipologia di parte non prevista dal foglio ufficiale: {tipologia}.")
    fisica = tipologia in {"Persona fisica", "Minore/Incapacita"}
    return (
        tipologia,
        str(parte.get("cognome") or "").strip().upper() if fisica else "",
        str(parte.get("nome") or "").strip().upper() if fisica else "",
        str(parte.get("codiceFiscale") or "").strip().upper(),
        str(parte.get("pec") or "").strip().lower(),
        str(parte.get("denominazione") or "").strip() if not fisica or tipologia == "Minore/Incapacita" else "",
    )


def _xml_riga(numero: int, valori: tuple[str, ...]) -> str:
    celle = "".join(
        f'<c r="{_COLONNE[i]}{numero}" t="inlineStr"><is><t xml:space="preserve">{escape(v)}</t></is></c>'
        for i, v in enumerate(valori) if v)
    return f'<row r="{numero}" spans="1:6">{celle}</row>'


def genera(parti: Iterable[dict[str, Any]]) -> bytes:
    righe = [riga(p) for p in parti]
    if not righe:
        raise ValueError("Nessuna parte da esportare per questo ruolo.")
    uscita = io.BytesIO()
    with zipfile.ZipFile(MODELLO) as origine, zipfile.ZipFile(uscita, "w", zipfile.ZIP_DEFLATED) as destinazione:
        for voce in origine.infolist():
            contenuto = origine.read(voce.filename)
            if voce.filename == FOGLIO:
                foglio = contenuto.decode("utf-8")
                intestazione = re.search(r'<row r="1".*?</row>', foglio, re.S)
                if intestazione is None:
                    raise ValueError("Il modello Excel_Parti non corrisponde più al foglio ufficiale: aggiornarlo.")
                dati = intestazione.group(0) + "".join(_xml_riga(n, v) for n, v in enumerate(righe, start=2))
                foglio = re.sub(r"<sheetData>.*</sheetData>", lambda _: f"<sheetData>{dati}</sheetData>", foglio, flags=re.S)
                foglio = re.sub(r'<dimension ref="[^"]*"/>', f'<dimension ref="A1:F{len(righe) + 1}"/>', foglio)
                contenuto = foglio.encode("utf-8")
            destinazione.writestr(voce, contenuto)
    return uscita.getvalue()


def leggi(dati: bytes) -> list[list[str]]:
    """Le righe (intestazione compresa) di un foglio parti, generato da IUSENTRA o scaricato dal portale."""
    from pct.penale_pdp.xlsx import leggi as leggi_xlsx

    return leggi_xlsx(dati)


__all__ = ["INTESTAZIONE", "MODELLO", "genera", "leggi", "riga"]
