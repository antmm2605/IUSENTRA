"""Testo di un articolo e di una sentenza precisa: dagli archivi ufficiali locali.

Quando l'avvocato chiede il testo di un articolo («art. 2043 c.c.», «art. 3-bis
L. 53/1994») o una sentenza precisa («Cass. n. 12345/2023»), Lex non lo chiede
a un modello linguistico e non lo ricostruisce a memoria:

* l'articolo si legge dall'archivio Normattiva locale (``normattiva.sqlite``),
  alimentato ogni notte dalle raccolte ufficiali di Normattiva (Codici e leggi
  fondamentali dello studio). Si riporta il testo come importato, con l'URN,
  il collegamento ufficiale all'articolo e la data dell'importazione;
* la sentenza si cerca nell'archivio giurisprudenza dello studio, alimentato
  dalle fonti ufficiali (Corte di cassazione, Corte costituzionale, giustizia
  amministrativa…): numero e anno devono coincidere. Si riportano massima o
  principio di diritto come registrati, con il collegamento alla pagina ufficiale
  e lo stato di verifica della fonte.

Se l'articolo o la sentenza non sono negli archivi, Lex lo dice e indica dove
leggerli sulla fonte ufficiale: non inventa il contenuto.

Base: D.P.R. 1092/1985 e L. 69/2009 art. 1 (Normattiva e pubblicità legale dei
testi normativi); art. 2 D.Lgs. 82/2005 (CAD); regola delle fonti certe (CLAUDE.md).
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable

NORMATTIVA_URI = "https://www.normattiva.it/uri-res/N2Ls?"
SENTENZEWEB = "https://www.italgiure.giustizia.it/sncass/"

_SUFFISSI = (
    "bis", "ter", "quater", "quinquies", "sexies", "septies", "octies", "novies", "nonies",
    "decies", "undecies", "duodecies", "terdecies", "quaterdecies", "quinquiesdecies",
    "sexiesdecies", "septiesdecies", "octiesdecies",
)
_SUFFISSO_RE = "|".join(sorted(_SUFFISSI, key=len, reverse=True))


@dataclass(frozen=True)
class Codice:
    chiave: str
    etichetta: str
    urn: str
    sinonimi: tuple[str, ...]


# URN NIR dei codici (Normattiva). L'ordine conta: le sigle più lunghe prima.
CODICI: tuple[Codice, ...] = (
    Codice("disp_att_cpc", "disposizioni di attuazione del c.p.c.", "urn:nir:stato:regio.decreto:1941-12-18;1368",
           ("disp. att. c.p.c.", "disp att cpc", "disposizioni di attuazione del codice di procedura civile")),
    Codice("disp_att_cpp", "norme di attuazione del c.p.p.", "urn:nir:stato:decreto.legislativo:1989-07-28;271",
           ("disp. att. c.p.p.", "disp att cpp", "norme di attuazione del codice di procedura penale")),
    Codice("cpc", "codice di procedura civile", "urn:nir:stato:regio.decreto:1940-10-28;1443",
           ("c.p.c.", "cpc", "codice di procedura civile", "cod. proc. civ.")),
    Codice("cpp", "codice di procedura penale", "urn:nir:presidente.repubblica:decreto:1988-09-22;447",
           ("c.p.p.", "cpp", "codice di procedura penale", "cod. proc. pen.")),
    Codice("cc", "codice civile", "urn:nir:stato:regio.decreto:1942-03-16;262",
           ("c.c.", "cc", "codice civile", "cod. civ.")),
    Codice("cp", "codice penale", "urn:nir:stato:regio.decreto:1930-10-19;1398",
           ("c.p.", "cp", "codice penale", "cod. pen.")),
    Codice("cost", "Costituzione", "urn:nir:stato:costituzione:1947-12-27",
           ("cost.", "costituzione", "della costituzione")),
)

_URN_CODICE_CIVILE = next(c.urn for c in CODICI if c.chiave == "cc")

# Tipi di atto: sigla scritta dall'avvocato → parte dell'URN NIR.
TIPI_ATTO: tuple[tuple[str, str, str], ...] = (
    (r"d\.?\s?lgs\.?|decreto legislativo", "decreto.legislativo", "D.Lgs."),
    (r"d\.?\s?l\.?|decreto[- ]legge", "decreto.legge", "D.L."),
    (r"d\.?\s?p\.?\s?r\.?|decreto del presidente della repubblica", "presidente.repubblica:decreto", "D.P.R."),
    (r"d\.?\s?m\.?|decreto ministeriale", "ministero", "D.M."),
    (r"l\.|legge", "stato:legge", "L."),
)


@dataclass(frozen=True)
class RichiestaArticolo:
    numero: str          # «2043», «3-bis»
    chiave: str          # «2043», «3bis» (per il confronto)
    etichetta_atto: str  # «codice civile», «L. 53/1994»
    urn: str             # URN esatto (codici) o vuoto
    urn_parti: tuple[str, str, str] = ("", "", "")  # (tipo, anno, numero) per le leggi

    @property
    def citazione(self) -> str:
        return f"art. {self.numero} {self.etichetta_atto}"

    def collegamento(self, urn: str = "") -> str:
        base = urn or self.urn
        if not base:
            return "https://www.normattiva.it/"
        return f"{NORMATTIVA_URI}{base}~art{self.chiave}"


@dataclass(frozen=True)
class RichiestaSentenza:
    organo: str   # «cassazione», «costituzionale», «consiglio di stato», ""
    numero: str
    anno: str

    @property
    def citazione(self) -> str:
        nomi = {"cassazione": "Cass.", "costituzionale": "Corte cost.", "consiglio di stato": "Cons. Stato"}
        prefisso = nomi.get(self.organo, "Sentenza")
        return f"{prefisso} n. {self.numero}/{self.anno}"


def _norm(testo: str) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "").lower())
    return "".join(c for c in base if not unicodedata.combining(c)).replace("’", "'")


def chiave_articolo(numero: str) -> str:
    """«Art. 3-bis.» → «3bis»; «2043» → «2043». Vuota se non è un numero di articolo."""
    testo = _norm(numero)
    m = re.search(rf"(\d+)\s*[-\s]?\s*({_SUFFISSO_RE})?\b", testo)
    if not m:
        return ""
    return m.group(1) + (m.group(2) or "")


_ART = rf"\bart(?:icolo|\.)?\s*(\d+)(?:\s*[-\s]\s*({_SUFFISSO_RE}))?\b"
_RICHIESTA_TESTO = re.compile(
    r"\b(testo|cosa (?:dice|prevede|stabilisce)|che cosa (?:dice|prevede)|riporta|leggi|trascrivi|dimmi|mostra|recita|contenuto)\b"
)


def riconosci_articolo(domanda: str) -> RichiestaArticolo | None:
    """Riconosce la richiesta del testo di un articolo con atto identificato con certezza."""
    testo = _norm(domanda)
    m = re.search(_ART, testo)
    if not m:
        return None
    if not _RICHIESTA_TESTO.search(testo) and not re.fullmatch(r"\s*" + _ART + r".{0,40}", testo.strip()):
        return None
    numero = m.group(1) + (f"-{m.group(2)}" if m.group(2) else "")
    chiave = m.group(1) + (m.group(2) or "")
    coda = testo[m.end():m.end() + 80]
    for codice in CODICI:
        for sinonimo in codice.sinonimi:
            s = re.escape(_norm(sinonimo))
            if re.match(rf"\s*(?:,\s*)?(?:comma \d+\s*,?\s*)?(?:del(?:la|l')?\s+)?{s}(?![a-z])", coda):
                return RichiestaArticolo(numero, chiave, codice.etichetta, codice.urn)
    for modello, parte_urn, sigla in TIPI_ATTO:
        ml = re.match(rf"\s*(?:,\s*)?(?:comma \d+\s*,?\s*)?(?:del(?:la|l')?\s+|della\s+)?(?:{modello})\s*(?:n\.?\s*)?(\d{{1,5}})\s*(?:/|,?\s*del)\s*(\d{{4}}|\d{{2}})\b", coda)
        if ml:
            anno = ml.group(2)
            if len(anno) == 2:
                anno = ("19" if int(anno) > 30 else "20") + anno
            return RichiestaArticolo(numero, chiave, f"{sigla} {ml.group(1)}/{anno}", "", (parte_urn, anno, ml.group(1)))
    return None


def _connessione(percorso: str | Path) -> sqlite3.Connection | None:
    p = Path(str(percorso or ""))
    if not str(percorso or "") or not p.is_file():
        return None
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _documenti(conn: sqlite3.Connection, richiesta: RichiestaArticolo) -> list[sqlite3.Row]:
    colonne = "id, urn, titolo, vigenza, data_pubblicazione, imported_at, collection_name"
    if richiesta.urn:
        righe = conn.execute(
            f"SELECT {colonne} FROM normative_documents WHERE urn = ? OR urn LIKE ? OR urn LIKE ?",
            (richiesta.urn, richiesta.urn + "!%", richiesta.urn + "~%"),
        ).fetchall()
    else:
        tipo, anno, numero = richiesta.urn_parti
        righe = [
            r for r in conn.execute(
                f"SELECT {colonne} FROM normative_documents WHERE urn LIKE ? AND urn LIKE ?",
                (f"%{tipo}%", f"%:{anno}-%"),
            ).fetchall()
            if re.search(rf":{anno}-\d\d-\d\d;{numero}(?!\d)", r["urn"] or "")
        ]
    # Più recente prima: l'importazione notturna aggiorna il testo vigente.
    return sorted(righe, key=lambda r: (str(r["imported_at"] or ""), int(r["id"])), reverse=True)


def testo_articolo(percorso_db: str | Path, richiesta: RichiestaArticolo) -> dict[str, Any] | None:
    """Il testo dell'articolo come importato da Normattiva, o None se l'archivio non lo contiene."""
    try:
        conn = _connessione(percorso_db)
    except sqlite3.Error:
        return None
    if conn is None:
        return None
    try:
        for documento in _documenti(conn, richiesta):
            articoli = [
                a for a in conn.execute(
                    "SELECT id, article_number, article_text FROM normative_articles WHERE document_id = ? ORDER BY id",
                    (documento["id"],),
                ).fetchall()
                if chiave_articolo(a["article_number"] or "") == richiesta.chiave and len(a["article_text"] or "") >= 12
            ]
            if not articoli:
                continue
            # Il R.D. 262/1942 contiene anche le preleggi (artt. 1-31): l'articolo del
            # codice civile è l'ultimo con quel numero.
            scelto = articoli[-1] if richiesta.urn == _URN_CODICE_CIVILE else articoli[0]
            return {
                "testo": str(scelto["article_text"]).strip(),
                "urn": documento["urn"] or richiesta.urn,
                "titolo_atto": documento["titolo"] or "",
                "vigenza": documento["vigenza"] or "",
                "importato_il": str(documento["imported_at"] or "")[:10],
                "raccolta": documento["collection_name"] or "",
            }
        return None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


_ORGANI = (
    (r"\bcass(?:azione|\.)?\b|suprema corte|\bs\.?u\.?\b|sezioni unite", "cassazione"),
    (r"corte cost(?:ituzionale|\.)?|\bc\.?\s?cost\.?", "costituzionale"),
    (r"consiglio di stato|cons\.?\s?stato|\bcds\b", "consiglio di stato"),
)
_NUMERO_ANNO = re.compile(r"\b(?:n\.?|nr\.?|numero|sent(?:enza|\.)?|ord(?:inanza|\.)?)\s*(\d{1,6})\s*(?:/\s*|del\s+(?:\d{1,2}[./-]\d{1,2}[./-])?|dell'anno\s+)(\d{4})\b")


_ORGANO_NUMERO = re.compile(r"\b(?:cass(?:azione|\.)?|corte cost(?:ituzionale|\.)?|cons\.?\s?stato|consiglio di stato)[^0-9]{0,40}?(\d{1,6})\s*/\s*(\d{4})\b")


def riconosci_sentenza(domanda: str) -> RichiestaSentenza | None:
    testo = _norm(domanda)
    if not re.search(r"sentenz|ordinanz|pronuncia|decision|cass|corte|consiglio di stato|\bcds\b", testo):
        return None
    m = _NUMERO_ANNO.search(testo) or _ORGANO_NUMERO.search(testo)
    if not m:
        return None
    organo = next((nome for modello, nome in _ORGANI if re.search(modello, testo)), "")
    return RichiestaSentenza(organo, m.group(1), m.group(2))


def _numero_coincide(valore: str, richiesta: RichiestaSentenza) -> bool:
    for parte in re.split(r"[;,]", str(valore or "")):
        m = re.search(r"(\d{1,6})\s*(?:/\s*(\d{2,4}))?", parte)
        if m and m.group(1).lstrip("0") == richiesta.numero.lstrip("0"):
            anno = m.group(2) or ""
            if not anno or anno == richiesta.anno or (len(anno) == 2 and richiesta.anno.endswith(anno)):
                return True
    return False


def _organo_coincide(riga: dict[str, Any], richiesta: RichiestaSentenza) -> bool:
    if not richiesta.organo:
        return True
    testo = _norm(" ".join(str(riga.get(k) or "") for k in ("organo_giudicante", "ufficio", "source_system", "titolo")))
    chiavi = {
        "cassazione": ("cassazione", "cass"),
        "costituzionale": ("costituzional",),
        "consiglio di stato": ("consiglio di stato", "giustizia_amministrativa", "cds"),
    }[richiesta.organo]
    return any(c in testo for c in chiavi)


def trova_sentenza(sentenze: Iterable[dict[str, Any]], richiesta: RichiestaSentenza) -> dict[str, Any] | None:
    """La sentenza con numero e anno esatti (e organo, se indicato) nell'archivio."""
    for riga in sentenze:
        anno = str(riga.get("anno") or str(riga.get("data_deposito") or riga.get("data_decisione") or "")[:4])
        if not _numero_coincide(riga.get("numero_provvedimento", ""), richiesta):
            continue
        numero_con_anno = "/" in str(riga.get("numero_provvedimento") or "")
        if not numero_con_anno and anno and anno != richiesta.anno:
            continue
        if _organo_coincide(riga, richiesta):
            return riga
    return None


