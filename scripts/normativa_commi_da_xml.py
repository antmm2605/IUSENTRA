"""Indice dei commi dagli XML ufficiali di Normattiva (raccolte «XML VIGENTE» dell'OpenData).

Uso:
    python scripts/normativa_commi_da_xml.py RACCOLTA.zip [RACCOLTA.zip ...] [--atti 1942-03-16_262,...] [--uscita FILE]

Per ogni articolo si leggono i paragrafi del corpo nel formato NIR di Normattiva:
- leggi con i commi numerati («1.», «2.», «3-bis.»): un comma nuovo inizia solo al numero successivo atteso;
  le righe spezzate e le lettere restano nel comma;
- codici con i commi senza numero: ogni paragrafo rientrato di 2 px è un comma; i rientri maggiori e le voci
  «1)», «a)» restano nel comma; un paragrafo che non chiude la frase continua nel successivo.
Le note («AGGIORNAMENTO», righe di trattini) non fanno parte del corpo. Si salva solo dove inizia ogni comma e
l'impronta del testo (vedi ``lex/normativa/commi.py``): nessun testo normativo nuovo entra nell'indice.
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
import zipfile
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.normativa.commi import INDICE, _VOCE_INTERNA, chiave, voce_indice  # noqa: E402

_P = re.compile(r'<h:p(?P<attr>[^>]*)>(?P<testo>.*?)</h:p>', re.DOTALL)
_TAG = re.compile(r"<[^>]+>")
_ARTICOLO = re.compile(r"^Art(?:icolo)?\.?\s*(?P<n>\d+(?:[\s.-]*[a-z]+)?(?:\.\d+)?)\s*(?:\((?:L|R|D)\)\s*)?\.?\s*$", re.I)
_NUMERO_COMMA = re.compile(r"^(?P<n>\d{1,3})(?:[\s.-]*(?P<s>bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?\.\s")
_NOTA = re.compile(r"^(?:-{5,}|AGGIORNAMENTO\b|<!\[CDATA\[|&lt;!\[CDATA\[)")
_FINE_FRASE = re.compile(r"[.;:!?»\"”]\s*(?:\(\(?\d{1,4}[a-z]?\)\)?\s*)*$")
_NOME = re.compile(r"_(?P<data>\d{8})_(?P<numero>\d+[A-Za-z]*)/")


def _testo(frammento: str) -> str:
    return " ".join(html.unescape(_TAG.sub(" ", frammento)).split())


def _rientro(attr: str) -> int:
    trovato = re.search(r"padding-left:\s*(\d+)px", attr)
    return int(trovato.group(1)) if trovato else 0


def articoli(xml: str):
    """(numero, intestazione, paragrafi [(testo, rientro)]) per ogni articolo del documento."""
    corrente = None
    for p in _P.finditer(xml):
        attr, testo = p.group("attr"), _testo(p.group("testo"))
        if not testo:
            continue
        centrato = "center" in attr
        art = _ARTICOLO.match(testo) if centrato else None
        if art:
            if corrente:
                yield corrente
            corrente = {"numero": art.group("n"), "intestazione": [testo], "paragrafi": [], "note": False}
            continue
        if corrente is None or corrente["note"]:
            continue
        if _NOTA.match(testo) or testo.startswith("<![CDATA["):
            corrente["note"] = True
            continue
        if centrato:
            if not corrente["paragrafi"] and len(corrente["intestazione"]) < 3:
                corrente["intestazione"].append(testo)  # rubrica
            continue
        corrente["paragrafi"].append((testo, _rientro(attr)))
    if corrente:
        yield corrente


def _commi_numerati(paragrafi):
    commi, atteso = [], 1
    for testo, _ in paragrafi:
        numero = _NUMERO_COMMA.match(testo)
        if numero and (int(numero.group("n")) in (atteso, atteso - 1) if numero.group("s") else int(numero.group("n")) == atteso):
            commi.append(testo)
            if not numero.group("s"):
                atteso += 1
        elif commi:
            commi[-1] = f"{commi[-1]} {testo}"
        else:
            return None  # testo prima del comma 1: struttura non certa
    return commi


def _commi_senza_numero(paragrafi):
    if not paragrafi:
        return None
    from lex.normativa.commi import _SOLO_NOTE

    rientri = [rientro for testo, rientro in paragrafi if not _SOLO_NOTE.fullmatch(testo)]
    base = min(rientri) if rientri else 0
    commi, aperto = [], False
    for testo, rientro in paragrafi:
        interno = (rientro > base or _VOCE_INTERNA.match(testo) or testo[:1].islower()
                   or _SOLO_NOTE.fullmatch(testo))
        if commi and interno:
            commi[-1] = f"{commi[-1]} {testo}"
        else:
            commi.append(testo)
        aperto = not _FINE_FRASE.search(testo)
    return commi


def commi(paragrafi):
    if paragrafi and _NUMERO_COMMA.match(paragrafi[0][0]) and int(_NUMERO_COMMA.match(paragrafi[0][0]).group("n")) == 1:
        return _commi_numerati(paragrafi)
    return _commi_senza_numero(paragrafi)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("raccolte", nargs="+")
    ap.add_argument("--atti", default="", help="data_numero separati da virgola (es. 1942-03-16_262)")
    ap.add_argument("--uscita", default=str(INDICE))
    args = ap.parse_args()
    scelti = {a.strip() for a in args.atti.split(",") if a.strip()}
    voci, fonti = {}, []
    for raccolta in args.raccolte:
        with zipfile.ZipFile(raccolta) as archivio:
            for nome in archivio.namelist():
                trovato = _NOME.search(nome)
                if not nome.endswith(".xml") or not trovato:
                    continue
                data = f"{trovato['data'][:4]}-{trovato['data'][4:6]}-{trovato['data'][6:]}"
                if scelti and f"{data}_{trovato['numero']}" not in scelti:
                    continue
                xml = archivio.read(nome).decode("utf-8", "replace")
                quanti = 0
                for art in articoli(xml):
                    divisi = commi(art["paragrafi"])
                    if divisi and len(divisi) >= 2:
                        voci[chiave(data, trovato["numero"], art["numero"])] = voce_indice(art["intestazione"], divisi)
                        quanti += 1
                fonti.append({"raccolta": Path(raccolta).name, "file": nome, "articoli_con_commi": quanti})
    uscita = Path(args.uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open if uscita.suffix == ".gz" else open)(uscita, "wt", encoding="utf-8") as file:
        json.dump({"generato_il": date.today().isoformat(), "fonti": fonti, "voci": voci}, file,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"{len(voci)} articoli con commi da {len(fonti)} atti -> {uscita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
