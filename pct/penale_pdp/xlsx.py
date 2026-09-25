"""Lettore minimo di file .xlsx (Office Open XML, ISO/IEC 29500).

Gli elenchi del PDP si esportano in .xlsx: basta leggere il primo foglio,
le stringhe condivise e i valori. Nessuna dipendenza esterna, nessuna
formula eseguita; XML letto con defusedxml; i file oltre 20 MB o con più di
20.000 righe si rifiutano.
"""

from __future__ import annotations

import io
import re
import zipfile
from datetime import datetime, timedelta

from defusedxml.ElementTree import fromstring as _fromstring_sicuro

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
LIMITE_BYTE = 20 * 1024 * 1024
LIMITE_RIGHE = 20000


class XlsxError(ValueError):
    pass


def _colonna(riferimento: str) -> int:
    lettere = re.match(r"[A-Z]+", riferimento or "")
    numero = 0
    for carattere in (lettere.group(0) if lettere else "A"):
        numero = numero * 26 + (ord(carattere) - 64)
    return numero - 1


def _stringhe(archivio: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archivio.namelist():
        return []
    radice = _fromstring_sicuro(archivio.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{{{NS['m']}}}t")) for si in radice.findall("m:si", NS)]


def _primo_foglio(archivio: zipfile.ZipFile) -> str:
    try:
        libro = _fromstring_sicuro(archivio.read("xl/workbook.xml"))
        foglio = libro.find("m:sheets/m:sheet", NS)
        relazioni = _fromstring_sicuro(archivio.read("xl/_rels/workbook.xml.rels"))
        destinazione = next(r.get("Target") for r in relazioni if r.get("Id") == foglio.get(REL))
        destinazione = destinazione.lstrip("/")
        return destinazione if destinazione.startswith("xl/") else f"xl/{destinazione}"
    except Exception:
        return "xl/worksheets/sheet1.xml"


def _data_excel(valore: str) -> str:
    try:
        numero = float(valore)
    except ValueError:
        return valore
    if not 20000 < numero < 80000:
        return valore
    momento = datetime(1899, 12, 30) + timedelta(days=numero)
    return momento.strftime("%d/%m/%Y %H:%M") if numero % 1 else momento.strftime("%d/%m/%Y")


def leggi(dati: bytes) -> list[list[str]]:
    """Le righe del primo foglio come testo (le date Excel in gg/mm/aaaa [hh:mm])."""
    if len(dati) > LIMITE_BYTE:
        raise XlsxError("File troppo grande: il limite è 20 MB.")
    try:
        archivio = zipfile.ZipFile(io.BytesIO(dati))
    except zipfile.BadZipFile as exc:
        raise XlsxError("Il file non è un .xlsx valido: esporta di nuovo l'elenco dal PDP.") from exc
    with archivio:
        stringhe = _stringhe(archivio)
        try:
            foglio = _fromstring_sicuro(archivio.read(_primo_foglio(archivio)))
        except KeyError as exc:
            raise XlsxError("Il file .xlsx non contiene fogli leggibili.") from exc
        stili_data = _stili_data(archivio)
    righe: list[list[str]] = []
    for riga in foglio.iter(f"{{{NS['m']}}}row"):
        valori: dict[int, str] = {}
        for cella in riga.findall("m:c", NS):
            tipo = cella.get("t", "")
            v = cella.find("m:v", NS)
            if tipo == "inlineStr":
                testo = "".join(t.text or "" for t in cella.iter(f"{{{NS['m']}}}t"))
            elif v is None:
                continue
            elif tipo == "s":
                indice = int(v.text or 0)
                testo = stringhe[indice] if indice < len(stringhe) else ""
            else:
                testo = v.text or ""
                if cella.get("s") in stili_data:
                    testo = _data_excel(testo)
            valori[_colonna(cella.get("r", ""))] = " ".join(testo.split())
        if valori:
            righe.append([valori.get(i, "") for i in range(max(valori) + 1)])
        if len(righe) > LIMITE_RIGHE:
            raise XlsxError("Troppe righe: il limite è 20.000.")
    return righe


_FORMATI_DATA = {14, 15, 16, 17, 22, 45, 46, 47}


def _stili_data(archivio: zipfile.ZipFile) -> set[str]:
    """Indici degli stili di cella che rappresentano date (formati numerici predefiniti o personalizzati)."""
    if "xl/styles.xml" not in archivio.namelist():
        return set()
    radice = _fromstring_sicuro(archivio.read("xl/styles.xml"))
    personalizzati = {
        int(f.get("numFmtId", 0))
        for f in radice.findall("m:numFmts/m:numFmt", NS)
        if re.search(r"[dmyh]", (f.get("formatCode") or "").lower().replace("general", ""))
    }
    esito = set()
    for indice, xf in enumerate(radice.findall("m:cellXfs/m:xf", NS)):
        formato = int(xf.get("numFmtId", 0))
        if formato in _FORMATI_DATA or formato in personalizzati:
            esito.add(str(indice))
    return esito


__all__ = ["XlsxError", "leggi"]