def _blocco_citato(testo: str) -> str:
    return "\n".join("> " + riga if riga.strip() else ">" for riga in str(testo).splitlines())


def risposta_articolo(domanda: str, percorso_db: str | Path) -> dict[str, Any] | None:
    richiesta = riconosci_articolo(domanda)
    if richiesta is None:
        return None
    trovato = testo_articolo(percorso_db, richiesta)
    if trovato is None:
        collegamento = richiesta.collegamento()
        return {
            "testo": (
                f"Il testo dell'{richiesta.citazione} non è nell'archivio Normattiva di IUSENTRA, quindi non lo riporto: "
                "non ricostruisco a memoria il testo di una norma. Puoi leggerlo nella versione vigente sulla fonte "
                f"ufficiale: {collegamento}"
            ),
            "fonti": [{"title": f"Normattiva — {richiesta.citazione}", "url": collegamento}],
            "tipo": "testo_articolo_assente",
        }
    collegamento = richiesta.collegamento(trovato["urn"].split("!")[0].split("~")[0])
    righe = [
        f"**{richiesta.citazione[0].upper()}{richiesta.citazione[1:]}** — testo dall'archivio Normattiva di IUSENTRA "
        f"(importato il {trovato['importato_il'] or 'data non registrata'}):",
        "",
        _blocco_citato(trovato["testo"]),
        "",
        f"Fonte ufficiale: {collegamento}",
    ]
    if trovato["vigenza"]:
        righe.append(f"Versione dell'archivio: {trovato['vigenza']}.")
    righe.append("Prima di citarlo in un atto verifica sulla fonte ufficiale le modifiche successive all'importazione.")
    return {
        "testo": "\n".join(righe),
        "fonti": [{"title": f"Normattiva — {richiesta.citazione}", "url": collegamento}],
        "tipo": "testo_articolo",
    }


