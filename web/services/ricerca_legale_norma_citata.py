"""Norma citata nella Ricerca legale: gli estremi scritti dall'avvocato aprono l'articolo e il comma vigenti.

Se la domanda contiene gli estremi di un atto (tipo, numero e anno; se presenti articolo e comma) l'avvocato cerca
quella norma e non altre: si legge dall'archivio Normattiva del software e la si mette in cima come «Norma citata».
Gli stessi estremi si possono indicare nei campi della ricerca per estremi. Nessuna scelta per somiglianza: se gli
estremi individuano atti diversi (stesso numero e anno, date diverse) non si propone nulla.
Base: testo vigente pubblicato da Normattiva (art. 1 D.L. 200/2008, conv. L. 9/2009; art. 107 L. 388/2000).
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote

# (espressione, prefisso del file Normattiva, sigla, tipo nella URN NIR; None se l'autorità non è univoca)
TIPI_ATTO: tuple[tuple[str, str, str, str | None], ...] = (
    (r"legge\s+costituzionale|l\.\s*cost\.", "LEGGE COSTITUZIONALE", "L. cost.", "stato:legge.costituzionale"),
    (r"d\.\s*lgs\.?|d\.lgs\.?|dlgs|decreto\s+legislativo", "DECRETO LEGISLATIVO", "D.Lgs.", "stato:decreto.legislativo"),
    (r"d\.\s*l\.|d\.l\.|decreto[\s-]legge", "DECRETO-LEGGE", "D.L.", "stato:decreto.legge"),
    (r"d\.\s*p\.\s*c\.\s*m\.?|dpcm", "DECRETO DEL PRESIDENTE DEL CONSIGLIO DEI MINISTRI", "D.P.C.M.", None),
    (r"d\.\s*p\.\s*r\.?|dpr|decreto\s+del\s+presidente\s+della\s+repubblica", "DECRETO DEL PRESIDENTE DELLA REPUBBLICA", "D.P.R.",
     "presidente.repubblica:decreto"),
    (r"r\.\s*d\.?|regio\s+decreto", "REGIO DECRETO", "R.D.", "stato:regio.decreto"),
    (r"d\.\s*m\.?|decreto\s+ministeriale", "DECRETO MINISTERIALE", "D.M.", None),
    (r"legge|l\.", "LEGGE", "L.", "stato:legge"),
)
_MESI = "gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre"
_LATINI = r"(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies)"
_TIPO = "|".join(f"(?:{espr})" for espr, *_ in TIPI_ATTO)
_ATTO_BREVE = re.compile(rf"(?<![\w.])(?P<tipo>{_TIPO})\s*(?:n\.?\s*)?(?P<numero>\d{{1,5}})\s*(?:/|\s|del\s+)\s*(?P<anno>(?:18|19|20)\d{{2}})(?!\d)",
                         re.IGNORECASE)
_ATTO_ESTESO = re.compile(rf"(?<![\w.])(?P<tipo>{_TIPO})\s+(?:del\s+)?\d{{1,2}}\s+(?:{_MESI})\s+(?P<anno>(?:18|19|20)\d{{2}}),?\s*n\.?\s*(?P<numero>\d{{1,5}})",
                          re.IGNORECASE)
_ARTICOLO = re.compile(rf"\bart(?:icolo|t?\.)?\s*(?P<articolo>\d{{1,4}}(?:\s*-?\s*{_LATINI})?)\b", re.IGNORECASE)
_COMMA = re.compile(rf"\bcomm[ai]\s*(?P<comma>\d{{1,4}}(?:\s*-?\s*{_LATINI})?)\b", re.IGNORECASE)


def _normale(valore: Any) -> str:
    return re.sub(r"[\s-]+", "", str(valore or "")).lower()


def estremi(domanda: str = "", parametri: Mapping[str, Any] | None = None) -> dict[str, str] | None:
    """Tipo, numero, anno, articolo e comma: dai campi della ricerca per estremi o dal testo della domanda."""
    parametri = parametri or {}
    tipo_scelto = str(parametri.get("atto_tipo") or "").strip().upper()
    numero, anno = str(parametri.get("atto_numero") or "").strip(), str(parametri.get("atto_anno") or "").strip()
    if tipo_scelto and numero.isdigit() and re.fullmatch(r"\d{4}", anno):
        voce = next((v for v in TIPI_ATTO if v[1] == tipo_scelto), None)
        if voce:
            return {"prefisso": voce[1], "sigla": voce[2], "urn": voce[3] or "", "numero": numero, "anno": anno,
                    "articolo": _normale(parametri.get("articolo")), "comma": _normale(parametri.get("comma"))}
    testo = " ".join(str(domanda or "").split())
    trovato = _ATTO_ESTESO.search(testo) or _ATTO_BREVE.search(testo)
    if not trovato:
        return None
    voce = next(v for v in TIPI_ATTO if re.fullmatch(v[0], trovato["tipo"], re.IGNORECASE))
    resto = testo[: trovato.start()] + " " + testo[trovato.end():]
    articolo, comma = _ARTICOLO.search(resto), _COMMA.search(resto)
    parole = " ".join(w for w in re.findall(r"[a-zà-ù]{3,}", _ARTICOLO.sub(" ", _COMMA.sub(" ", resto)).lower())
                      if w not in _VUOTE and (len(w) > 3 or w in _SIGLE_BREVI))
    return {"prefisso": voce[1], "sigla": voce[2], "urn": voce[3] or "", "numero": trovato["numero"], "anno": trovato["anno"],
            "articolo": _normale(articolo["articolo"]) if articolo else "", "comma": _normale(comma["comma"]) if comma else "",
            "parole": parole}


_SIGLE_BREVI = {"pec", "iva", "tar", "irpef"}
_VUOTE = {"legge", "decreto", "articolo", "comma", "commi", "della", "delle", "dello", "degli", "sulla", "sulle", "nella",
          "nelle", "come", "quale", "quali", "testo", "vigente", "norma", "norme", "dove", "cosa"}


def _comma_per_parole(righe: list[dict], parole: str) -> tuple[dict, str] | None:
    """Senza articolo indicato: il comma dell'atto che contiene più parole della domanda (almeno due, radici di 5 lettere)."""
    radici = {w[:5] for w in parole.split()}
    lista = [w[:5] for w in parole.split()]
    coppie = list(zip(lista, lista[1:]))
    if len(radici) < 2:
        return None
    migliore: tuple[int, int, dict, str] | None = None
    for riga in righe:
        testo = " ".join(str(riga["article_text"] or "").split())
        inizi = [m for m in _INIZIO_COMMA.finditer(testo)]
        rubrica = testo[: inizi[0].start()].lower() if inizi else ""  # «Art. 52 (Disciplina delle mansioni)»
        for i, m in enumerate(inizi):
            pezzo = testo[m.start(): inizi[i + 1].start() if i + 1 < len(inizi) else len(testo)].lower()
            punti = sum(1 for r in radici if r in pezzo) + 2 * sum(1 for r in radici if r in rubrica) + sum(
                1 for a, b in coppie if re.search(rf"\b{a}\w*\s+(?:\w+\s+)?{b}", pezzo))
            if punti >= 2 and (migliore is None or punti > migliore[0]):
                migliore = (punti, -len(pezzo), riga, _normale(m[1]))
    return (migliore[2], migliore[3]) if migliore else None


