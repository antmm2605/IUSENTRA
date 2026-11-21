"""Indice dei commi dagli Akoma Ntoso di Normattiva (esportazione «caricaAKN» dell'atto vigente).

Uso: python scripts/normativa_commi_da_akn.py FILE.xml [FILE.xml ...] [--uscita FILE] [--unisci FILE]

Due forme dell'esportazione ufficiale:
- leggi e decreti con ``article``/``paragraph``: ogni ``paragraph`` è un comma (con elenchi e lettere dentro);
- codici con il testo nel ``mainBody``: ogni articolo è un blocco «Art. N.» e i commi sono separati da una riga
  vuota; le voci «1)», «a)» restano nel comma che le introduce.
Nella Costituzione i commi di un articolo sono righe distinte dello stesso paragrafo.
Le note (righe di trattini, «AGGIORNAMENTO») non fanno parte del corpo. Si salva solo dove inizia ogni comma e
l'impronta del testo (``lex/normativa/commi.py``).
"""
from __future__ import annotations

import argparse
import gzip
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from defusedxml import ElementTree as ET  # noqa: E402

from lex.normativa.commi import INDICE, chiave, raggruppa_commi, voce_indice  # noqa: E402

NS = {"a": "http://docs.oasis-open.org/legaldocml/ns/akn/3.0"}
_A = "{http://docs.oasis-open.org/legaldocml/ns/akn/3.0}"
_ART = re.compile(r"^\s*Art(?:icolo)?\.?\s*(?P<n>\d+(?:[\s.-]*[a-z]+)?(?:\.\d+)?)\s*\.?\s*$", re.I)
_NOTA = re.compile(r"^\s*(?:-{5,}|AGGIORNAMENTO\b)")


def _testo(elemento) -> str:
    return "".join(elemento.itertext())


def _riga(testo: str) -> str:
    return " ".join(html.unescape(testo).split())


def _identita(radice) -> tuple[str, str]:
    this = radice.find(".//a:FRBRWork/a:FRBRthis", NS)
    valore = this.get("value") if this is not None else ""
    trovato = re.search(r"/(\d{4}-\d{2}-\d{2})/(\d+)/", valore or "")
    if not trovato:
        data = radice.find(".//a:FRBRWork/a:FRBRdate", NS)
        numero = radice.find(".//a:FRBRWork/a:FRBRnumber", NS)
        return (data.get("date") if data is not None else ""), (numero.get("value") if numero is not None else "")
    return trovato.group(1), trovato.group(2)


def _articoli_strutturati(radice, costituzione: bool):
    for articolo in radice.iter(f"{_A}article"):
        numero = articolo.find("a:num", NS)
        rubrica = articolo.find("a:heading", NS)
        intestazione = [_riga(_testo(numero))] if numero is not None else []
        if rubrica is not None and _riga(_testo(rubrica)):
            intestazione.append(_riga(_testo(rubrica)))
        paragrafi = [p for p in articolo if p.tag == f"{_A}paragraph"]
        # Un solo paragrafo senza numero (Costituzione, leggi meno recenti): i commi sono le sue righe.
        if len(paragrafi) == 1 and paragrafi[0].find("a:num", NS) is None:
            righe = [r for r in (_riga(x) for x in _testo(paragrafi[0]).split("\n")) if r]
        else:
            righe = [_riga(_testo(p)) for p in paragrafi]
        corpo = []
        for riga in righe:
            if _NOTA.match(riga):
                break
            corpo.append(riga)
        m = _ART.match(intestazione[0]) if intestazione else None
        if m:
            yield m.group("n"), intestazione, raggruppa_commi(corpo)


def _articoli_nel_corpo(radice):
    # Il decreto di approvazione e il codice allegato hanno ciascuno il proprio mainBody.
    for p in (p for corpo in radice.iter(f"{_A}mainBody") for p in corpo.iter(f"{_A}p")):
        testo = html.unescape(_testo(p))
        blocchi = [b for b in re.split(r"\n[ \t]*\n", testo) if b.strip()]
        if not blocchi:
            continue
        righe_intestazione = [_riga(r) for r in blocchi[0].split("\n") if r.strip()]
        m = _ART.match(righe_intestazione[0]) if righe_intestazione else None
        if not m:
            continue
        intestazione = righe_intestazione[:2]
        resto = righe_intestazione[2:]
        commi = []
        for blocco in ([" ".join(resto)] if resto else []) + blocchi[1:]:
            riga = _riga(blocco)
            if _NOTA.match(riga):
                break
            # La rubrica «(Saggio degli interessi).» può stare in un blocco a sé: è intestazione, non comma.
            if not commi and len(intestazione) == 1 and re.fullmatch(r"\(.*\)\.?", riga):
                intestazione.append(riga)
                continue
            commi.append(riga)
        yield m.group("n"), intestazione, raggruppa_commi(commi)


def leggi(percorso: Path) -> tuple[tuple[str, str], list]:
    radice = ET.parse(percorso).getroot()
    this = radice.find(".//a:FRBRWork/a:FRBRthis", NS)
    costituzione = "costituzione" in ((this.get("value") if this is not None else "") or "")
    data, numero = ("1947-12-27", "") if costituzione else _identita(radice)
    # Nei codici gli articoli stanno nel corpo («Art. N.» e commi separati da righe vuote); gli «article»
    # strutturati sono gli articoli del decreto di approvazione: valgono solo per i numeri non presenti nel corpo.
    articoli = {numero_art: (numero_art, intestazione, commi) for numero_art, intestazione, commi in _articoli_nel_corpo(radice)}
    for numero_art, intestazione, commi in _articoli_strutturati(radice, costituzione):
        articoli.setdefault(numero_art, (numero_art, intestazione, commi))
    return (data, numero), list(articoli.values())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="+")
    ap.add_argument("--uscita", default=str(INDICE))
    ap.add_argument("--unisci", default="", help="indice esistente da completare (le voci AKN prevalgono)")
    args = ap.parse_args()
    voci, fonti = {}, []
    if args.unisci and Path(args.unisci).is_file():
        with gzip.open(args.unisci, "rt", encoding="utf-8") as file:
            precedente = json.load(file)
        voci.update(precedente.get("voci", {}))
        fonti.extend(precedente.get("fonti", []))
    for nome in args.file:
        (data, numero), articoli = leggi(Path(nome))
        quanti = 0
        for articolo, intestazione, commi in articoli:
            if len(commi) >= 2:
                voci[chiave(data, numero, articolo)] = voce_indice(intestazione, commi)
                quanti += 1
        fonti.append({"file": Path(nome).name, "atto": f"{data}/{numero}", "articoli_con_commi": quanti,
                      "formato": "Akoma Ntoso Normattiva (caricaAKN)"})
        print(f"{Path(nome).name}: {data} n. {numero}, {quanti} articoli con commi", flush=True)
    uscita = Path(args.uscita)
    uscita.parent.mkdir(parents=True, exist_ok=True)
    with (gzip.open if uscita.suffix == ".gz" else open)(uscita, "wt", encoding="utf-8") as file:
        json.dump({"generato_il": date.today().isoformat(), "fonti": fonti, "voci": voci}, file,
                  ensure_ascii=False, separators=(",", ":"))
    print(f"{len(voci)} articoli con commi -> {uscita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
