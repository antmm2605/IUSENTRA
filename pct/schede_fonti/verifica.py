"""Verifica delle norme delle schede contro l'edizione vigente della biblioteca «Codici e leggi»."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass, field
from pathlib import Path
from datetime import date

from lex.normativa.biblioteca.fabbisogno import COLLEZIONE, CARTELLA_SCHEDE, norm_articolo, riferimenti_schede

ABROGATO_INTERO = re.compile(r"^\s*Art\.?\s*[\w\-.]+\s*(?:\([^)]*\))?\s*\(*\s*ARTICOLO\s+ABROGATO", re.I)
SOSTITUITO_DA = re.compile(r"ABROGAT[OA]\s+DA(?:L|LLA|LL')?\s+([^()]{5,160}?)\s*(?:\)\)|\)\s*$|$)", re.I)
COMMI_ABROGATI = re.compile(r"COMM[AI]\s+[^.]{0,40}?ABROGAT", re.I)


@dataclass
class EsitoNorma:
    scheda: str
    atto: str
    articolo: str
    origine: str
    perche: str
    stato: str  # "presente" | "abrogato" | "atto_assente" | "articolo_assente"
    sha256: str = ""
    url: str = ""
    aggiornato_al: str = ""
    commi_abrogati: int = 0
    abrogato_da: str = ""
    testo: str = ""
    acquisita_il: str = ""
    document_id: int | None = None
    article_id: int | None = None
    provenienza_archivio: dict = field(default_factory=dict)

    def chiave(self) -> tuple[str, str, str]:
        return (self.scheda, self.atto, norm_articolo(self.articolo))


def sha_testo(testo: str) -> str:
    return hashlib.sha256((testo or "").encode("utf-8")).hexdigest()


def _url(meta_json: str, urn: str) -> str:
    try:
        meta = json.loads(meta_json or "{}")
        fonte = meta.get("consultazione_fonte") or {}
        fonte = json.loads(fonte) if isinstance(fonte, str) else fonte
        if fonte.get("url"):
            return str(fonte["url"])
    except (TypeError, ValueError):
        pass
    return f"https://www.normattiva.it/uri-res/N2Ls?{urn}" if urn else ""


def verifica_schede(db: Path, cartella: Path = CARTELLA_SCHEDE, *, solo_scheda: str = "", alla_data: date | None = None) -> list[EsitoNorma]:
    refs = [r for r in riferimenti_schede(cartella,solo_scheda=solo_scheda) if not solo_scheda or r.scheda == solo_scheda]
    esiti: list[EsitoNorma] = []
    cache: dict[tuple[str, str], list] = {}
    with closing(sqlite3.connect(Path(db).resolve().as_uri() + "?mode=ro", uri=True, timeout=10)) as conn:
        conn.execute("PRAGMA cache_size=-32768")
        from lex.normativa.provenienza_edizione import priorita_edizione_archiviata
        from lex.normativa.biblioteca.identita import espressione_numero_articolo_sql
        target = alla_data or date.today()
        collections = list(dict.fromkeys(COLLEZIONE + ref.atto for ref in refs))
        ultimi = {}
        priorities = {}
        for offset in range(0, len(collections), 200):
            batch = collections[offset:offset + 200]
            sql = """SELECT d.id,d.collection_name,d.redazione_id,d.urn,d.xml_sha256,
                (SELECT c.metadata_json FROM normative_chunks c WHERE c.document_id=d.id ORDER BY c.id LIMIT 1)
                FROM normative_documents d WHERE d.collection_name IN (""" + ",".join("?" for _ in batch) + ")"
            for ident, coll, red, urn, xmlsha, raw in conn.execute(sql, batch):
                try:
                    md = json.loads(raw or "{}")
                except (TypeError, ValueError):
                    md = {}
                md = md if isinstance(md, dict) else {}
                document = {"id": ident, "urn": urn, "redazione_id": red, "xml_sha256": xmlsha}
                priority = priorita_edizione_archiviata(md, document, target)
                key = coll[len(COLLEZIONE):]
                if key not in priorities or priority > priorities[key]:
                    priorities[key] = priority
                    ultimi[key] = (int(ident), red or "", urn or "", priority[1])
        for r in refs:
            base = dict(scheda=r.scheda, atto=r.atto, articolo=r.articolo, origine=r.origine, perche=r.perche)
            doc = ultimi.get(r.atto)
            if not doc:
                esiti.append(EsitoNorma(**base, stato="atto_assente"))
                continue
            k = (r.atto, norm_articolo(r.articolo))
            if k not in cache:
                cache[k] = conn.execute(
                    "SELECT a.article_text, (SELECT c.metadata_json FROM normative_chunks c WHERE c.article_id = a.id "
                    "ORDER BY c.id LIMIT 1), a.id FROM normative_articles a WHERE a.document_id = ? AND "
                    + espressione_numero_articolo_sql("a.article_number") + " = ?", (doc[0], k[1])).fetchall()
            righe = cache[k]
            if len(righe)>1:
                esiti.append(EsitoNorma(**base, stato="articolo_ambiguo", aggiornato_al=doc[1], document_id=doc[0]))
                continue
            riga = righe[0] if righe else None
            if not riga:
                esiti.append(EsitoNorma(**base, stato="articolo_assente", aggiornato_al=doc[1]))
                continue
            testo = riga[0] or ""
            da = SOSTITUITO_DA.search(testo[:400])
            from lex.normativa.qualita_testo import qualita_testo
            try:
                metadata=json.loads(riga[1] or "{}")
            except (TypeError,ValueError):
                metadata={}
            quality=qualita_testo(testo,solo_rubrica=isinstance(metadata,dict) and metadata.get("consultazione_senza_testo") is True)
            intero = bool(ABROGATO_INTERO.search(testo)) or quality=="avviso_abrogazione"
            esiti.append(EsitoNorma(
                **base, stato="abrogato" if intero else ("testo_non_integrale" if quality!="testo_acquisito" else "presente"), sha256=sha_testo(testo), url=_url(riga[1], doc[2]),
                aggiornato_al=doc[1], commi_abrogati=len(COMMI_ABROGATI.findall(testo)),
                abrogato_da=(da.group(1).strip() if (intero and da) else ""), testo=testo, acquisita_il=doc[3][:10], document_id=doc[0], article_id=riga[2], provenienza_archivio=metadata if isinstance(metadata,dict) else {}))
    return esiti


def campi_obbligatori_senza_norma(cartella: Path = CARTELLA_SCHEDE) -> list[tuple[str, str]]:
    out = []
    for f in sorted(Path(cartella).glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for c in d.get("campi") or []:
            if c.get("obbligatorio") and not c.get("norma") and (c.get("fonte") or {}).get("tipo") != "database":
                out.append((str(d.get("id") or f.stem), str(c.get("campo"))))
    return out


def riepilogo(esiti: list[EsitoNorma]) -> dict:
    stati: dict[str, int] = {}
    for e in esiti:
        stati[e.stato] = stati.get(e.stato, 0) + 1
    return {"norme": len(esiti), "stati": stati,
            "con_commi_abrogati": sum(1 for e in esiti if e.commi_abrogati),
            "problemi": [{k: v for k, v in asdict(e).items() if k != "testo"} for e in esiti if e.stato != "presente"]}