def _documento(conn: sqlite3.Connection, e: Mapping[str, str]) -> dict | None:
    conn.row_factory = sqlite3.Row
    righe = [dict(r) for r in conn.execute(
        "SELECT id, numero, data_atto, titolo, vigenza, xml_entry FROM normative_documents "
        "WHERE numero=? AND data_atto>=? AND data_atto<? AND xml_entry LIKE ? ESCAPE '\\'",
        (e["numero"], f"{e['anno']}-01-01", f"{int(e['anno']) + 1}-01-01", e["prefisso"].replace("_", "\\_") + "\\_%"))]
    if len({r["data_atto"] for r in righe}) != 1:
        return None  # nessun atto o atti diversi con lo stesso numero e anno: non si sceglie
    return max(righe, key=lambda r: ((r.get("vigenza") or "").upper() == "VIGENTE", _vigenza_file(r), r["id"]))


def _vigenza_file(documento: Mapping[str, Any]) -> str:
    trovata = re.search(r"VIGENZA_(\d{4}-\d{2}-\d{2})", str(documento.get("xml_entry") or ""))
    return trovata[1] if trovata else ""


def _numero_articolo(etichetta: str) -> tuple[str, tuple[int, int] | None]:
    trovato = re.match(rf"\s*art(?:icolo|\.)?\s*(\d{{1,4}}(?:\s*-?\s*{_LATINI})?)", etichetta or "", re.IGNORECASE)
    commi = re.search(r"\(commi\s+(\d+)\s*-\s*(\d+)\)", etichetta or "", re.IGNORECASE)
    return (_normale(trovato[1]) if trovato else "", (int(commi[1]), int(commi[2])) if commi else None)


_INIZIO_COMMA = re.compile(rf"(?<![\w,./'’])(\d{{1,4}}(?:-?{_LATINI})?)\.\s+(?=[A-ZÀ-Ý«\"(])")


