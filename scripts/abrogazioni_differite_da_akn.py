"""Indice delle abrogazioni con efficacia differita, dagli Akoma Ntoso vigenti dei testi unici (Normattiva).

Uso: python scripts/abrogazioni_differite_da_akn.py --db codici_leggi.sqlite --proroga dl200_2025.xml \\
        --uscita lex/normativa/dati/abrogazioni_differite.json TU.xml [TU.xml ...]

Per ogni testo unico si leggono dal testo ufficiale:
- l'articolo «Decorrenza» («Le disposizioni del presente testo unico si applicano [a decorrere] dal …»);
- gli articoli «Abrogazioni» («A decorrere dalla data di cui all'articolo N sono abrogate …»), lettera per lettera:
  atto citato, articoli (anche «da X a Y», con l'ordine degli articoli letto dalla biblioteca), commi abrogati;
- la corrispondenza dall'intestazione degli articoli del testo unico («( articolo 21 decreto del Presidente della
  Repubblica 29 settembre 1973, n. 602 )»).
Dal decreto di proroga (d.l. 200/2025) si legge quale comma ha spostato la decorrenza di ciascun testo unico.
Una lettera che non si riesce a leggere con certezza resta fuori dall'indice e compare nel rapporto.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

RADICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RADICE))

from lex.normativa.commi import chiave  # noqa: E402

MESI = {m: i for i, m in enumerate(("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                    "settembre", "ottobre", "novembre", "dicembre"), 1)}
TIPI = r"decreto del Presidente della Repubblica|decreto legislativo|decreto-legge|legge|regio decreto"
CITAZIONE = re.compile(rf"({TIPI})\s+(\d{{1,2}})°?\s+(\w+)\s+(\d{{4}}),\s*n\.\s*(\d+)")
CITAZIONE_BREVE = re.compile(rf"({TIPI})\s+n\.\s*(\d+)\s+del\s+(\d{{4}})")
SIGLE = {"decreto del Presidente della Repubblica": "d.P.R.", "decreto legislativo": "d.lgs.", "decreto-legge": "d.l.",
         "legge": "l.", "regio decreto": "r.d."}


def testo_piatto(xml: Path) -> str:
    grezzo = xml.read_text(encoding="utf-8", errors="replace")
    corpo = grezzo[grezzo.find("<body"):] if "<body" in grezzo else grezzo
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", corpo)).replace("((", "").replace("))", "")


def articoli_tu(testo: str) -> list[tuple[str, str]]:
    """(numero, testo) di ogni articolo del testo unico, dalle intestazioni «ART. N» / «Art. N.»."""
    posizioni = [(m.start(), m.group(1)) for m in re.finditer(r"\b(?:ART\.|Art\.) (\d+(?:-[a-z]+)?)\.? (?=[A-Z(])", testo)]
    return [(n, testo[p:(posizioni[i + 1][0] if i + 1 < len(posizioni) else len(testo))]) for i, (p, n) in enumerate(posizioni)]


def _data(giorno: str, mese: str, anno: str) -> str:
    """Data ISO della citazione; stringa vuota se il mese è scritto male nella fonte (per esempio «decembre»)."""
    return f"{anno}-{MESI[mese.lower()]:02d}-{int(giorno):02d}" if mese.lower() in MESI else ""


def ordine_articoli(db: sqlite3.Connection, data: str, numero: str) -> list[str]:
    """Gli articoli dell'atto nell'ordine della fonte (edizione più recente della biblioteca)."""
    riga = db.execute("SELECT id FROM normative_documents WHERE data_atto=? AND numero=? ORDER BY redazione_id DESC, id DESC "
                      "LIMIT 1", (data, numero)).fetchone()
    if not riga:
        return []
    return [str(r[0]) for r in db.execute("SELECT article_number FROM normative_articles WHERE document_id=? ORDER BY id",
                                          (riga[0],))]


def _norm(n: str) -> str:
    return re.sub(r"[\s.\-]", "", re.sub(r"^art(?:icolo)?\.?\s*", "", str(n).strip().lower()))


def leggi_specifica(spec: str, ordine: list[str]) -> list[tuple[str, str]] | None:
    """«articoli da 1 a 17, da 17-ter a 27, 30» → [(articolo, commi abrogati o "")]; None se non è certa."""
    spec = re.sub(r"\b(?:gli|la|il|i|del|della|dei|delle)\b|\bl['’]", " ", spec)
    spec = re.sub(r"\barticol[oi]\b", " ", spec)
    spec = re.sub(r"\s+", " ", spec).strip(" ,;")
    if not spec:
        return []
    norm_ordine = [_norm(a) for a in ordine]
    esito: list[tuple[str, str]] = []
    pezzi = [p.strip() for p in re.split(r",|\be\b", spec) if p.strip()]
    commi_di: str | None = None
    for pezzo in pezzi:
        intervallo = re.fullmatch(r"da (\d+(?:-[a-z]+)?) a (\d+(?:-[a-z]+)?)", pezzo)
        if commi_di is not None and (re.fullmatch(r"(?:da )?\d+(?:-[a-z]+)?(?: a \d+(?:-[a-z]+)?)?", pezzo)
                                     or re.fullmatch(r"[a-z]+", pezzo)):  # «commi quarto e quinto»
            esito[-1] = (esito[-1][0], f"{esito[-1][1]}, {pezzo}")
            continue
        if re.match(r"comm[ai]\b", pezzo):
            if not esito:
                return None
            esito[-1] = (esito[-1][0], pezzo)
            commi_di = esito[-1][0]
            continue
        if re.search(r"\bcomma\b", pezzo) or re.search(r"\bperiod", pezzo):  # «nono comma», «primo periodo»
            if not esito:
                return None
            esito[-1] = (esito[-1][0], f"{esito[-1][1]} {pezzo}".strip())
            continue
        commi_di = None
        if intervallo:
            a, b = _norm(intervallo.group(1)), _norm(intervallo.group(2))
            if a not in norm_ordine or b not in norm_ordine:
                return None
            esito += [(ordine[i], "") for i in range(norm_ordine.index(a), norm_ordine.index(b) + 1)]
            continue
        if re.fullmatch(r"\d+(?:-[a-z]+)?", pezzo):
            esito.append((pezzo, ""))
            continue
        if re.match(r"(tabell|allegat|tariff|prospett)", pezzo):
            continue  # tabelle e allegati: non sono articoli
        return None
    return [(a, (("commi " if c and not c.startswith(("comma", "commi")) and not re.search(r"\bcomma\b", c) else "") + c).strip())
            for a, c in esito]


def abrogazioni(testo_articolo: str, db: sqlite3.Connection) -> tuple[list[dict], list[str]]:
    corpo = testo_articolo.split(" 2. Restano abrogate")[0]
    corpo = corpo[corpo.find(":") + 1:] if ":" in corpo else corpo
    lettere = re.split(r"(?:^|;)\s*[a-z]{1,4}\)\s", corpo)
    voci, scartate = [], []
    for lettera in (x.strip(" ;.") for x in lettere):
        if not lettera or "ABROGATA" in lettera:
            continue
        citazione = CITAZIONE.search(lettera)
        if not citazione:
            scartate.append(lettera[:160])
            continue
        tipo, g, m, anno, numero = citazione.groups()
        data = _data(g, m, anno)
        if not data:
            scartate.append(lettera[:160])
            continue
        spec = lettera[:citazione.start()]
        spec = re.sub(r"(?:del|della|il|la)\s*$", "", spec.strip()).strip()
        if not re.search(r"\d", spec):
            # L'atto intero: tutti i suoi articoli, più la voce «*» per gli articoli che la biblioteca non ha.
            articoli = [(a, "") for a in ordine_articoli(db, data, numero)] + [("*", "")]
            intero = True
        else:
            articoli = leggi_specifica(spec, ordine_articoli(db, data, numero))
            intero = False
        if articoli is None:
            scartate.append(lettera[:160])
            continue
        voci.append({"tipo": tipo, "data": data, "numero": numero, "articoli": articoli, "intero": intero,
                     "estremi": f"{SIGLE[tipo]} {int(g)} {m} {anno}, n. {numero}"})
    return voci, scartate


def corrispondenze(articoli: list[tuple[str, str]], date_per_atto: dict[tuple[str, str], str]) -> dict[str, list[str]]:
    """chiave dell'articolo abrogato → articoli del testo unico che lo riprendono (dall'intestazione)."""
    esito: dict[str, list[str]] = {}
    for numero_tu, testo in articoli:
        fonte = re.match(r"[^()]{0,200}?\(\s*(articol[^)]{3,600})\)", testo[len("ART. ") + len(numero_tu):])
        if not fonte:
            continue
        for segmento in fonte.group(1).split(";"):
            citazione = CITAZIONE.search(segmento)
            if citazione:
                tipo, g, m, anno, numero = citazione.groups()
                data = _data(g, m, anno)
                if not data:
                    continue
            else:
                breve = CITAZIONE_BREVE.search(segmento)
                if not breve:
                    continue
                numero, anno = breve.group(2), breve.group(3)
                data = date_per_atto.get((numero, anno))
                if not data:
                    continue
                citazione = breve
            spec = segmento[:citazione.start()]
            for art in re.findall(r"articol[oi] (\d+(?:-[a-z]+)?)", spec):
                esito.setdefault(chiave(data, numero, art), []).append(f"art. {numero_tu}")
    return esito


def proroghe(xml: Path) -> dict[str, str]:
    """Numero del testo unico (d.lgs.) → «art. 4, comma N, del d.l. …» che ne ha spostato la decorrenza."""
    testo = testo_piatto(xml)
    articolo = re.search(r"Art\. 4\. Proroga di termini in materie di competenza del Ministero dell'economia(.{0,6000})", testo)
    esito = {}
    for comma, art, numero in re.findall(r"(\d+)\. All'?\s*articolo (\d+), comma 1, del testo unico [^;]{0,300}?decreto legislativo "
                                        r"\d{1,2}°? \w+ \d{4}, n\. (\d+) , le parole: «1° gennaio 2026» sono sostituite dalle "
                                        r"seguenti: «1° gennaio 2027»", articolo.group(1) if articolo else ""):
        esito[numero] = f"art. 4, comma {comma}, del d.l. 31 dicembre 2025, n. 200, convertito, con modificazioni, dalla l. 27 febbraio 2026, n. 26"
    return esito


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True)
    ap.add_argument("--proroga", required=True)
    ap.add_argument("--uscita", required=True)
    ap.add_argument("--verificato-il", default="2026-11-21")
    ap.add_argument("tu", nargs="+")
    args = ap.parse_args()
    db = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    rinvii = proroghe(Path(args.proroga))
    indice: dict = {"verificato_il": args.verificato_il, "fonte": "Normattiva, Akoma Ntoso vigenti al " + args.verificato_il,
                    "atti_abroganti": {}, "voci": {}, "non_lette": []}
    for nome in args.tu:
        xml = Path(nome)
        testo = testo_piatto(xml)
        urn = re.search(r'FRBRalias[^>]*value="urn:nir:stato:decreto\.legislativo:(\d{4})-(\d{2})-(\d{2});(\d+)"',
                        xml.read_text(encoding="utf-8", errors="replace"))
        anno, mm, gg, numero_tu = urn.groups()
        g, m = str(int(gg)), next(k for k, v in MESI.items() if v == int(mm))
        titolo = re.search(r"(Testo unico[^.(]{3,160})", xml.read_text(encoding="utf-8", errors="replace"))
        articoli = articoli_tu(testo)
        decorrenza_art, decorrenza_testo = next(((n, t) for n, t in articoli if re.match(rf"(?:ART\.|Art\.) {n}\.? Decorrenza \d", t)), ("", ""))
        dal_testo = re.search(r"si applicano (?:a decorrere )?dal (\d{1,2})° (\w+) (\d{4})", decorrenza_testo)
        if not dal_testo:
            indice["non_lette"].append(f"{xml.name}: decorrenza non letta")
            continue
        dal = _data(*dal_testo.groups())
        sigla = f"d.lgs. {'1°' if g == '1' else g} {m} {anno}, n. {numero_tu}"
        indice["atti_abroganti"][sigla] = {
            "estremi": f"{sigla} ({titolo.group(1).strip()})" if titolo else sigla,
            "decorrenza": f"art. {decorrenza_art}, comma 1, {sigla}" + (f", come modificato dall'{rinvii[numero_tu]}" if numero_tu in rinvii else ""),
            "dal": dal,
            "url": f"https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:decreto.legislativo:{anno}-{MESI[m.lower()]:02d}-{int(g):02d};{numero_tu}",
        }
        date_per_atto: dict[tuple[str, str], str] = {}
        tutte = []
        for n, t in articoli:
            if re.match(rf"(?:ART\.|Art\.) {n}\.? Abrogazion", t) and "dalla data" in t[:300].lower():
                voci, scartate = abrogazioni(t, db)
                tutte += [(n, v) for v in voci]
                indice["non_lette"] += [f"{sigla}, art. {n}: {s}" for s in scartate]
                for v in voci:
                    date_per_atto[(v["numero"], v["data"][:4])] = v["data"]
        corr = corrispondenze(articoli, date_per_atto)
        for n_abrogante, voce in tutte:
            for articolo, commi in voce["articoli"]:
                k = chiave(voce["data"], voce["numero"], articolo)
                indice["voci"][k] = {"abrogante": sigla, "articolo_abrogante": f"art. {n_abrogante}", "dal": dal,
                                     "parziale": commi, "atto": voce["estremi"], "articolo": articolo,
                                     "corrispondenti": sorted(set(corr.get(k, [])), key=lambda x: int(re.sub(r"\D.*", "", x[5:]) or 0))}
        print(f"{sigla}: dal {dal}, {sum(len(v['articoli']) for _, v in tutte)} articoli abrogati, "
              f"{len(corr)} corrispondenze", flush=True)
    Path(args.uscita).write_text(json.dumps(indice, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(indice['voci'])} voci, {len(indice['non_lette'])} lettere non lette -> {args.uscita}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