def risposta_sentenza(domanda: str, sentenze: Callable[[], Iterable[dict[str, Any]]] | None) -> dict[str, Any] | None:
    richiesta = riconosci_sentenza(domanda)
    if richiesta is None:
        return None
    riga = None
    if sentenze is not None:
        try:
            riga = trova_sentenza(sentenze(), richiesta)
        except Exception:
            riga = None
    if riga is None:
        fonte = {
            "cassazione": ("SentenzeWeb (Corte di cassazione)", SENTENZEWEB),
            "costituzionale": ("Corte costituzionale", "https://www.cortecostituzionale.it/actionPronuncia.do"),
            "consiglio di stato": ("Giustizia amministrativa", "https://www.giustizia-amministrativa.it/"),
        }.get(richiesta.organo, ("Portale della giurisprudenza ufficiale", SENTENZEWEB))
        return {
            "testo": (
                f"La pronuncia {richiesta.citazione} non è nell'archivio giurisprudenza di IUSENTRA, quindi non ne riporto "
                f"il contenuto: non ricostruisco a memoria massime o principi. Puoi consultarla su {fonte[0]}: {fonte[1]}"
            ),
            "fonti": [{"title": fonte[0], "url": fonte[1]}],
            "tipo": "sentenza_assente",
        }
    url = str(riga.get("url_pagina_ufficiale") or riga.get("url_origine") or "")
    verificata = bool(riga.get("fonte_ufficiale_confermata")) or str(riga.get("stato_verifica_fonte") or "") in {"verificata", "verificato", "confermata"}
    righe = [f"**{riga.get('titolo') or richiesta.citazione}**"]
    dettagli = [str(riga.get(k) or "") for k in ("organo_giudicante", "sezione", "tipo_provvedimento")]
    data = str(riga.get("data_deposito") or riga.get("data_decisione") or "")
    if data:
        dettagli.append(f"depositata il {data[8:10]}/{data[5:7]}/{data[:4]}" if len(data) >= 10 else data)
    dettagli = [d for d in dettagli if d]
    if dettagli:
        righe.append(" · ".join(dettagli))
    for chiave, etichetta in (("massima", "Massima"), ("principio_diritto", "Principio di diritto")):
        if riga.get(chiave):
            righe.extend(["", f"{etichetta} (come registrata nell'archivio):", _blocco_citato(riga[chiave])])
    if not riga.get("massima") and not riga.get("principio_diritto"):
        righe.extend(["", "Nell'archivio non sono registrati massima né principio di diritto di questa pronuncia."])
    righe.append("")
    righe.append(f"Pagina ufficiale: {url}" if url else "Pagina ufficiale non registrata nell'archivio.")
    if not verificata:
        righe.append("Fonte non ancora confermata sull'originale: verificala prima di citarla in un atto.")
    return {
        "testo": "\n".join(righe),
        "fonti": [{"title": richiesta.citazione, "url": url}] if url else [],
        "tipo": "sentenza",
    }


__all__ = [
    "CODICI",
    "RichiestaArticolo",
    "RichiestaSentenza",
    "chiave_articolo",
    "riconosci_articolo",
    "riconosci_sentenza",
    "risposta_articolo",
    "risposta_sentenza",
    "testo_articolo",
    "trova_sentenza",
]