def _leggibile(numero: str) -> str:
    """«2bis» -> «2-bis», come si cita in atti."""
    return re.sub(rf"^(\d+)({_LATINI})$", r"\1-\2", numero or "")


def _art(e: Mapping[str, str]) -> str:
    return "la" if e["sigla"].startswith("L.") else "il"


def _di(e: Mapping[str, str]) -> str:
    return "della" if _art(e) == "la" else "del"


def _intero(valore: str) -> int:
    cifre = re.match(r"\d+", valore or "")
    return int(cifre[0]) if cifre else 0


def testo_del_comma(testo: str, comma: str) -> str:
    """Il comma dal suo numero fino al comma successivo (numerazione «121.», «121-bis.» del testo Normattiva)."""
    testo = " ".join(str(testo or "").split())
    inizio = next((m for m in _INIZIO_COMMA.finditer(testo) if _normale(m[1]) == comma), None)
    if inizio is None:
        return ""
    fine = next((m.start() for m in _INIZIO_COMMA.finditer(testo, inizio.end()) if _normale(m[1]) != comma
                 and _intero(m[1]) >= _intero(comma)), len(testo))
    return testo[inizio.start():fine].strip()[:6000]


def _articolo(conn: sqlite3.Connection, documento_id: int, e: Mapping[str, str]) -> dict | None:
    righe = [dict(r) for r in conn.execute(
        "SELECT id, article_number, article_text, article_key FROM normative_articles WHERE document_id=? ORDER BY id", (documento_id,))]
    if not e["articolo"]:
        return righe[0] if righe else None
    return _articolo_indicato(righe, e)


def _articolo_indicato(righe: list[dict], e: Mapping[str, str]) -> dict | None:
    candidati = [r for r in righe if _numero_articolo(r["article_number"])[0] == e["articolo"]]
    if e["comma"].isdigit():
        n = int(e["comma"])
        partizione = next((r for r in candidati if (_numero_articolo(r["article_number"])[1] or (0, 10**6))[0] <= n
                           <= (_numero_articolo(r["article_number"])[1] or (0, 10**6))[1] and testo_del_comma(r["article_text"], e["comma"])), None)
        if partizione:
            return partizione
    return candidati[0] if candidati else None


def _url(e: Mapping[str, str], documento: Mapping[str, Any]) -> str:
    if not e["urn"]:
        return ""
    urn = f"urn:nir:{e['urn']}:{documento['data_atto']};{e['numero']}" + (f"~art{e['articolo']}" if e["articolo"] else "")
    return "https://www.normattiva.it/uri-res/N2Ls?" + quote(urn, safe=":;.~-")


def norma_citata(db: Path, e: Mapping[str, str]) -> dict[str, Any] | None:
    """La scheda della norma citata, letta dall'archivio; None se gli estremi non individuano una norma sola."""
    if not db.is_file():
        return None
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5) as conn:
        documento = _documento(conn, e)
        if documento is None:
            return _assente(conn, e)
        e = dict(e)
        articolo = None
        if not e["articolo"] and e.get("parole"):
            righe = [dict(r) for r in conn.execute(
                "SELECT id, article_number, article_text, article_key FROM normative_articles WHERE document_id=? ORDER BY id", (documento["id"],))]
            trovato = _comma_per_parole(righe, e["parole"])
            if trovato:
                articolo, e["comma"] = trovato
                e["articolo"] = _numero_articolo(articolo["article_number"])[0]
                e["dedotto"] = "1"
        articolo = articolo or _articolo(conn, documento["id"], e)
        if articolo is None:
            return None
        comma = testo_del_comma(articolo["article_text"], e["comma"]) if e["comma"] else ""
        testo = comma or " ".join(str(articolo["article_text"] or "").split())[:6000]
        chunk = conn.execute(
            "SELECT chunk_key FROM normative_chunks WHERE article_id=? AND instr(chunk_text, ?) > 0 ORDER BY id LIMIT 1",
            (articolo["id"], testo[:40])).fetchone() or conn.execute(
            "SELECT chunk_key FROM normative_chunks WHERE article_id=? ORDER BY id LIMIT 1", (articolo["id"],)).fetchone()
    estremi_atto = f"{e['sigla']} {e['numero']}/{e['anno']}"
    rif = (f"art. {_leggibile(e['articolo'])}" if e["articolo"] else "") + (f", comma {_leggibile(e['comma'])}" if comma else "")
    vigenza = _vigenza_file(documento)
    vigente = (documento.get("vigenza") or "").upper() == "VIGENTE"
    nota = (f"Testo vigente nell'archivio Normattiva del software (aggiornamento del {vigenza[8:]}/{vigenza[5:7]}/{vigenza[:4]})."
            if vigente and vigenza else "Testo dell'archivio Normattiva del software: verificare la vigenza sulla fonte originale.")
    avvisi = [nota]
    if e.get("dedotto"):
        avvisi.append(f"Articolo e comma individuati dalle parole della domanda nel testo {_di(e)} {estremi_atto}: verificare che siano quelli cercati.")
    if e["comma"] and not comma:
        avvisi.append(f"Comma {e['comma']} non individuato nel testo: si mostra l'articolo intero.")
    estratto = testo[:640]
    return {
        "id": (chunk[0] if chunk else "") or f"norma-citata:{documento['id']}:{articolo['id']}",
        "normaCitata": True,
        "officialContext": testo,
        "nativeArticleTextVerified": False,
        "nativeArticleIdentity": "",
        "kind": "normativa",
        "title": f"{estremi_atto}{' — ' + rif if rif else ''} — {str(documento.get('titolo') or '').strip()}"[:300],
        "subtitle": estratto,
        "sourceExcerpt": estratto,
        "sourceLabel": "Normattiva",
        "sourceKind": "fonte ufficiale",
        "sourceHref": _url(e, documento),
        "date": str(documento.get("data_atto") or ""),
        "area": "Normativa",
        "branch": "Norma citata · Archivio Normattiva",
        "approvalLabel": "norma citata" if vigente else "verificare vigenza",
        "approvalTone": "success" if vigente else "warning",
        "registryNumber": rif or estremi_atto,
        "legacyHref": "/ricerca-legale",
        "evidenceType": "testo della norma citata",
        "contextCompleted": True,
        "contextSummary": testo,
        "keyPoints": [f"{estremi_atto}{', ' + rif if rif else ''}: {estratto}"],
        "operationalChecks": avvisi,
    }


def _assente(conn: sqlite3.Connection, e: Mapping[str, str]) -> dict[str, Any] | None:
    """L'atto non è nell'archivio: lo si dice, con il collegamento a Normattiva, invece di mostrare norme estranee."""
    if conn.execute("SELECT 1 FROM normative_documents WHERE numero=? AND data_atto>=? AND data_atto<? LIMIT 1",
                    (e["numero"], f"{e['anno']}-01-01", f"{int(e['anno']) + 1}-01-01")).fetchone() and not e["urn"]:
        return None
    estremi_atto = f"{e['sigla']} {e['numero']}/{e['anno']}"
    rif = (f"art. {_leggibile(e['articolo'])}" if e["articolo"] else "") + (f", comma {_leggibile(e['comma'])}" if e["comma"] else "")
    urn = f"urn:nir:{e['urn']}:{e['anno']};{e['numero']}" + (f"~art{e['articolo']}" if e["articolo"] else "") if e["urn"] else ""
    avviso = (f"{_art(e).capitalize()} {estremi_atto} non è nell'archivio Normattiva del software: il testo vigente si apre su Normattiva "
              "e l'atto è segnalato per l'acquisizione.")
    return {
        "id": f"norma-citata-assente:{e['prefisso']}:{e['numero']}:{e['anno']}", "normaCitata": True, "normaAssente": True,
        "officialContext": "", "nativeArticleTextVerified": False, "nativeArticleIdentity": "", "kind": "normativa",
        "title": f"{estremi_atto}{' — ' + rif if rif else ''} — non presente nell'archivio del software",
        "subtitle": avviso, "sourceExcerpt": "", "sourceLabel": "Normattiva", "sourceKind": "fonte ufficiale",
        "sourceHref": "https://www.normattiva.it/uri-res/N2Ls?" + quote(urn, safe=":;.~-") if urn else "",
        "date": "", "area": "Normativa", "branch": "Norma citata · da acquisire", "approvalLabel": "da acquisire",
        "approvalTone": "warning", "registryNumber": rif or estremi_atto, "legacyHref": "/ricerca-legale",
        "evidenceType": "riferimento fonte ufficiale", "contextCompleted": False, "contextSummary": avviso,
        "keyPoints": [], "operationalChecks": [avviso],
    }


def in_cima(records: list[dict[str, Any]], domanda: str, parametri: Mapping[str, Any] | None = None, *, db: Path | None = None) -> list[dict[str, Any]]:
    """Mette la norma citata per prima; gli altri risultati restano nell'ordine della ricerca."""
    e = estremi(domanda, parametri)
    if not e:
        return records
    if db is None:
        from lex.retrieval.normativa_catalog import runtime_general_path

        db = runtime_general_path()
    try:
        scheda = norma_citata(Path(db), e)
    except sqlite3.Error:
        return records
    if not scheda:
        return records
    return [scheda] + [r for r in records if r.get("id") != scheda["id"]]


__all__ = ["TIPI_ATTO", "estremi", "in_cima", "norma_citata", "testo_del_comma"]
